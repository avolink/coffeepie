"""Provider node registry endpoints — backs the Proveedores tab.

The first real "write" path of the panel: registering a node persists it in the
`node` table (db/01_schema.sql), owned by the authenticated provider. Reads are
scoped to the caller's own nodes (admins see all).
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.identity import AuthenticatedUser, Role, roles_of
from app.auth.rbac import require_roles
from app.db import get_conn

router = APIRouter(prefix="/nodes", tags=["nodes"])

VALID_STATUS = ("active", "maintenance", "offline")

# Coffee Pie Slice base (AGENTS.md): one Slice = 1 vCore (CPU 4x overcommit),
# 1 GB RAM, 8 GB SSD, 125 MB GPU VRAM. A node's Slice count is the bottleneck
# resource — every Slice streams, so a node with no GPU serves no Slices.
_CPU_OVERCOMMIT = 4
_SLICE_RAM_GB = 1
_SLICE_SSD_GB = 8
_SLICE_GPU_MB = 125

# Hypervisors we can detect. Proxmox is the recommended/most common, hence weighted.
_HYPERVISORS = ["proxmox", "proxmox", "proxmox", "esxi", "kvm", "hyperv", "xen"]


def _slices_for(vcores: int, ram_gb: int, ssd_gb: int, gpu_vram_mb: int) -> tuple[int, str]:
    """How many Slices a node can serve = the bottleneck resource."""
    candidates = {
        "CPU": vcores * _CPU_OVERCOMMIT,
        "RAM": ram_gb // _SLICE_RAM_GB,
        "SSD": ssd_gb // _SLICE_SSD_GB,
        "GPU": gpu_vram_mb // _SLICE_GPU_MB,
    }
    bottleneck = min(candidates, key=candidates.get)
    return candidates[bottleneck], bottleneck


def _probe_hardware(public_ip: str) -> dict:
    """Measure a node's REAL hardware capacity AND detect its hypervisor.

    This is the anti-fraud core: capacity and hypervisor are determined *here*,
    server-side, and the create/update endpoints use this — they never trust
    client-sent values, so a DC admin can neither inflate how many Slices they
    serve nor mis-state their platform.

    The hypervisor is *detected*, not chosen: in production we fingerprint the
    management API at `public_ip` (Proxmox `:8006/api2/json/version`, ESXi
    `:443/sdk`, libvirt/KVM `:16509`, Hyper-V WinRM `:5985`, XenServer XAPI), or
    simply read it off the DC-Agent, which already knows which adapter it loaded.

    QA stand-in: deterministic from the node's public IP, so results are stable
    and reproducible without a live hypervisor. Only the body changes in prod;
    the contract (measured/detected, not declared) stays identical.
    """
    seed = int(hashlib.sha256((public_ip or "").encode()).hexdigest(), 16)
    vcores = 16 + (seed % 7) * 8                       # 16..64
    ram_gb = vcores * (4 if (seed >> 3) & 1 else 8)    # 4 or 8 GB/core
    ssd_gb = 1000 * (1 + (seed >> 6) % 8)              # 1..8 TB
    gpu_vram_mb = [8000, 16000, 16000, 24000, 48000][(seed >> 9) % 5]
    hypervisor = _HYPERVISORS[(seed >> 12) % len(_HYPERVISORS)]
    slices, bottleneck = _slices_for(vcores, ram_gb, ssd_gb, gpu_vram_mb)
    return {
        "vcores": vcores,
        "ram_gb": ram_gb,
        "ssd_gb": ssd_gb,
        "gpu_vram_mb": gpu_vram_mb,
        "hypervisor": hypervisor,
        "slices": slices,
        "bottleneck": bottleneck,
    }


class NodeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    public_ip: str = Field(min_length=1, max_length=64)
    vcores: int = Field(ge=0, le=4096)
    ram_gb: int = Field(ge=0, le=65536)
    ssd_gb: int = Field(ge=0, le=1048576)
    gpu_vram_mb: int = Field(default=0, ge=0, le=1048576)
    hypervisor: str = Field(default="proxmox", max_length=40)
    location: str = Field(default="", max_length=160)


class NodeOut(NodeIn):
    id: str
    provider_id: str
    status: str
    created_at: str


class NodePatch(BaseModel):
    """Partial update — only the fields present are written."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    public_ip: str | None = Field(default=None, min_length=1, max_length=64)
    vcores: int | None = Field(default=None, ge=0, le=4096)
    ram_gb: int | None = Field(default=None, ge=0, le=65536)
    ssd_gb: int | None = Field(default=None, ge=0, le=1048576)
    gpu_vram_mb: int | None = Field(default=None, ge=0, le=1048576)
    hypervisor: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=160)
    status: str | None = None


class ProbeIn(BaseModel):
    # Hypervisor is detected, not supplied — only the IP is needed to reach the node.
    public_ip: str = Field(min_length=1, max_length=64)


class ProbeOut(BaseModel):
    vcores: int
    ram_gb: int
    ssd_gb: int
    gpu_vram_mb: int
    hypervisor: str
    slices: int
    bottleneck: str


def _is_unique_violation(e: Exception) -> bool:
    s = str(e)
    return "23505" in s or "duplicate key" in s.lower()


def _row_to_node(r) -> NodeOut:
    return NodeOut(
        id=r[0],
        provider_id=r[1],
        name=r[2],
        public_ip=str(r[3]) if r[3] is not None else "",
        vcores=r[4],
        ram_gb=r[5],
        ssd_gb=r[6],
        gpu_vram_mb=r[7],
        hypervisor=r[8],
        location=r[9] or "",
        status=r[10],
        created_at=str(r[11]),
    )


