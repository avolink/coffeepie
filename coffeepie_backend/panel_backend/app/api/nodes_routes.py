"""Provider node registry endpoints — backs the Proveedores tab.

The first real "write" path of the panel: registering a node persists it in the
`node` table (db/01_schema.sql), owned by the authenticated provider. Reads are
scoped to the caller's own nodes (admins see all).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.identity import AuthenticatedUser, Role, roles_of
from app.auth.rbac import require_roles
from app.db import get_conn

router = APIRouter(prefix="/nodes", tags=["nodes"])

VALID_STATUS = ("active", "maintenance", "offline")


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


@router.post("", response_model=NodeOut, status_code=201)
def create_node(
    body: NodeIn,
    user: AuthenticatedUser = Depends(require_roles(Role.PROVIDER)),
):
    """Register a node owned by the authenticated provider."""
    node_id = str(uuid.uuid4())
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
                    body.vcores,
                    body.ram_gb,
                    body.ssd_gb,
                    body.gpu_vram_mb,
                    body.hypervisor,
                    body.location,
                ),
            )
            conn.commit()
            cur.execute(_SELECT + " WHERE id = %s::uuid", (node_id,))
            row = cur.fetchone()
        except Exception as e:
            conn.rollback()
            # inet cast rejects malformed IPs, CHECKs reject bad numbers, etc.
            raise HTTPException(status_code=400, detail=f"Invalid node data: {e}")
        finally:
            cur.close()
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