_SELECT = """
    SELECT id::text, provider_id::text, name, public_ip, vcores, ram_gb,
           ssd_gb, gpu_vram_mb, hypervisor, location, status, created_at
    FROM node
"""


@router.get("", response_model=list[NodeOut])
def list_nodes(user: AuthenticatedUser = Depends(require_roles(Role.PROVIDER))):
    """The caller's own nodes (admins see every node)."""
    is_admin = Role.ADMIN in roles_of(user)
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            if is_admin:
                cur.execute(_SELECT + " ORDER BY created_at")
            else:
                cur.execute(
                    _SELECT + " WHERE provider_id = %s::uuid ORDER BY created_at",
                    (user.uid,),
                )
            rows = cur.fetchall()
        finally:
            cur.close()
    return [_row_to_node(r) for r in rows]


@router.post("/probe", response_model=ProbeOut)
def probe_node(
    body: ProbeIn,
    user: AuthenticatedUser = Depends(require_roles(Role.PROVIDER)),
):
    """Measure the real hardware capacity of a node at the given IP.

    Provider-gated. The returned numbers are what create/update will store — the
    panel renders them read-only so the admin cannot edit how many Slices the node
    serves; they can only re-run this probe.
    """
    return ProbeOut(**_probe_hardware(body.public_ip))


@router.post("", response_model=NodeOut, status_code=201)
def create_node(
    body: NodeIn,
    user: AuthenticatedUser = Depends(require_roles(Role.PROVIDER)),
):
    """Register a node owned by the authenticated provider.

    Capacity is measured server-side from the node's IP — client-supplied
    vcores/ram/ssd/gpu are ignored, so a provider cannot over-declare capacity.
    """
    node_id = str(uuid.uuid4())
    measured = _probe_hardware(body.public_ip)
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO node
                    (id, provider_id, name, public_ip, vcores, ram_gb,
                     ssd_gb, gpu_vram_mb, hypervisor, location, status)
                VALUES (%s::uuid, %s::uuid, %s, %s::inet, %s, %s, %s, %s, %s, %s, 'active')
                """,
                (
                    node_id,
                    user.uid,
                    body.name,
                    body.public_ip,
                    measured["vcores"],
                    measured["ram_gb"],
                    measured["ssd_gb"],
                    measured["gpu_vram_mb"],
                    measured["hypervisor"],
                    body.location,
                ),
            )
            conn.commit()
            cur.execute(_SELECT + " WHERE id = %s::uuid", (node_id,))
            row = cur.fetchone()
        except Exception as e:
            conn.rollback()
            if _is_unique_violation(e):
                raise HTTPException(
                    status_code=409,
                    detail=f'Ya tienes un nodo llamado "{body.name}".',
                )
            # inet cast rejects malformed IPs, CHECKs reject bad numbers, etc.
            raise HTTPException(status_code=400, detail=f"Invalid node data: {e}")
        finally:
            cur.close()
    return _row_to_node(row)


@router.patch("/{node_id}", response_model=NodeOut)
def update_node(
    node_id: str,
    body: NodePatch,
    user: AuthenticatedUser = Depends(require_roles(Role.PROVIDER)),
):
    """Partially update a node. Owners edit their own; admins any."""
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    # Capacity AND hypervisor are server-measured/detected, never client-supplied.
    # Drop anything the client tried to send; re-probe only if the IP changed.
    for measured_key in ("vcores", "ram_gb", "ssd_gb", "gpu_vram_mb", "hypervisor"):
        fields.pop(measured_key, None)
    if "public_ip" in fields:
        measured = _probe_hardware(fields["public_ip"])
        fields["vcores"] = measured["vcores"]
        fields["ram_gb"] = measured["ram_gb"]
        fields["ssd_gb"] = measured["ssd_gb"]
        fields["gpu_vram_mb"] = measured["gpu_vram_mb"]
        fields["hypervisor"] = measured["hypervisor"]
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "status" in fields and fields["status"] not in VALID_STATUS:
        raise HTTPException(
            status_code=400, detail=f"status must be one of {VALID_STATUS}"
        )

    # Column names come from the NodePatch model, never from the request.
    casts = {"public_ip": "%s::inet", "status": "%s::node_status"}
    set_sql = ", ".join(k + " = " + casts.get(k, "%s") for k in fields)
    params: list = list(fields.values())

    is_admin = Role.ADMIN in roles_of(user)
    where = "id = %s::uuid"
    params.append(node_id)
    if not is_admin:
        where += " AND provider_id = %s::uuid"
        params.append(user.uid)

    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(f"UPDATE node SET {set_sql} WHERE {where}", params)
            updated = cur.rowcount
            conn.commit()
            if updated:
                cur.execute(_SELECT + " WHERE id = %s::uuid", (node_id,))
                row = cur.fetchone()
        except Exception as e:
            conn.rollback()
            if _is_unique_violation(e):
                raise HTTPException(
                    status_code=409,
                    detail=f'Ya tienes un nodo llamado "{fields.get("name", "")}".',
                )
            raise HTTPException(status_code=400, detail=f"Invalid node data: {e}")
        finally:
            cur.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Node not found or not yours")
    return _row_to_node(row)


@router.delete("/{node_id}", status_code=204)
def delete_node(
    node_id: str,
    user: AuthenticatedUser = Depends(require_roles(Role.PROVIDER)),
):
    """Remove a node. Owners can delete their own; admins any."""
    is_admin = Role.ADMIN in roles_of(user)
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            if is_admin:
                cur.execute("DELETE FROM node WHERE id = %s::uuid", (node_id,))
            else:
                cur.execute(
                    "DELETE FROM node WHERE id = %s::uuid AND provider_id = %s::uuid",
                    (node_id, user.uid),
                )
            deleted = cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Invalid node id")
        finally:
            cur.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Node not found or not yours")
