"""Consumer virtual machines on the QFDM Network.

Implements the /vms/* contract the frontends (QML client and the browser
"Mis Máquinas" page) speak:

  POST   /vms                    create a machine (Big_Package tier)
  GET    /vms/me                 the caller's machines
  GET    /vms/{id}/status        live hypervisor status (syncs the row)
  POST   /vms/{id}/start|stop|shutdown|reboot
  PATCH  /vms/{id}/specs         resize Slices — only while the VM is off
  DELETE /vms/{id}

Scheduling ("closest node with space"): rank every active node that has
stored root credentials by real TCP round-trip time to its hypervisor port
(8006), keep only nodes whose free Slice capacity (vcores − already-allocated
slices) covers the request, and provision on the lowest-latency one. With one
node registered the ranking is trivial, but the algorithm is the real one.

Provisioning is asynchronous: POST /vms returns immediately with
status='creating'; a background task clones the node's OS template, sizes it
(cores = slices, memory = slices GiB — QFDM: 1 Slice = 1 vCore + 1 GiB), and
flips the row to 'created'. The frontend polls /vms/me and notifies the user.

Honest scope notes:
  * template per OS: the node is searched for a template whose name matches
    the requested OS; if none matches, the node's default template is used
    (single-template nodes serve every OS request with what they have);
  * recurrence (minute/month/year) is stored for billing but the billing
    engine itself is future work;
  * disk is not resized on Slice changes (linked clones share the template's
    disk); cores and memory are.
"""
from __future__ import annotations

import socket
import time
import uuid as uuidlib

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.stream_routes import _authenticate, _pve, _wait_task
from app.auth.identity import AuthenticatedUser
from app.auth.node_credentials import decrypt_password
from app.auth.rbac import verify_bearer_token
from app.db import get_conn

router = APIRouter(prefix="/vms", tags=["vms"])

RATE_CR_PER_SLICE_MIN = 30      # Cr per Slice per minute (uniform base rate)
MAX_SLICES = 256


# ── Schemas ────────────────────────────────────────────────────────────────
class VmCreateIn(BaseModel):
    name: str = Field(default="Mi Máquina", max_length=80)
    os: str = Field(max_length=32)
    slices: int = Field(ge=1, le=MAX_SLICES)
    recurrence: str = Field(default="minute", pattern="^(minute|month|year)$")


class VmSpecsIn(BaseModel):
    slices: int = Field(ge=1, le=MAX_SLICES)


# ── Helpers ────────────────────────────────────────────────────────────────
def _require_big(user: AuthenticatedUser) -> None:
    tier = str((user.claims.get("app_metadata") or {}).get("tier", "free")).lower()
    if tier != "big_package":
        raise HTTPException(403, "Crear y usar máquinas en el navegador requiere el Paquete Grande.")


def _row_to_vm(r) -> dict:
    (vid, owner, node_id, pvmid, name, os_key, slices, recurrence,
     rate, status, err, created, node_name) = r
    return {
        "id": str(vid),
        "vmid": pvmid,
        "name": name,
        "os": os_key,
        "slices": slices,
        "recurrence": recurrence,
        "credits_for_minutes": float(rate),
        "status": status,
        "error_detail": err,
        "node": node_name,
        "created_at": created.isoformat() if created else None,
        # legacy specs shape the QML client reads
        "specs": {"so": os_key, "cpu": slices, "memory": slices * 1024, "storage": slices * 8},
    }


_VM_SELECT = (
    "SELECT v.id, v.owner_id, v.node_id, v.proxmox_vmid, v.name, v.os, v.slices, "
    "v.recurrence, v.rate_cr_min, v.status, v.error_detail, v.created_at, n.name "
    "FROM vm v LEFT JOIN node n ON n.id = v.node_id "
)


def _get_vm(vm_id: str, owner_uid: str) -> dict:
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(_VM_SELECT + "WHERE v.id = %s::uuid AND v.owner_id = %s::uuid",
                        (vm_id, owner_uid))
            row = cur.fetchone()
        finally:
            cur.close()
    if not row:
        raise HTTPException(404, "Máquina no encontrada.")
    return _row_to_vm(row)


def _vm_update(vm_id: str, **fields) -> None:
    keys = list(fields.keys())
    sets = ", ".join(f"{k} = %s" for k in keys)
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(f"UPDATE vm SET {sets} WHERE id = %s::uuid",
                        tuple(fields[k] for k in keys) + (vm_id,))
            conn.commit()
        finally:
            cur.close()


def _node_creds(node_id: str) -> dict:
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT name, host(public_ip), root_username, root_password_enc "
                "FROM node WHERE id = %s::uuid", (node_id,))
            row = cur.fetchone()
        finally:
            cur.close()
    if not row or not row[3]:
        raise HTTPException(503, "El nodo de esta máquina no está disponible.")
    return {"name": row[0], "ip": row[1], "user": row[2], "pw": decrypt_password(row[3])}


# ── Scheduler: lowest-ping node with free Slice capacity ───────────────────
def _tcp_ping_ms(ip: str, port: int = 8006, attempts: int = 2) -> float | None:
    """Real reachability + latency: TCP connect time to the hypervisor port.
    Returns the best of `attempts` in ms, or None if unreachable."""
    best = None
    for _ in range(attempts):
        t0 = time.monotonic()
        try:
            with socket.create_connection((ip, port), timeout=4):
                dt = (time.monotonic() - t0) * 1000.0
        except OSError:
            continue
        best = dt if best is None else min(best, dt)
    return best


def _rank_nodes(slices_needed: int) -> list[dict]:
    """Active credentialed nodes with enough free Slices, best ping first."""
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT n.id, n.name, host(n.public_ip), n.root_username, "
                "       n.root_password_enc, n.vcores, "
                "       COALESCE((SELECT SUM(v.slices) FROM vm v "
                "                 WHERE v.node_id = n.id AND v.status != 'error'), 0) "
                "FROM node n WHERE n.status = 'active' "
                "AND n.root_password_enc IS NOT NULL AND n.public_ip IS NOT NULL"
            )
            rows = cur.fetchall()
        finally:
            cur.close()

    ranked = []
    for nid, name, ip, ruser, penc, vcores, used in rows:
        free = int(vcores or 0) - int(used or 0)
        if free < slices_needed:
            continue
        ping = _tcp_ping_ms(ip)
        if ping is None:
            continue                      # unreachable right now — skip
        ranked.append({"id": str(nid), "name": name, "ip": ip, "user": ruser,
                       "pw": decrypt_password(penc), "free": free, "ping_ms": ping})
    ranked.sort(key=lambda n: n["ping_ms"])
    return ranked


# ── Template selection + provisioning worker ───────────────────────────────
_OS_TOKENS = {
    "bodhi": ("bodhi",), "mint": ("mint",), "debian": ("debian",),
    "arch": ("arch", "manjaro"), "centos": ("cent",), "docker": ("docker", "ubuntu"),
    "win10": ("w10", "win10", "windows10"), "win11": ("w11", "win11", "windows11"),
    "steamos": ("steam",),
}


def _find_template(ip: str, cookie: str, pve_node: str, os_key: str):
    """Template vmid for the OS on this node; falls back to any template."""
    vms = _pve(ip, f"/nodes/{pve_node}/qemu", cookie=cookie) or []
    templates = [v for v in vms if v.get("template") == 1]
    if not templates:
        return None
    tokens = _OS_TOKENS.get(os_key, (os_key,))
    for t in templates:
        name = (t.get("name") or "").lower()
        if any(tok in name for tok in tokens):
            return t["vmid"]
    return templates[0]["vmid"]           # single-template node serves all


def _sanitize_pve_name(name: str, vm_row_id: str) -> str:
    """Proxmox VM names must be DNS names: ASCII [a-z0-9-] only. Note
    str.isalnum() is Unicode-aware ('á' passes), so filter to ASCII explicitly
    (accents in names like "Mi Máquina" would otherwise reach the API)."""
    import unicodedata
    ascii_name = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()
    s = "".join(c if ("a" <= c <= "z" or "0" <= c <= "9") else "-" for c in ascii_name)
    s = "-".join(filter(None, s.split("-")))[:40] or "maquina"
    return f"cp-{s}-{vm_row_id[:6]}"


def _provision(vm_row_id: str, os_key: str, slices: int, display_name: str) -> None:
    """Background worker: pick the best node, clone + size the VM, flip the
    row to 'created' (or 'error' with detail). Never raises."""
    try:
        nodes = _rank_nodes(slices)
        if not nodes:
            _vm_update(vm_row_id, status="error",
                       error_detail="No hay nodos con capacidad disponible en la Red QFDM.")
            return

        last_err = "sin detalle"
        for node in nodes:                # best ping first; fail over down the list
            try:
                cookie, csrf = _authenticate(node["ip"], node["user"], node["pw"])
                pve_node = _pve(node["ip"], "/nodes", cookie=cookie)[0]["node"]
                template = _find_template(node["ip"], cookie, pve_node, os_key)
                if template is None:
                    last_err = f"El nodo {node['name']} no tiene plantillas de SO."
                    continue

                newid = _pve(node["ip"], "/cluster/nextid", cookie=cookie)
                label = _sanitize_pve_name(display_name, vm_row_id)
                upid = _pve(node["ip"], f"/nodes/{pve_node}/qemu/{template}/clone",
                            cookie=cookie, csrf=csrf,
                            data={"newid": newid, "name": label, "full": 0})
                if not _wait_task(node["ip"], cookie, pve_node, upid, timeout=120):
                    last_err = f"La clonación falló en el nodo {node['name']}."
                    continue

                # QFDM sizing: 1 Slice = 1 vCore + 1 GiB RAM.
                _pve(node["ip"], f"/nodes/{pve_node}/qemu/{newid}/config",
                     cookie=cookie, csrf=csrf,
                     data={"cores": slices, "memory": slices * 1024})

                _vm_update(vm_row_id, status="created", node_id=node["id"],
                           proxmox_vmid=int(newid))
                return
            except Exception as e:          # noqa: BLE001 — try the next node
                last_err = str(e)[:200]

        _vm_update(vm_row_id, status="error",
                   error_detail=f"No se pudo crear la máquina: {last_err}")
    except Exception as e:                  # noqa: BLE001 — worker must not die silently
        _vm_update(vm_row_id, status="error", error_detail=str(e)[:200])


# ── Proxmox status/actions for an existing VM ──────────────────────────────
def _vm_session(vm: dict) -> dict:
    """Node creds + auth cookie for a provisioned VM."""
    if not vm["vmid"]:
        raise HTTPException(409, "La máquina aún se está creando.")
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT node_id FROM vm WHERE id = %s::uuid", (vm["id"],))
            node_id = cur.fetchone()[0]
        finally:
            cur.close()
    creds = _node_creds(str(node_id))
    cookie, csrf = _authenticate(creds["ip"], creds["user"], creds["pw"])
    pve_node = _pve(creds["ip"], "/nodes", cookie=cookie)[0]["node"]
    return {"ip": creds["ip"], "cookie": cookie, "csrf": csrf, "pve_node": pve_node}


def _pve_status(s: dict, vmid: int) -> str:
    st = _pve(s["ip"], f"/nodes/{s['pve_node']}/qemu/{vmid}/status/current", cookie=s["cookie"])
    return (st or {}).get("status", "unknown")


def _power(vm: dict, action: str) -> dict:
    s = _vm_session(vm)
    _pve(s["ip"], f"/nodes/{s['pve_node']}/qemu/{vm['vmid']}/status/{action}",
         cookie=s["cookie"], csrf=s["csrf"], data={})
    new = {"start": "running", "reboot": "running",
           "stop": "stopped", "shutdown": "stopped"}[action]
    _vm_update(vm["id"], status=new)
    vm["status"] = new
    return vm


# ── Routes ─────────────────────────────────────────────────────────────────
@router.post("", status_code=201)
def create_vm(body: VmCreateIn, bg: BackgroundTasks,
              user: AuthenticatedUser = Depends(verify_bearer_token)):
    _require_big(user)
    vm_id = str(uuidlib.uuid4())
    rate = body.slices * RATE_CR_PER_SLICE_MIN
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO vm (id, owner_id, name, os, slices, recurrence, rate_cr_min, status) "
                "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, 'creating')",
                (vm_id, user.uid, body.name.strip() or "Mi Máquina", body.os,
                 body.slices, body.recurrence, rate))
            conn.commit()
        finally:
            cur.close()
    bg.add_task(_provision, vm_id, body.os, body.slices, body.name)
    return _get_vm(vm_id, user.uid)


@router.get("/me")
def my_vms(user: AuthenticatedUser = Depends(verify_bearer_token)):
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(_VM_SELECT + "WHERE v.owner_id = %s::uuid ORDER BY v.created_at",
                        (user.uid,))
            rows = cur.fetchall()
        finally:
            cur.close()
    return [_row_to_vm(r) for r in rows]


@router.get("/{vm_id}/status")
def vm_status(vm_id: str, user: AuthenticatedUser = Depends(verify_bearer_token)):
    vm = _get_vm(vm_id, user.uid)
    if vm["status"] in ("creating", "error"):
        return {"status": vm["status"], "detail": vm.get("error_detail")}
    s = _vm_session(vm)
    live = _pve_status(s, vm["vmid"])
    mapped = "running" if live == "running" else ("stopped" if live == "stopped" else vm["status"])
    if mapped != vm["status"]:
        _vm_update(vm["id"], status=mapped)
    return {"status": mapped}


@router.post("/{vm_id}/start")
def start_vm(vm_id: str, user: AuthenticatedUser = Depends(verify_bearer_token)):
    return _power(_get_vm(vm_id, user.uid), "start")


@router.post("/{vm_id}/stop")
def stop_vm(vm_id: str, user: AuthenticatedUser = Depends(verify_bearer_token)):
    return _power(_get_vm(vm_id, user.uid), "stop")


@router.post("/{vm_id}/shutdown")
def shutdown_vm(vm_id: str, user: AuthenticatedUser = Depends(verify_bearer_token)):
    return _power(_get_vm(vm_id, user.uid), "shutdown")


@router.post("/{vm_id}/reboot")
def reboot_vm(vm_id: str, user: AuthenticatedUser = Depends(verify_bearer_token)):
    return _power(_get_vm(vm_id, user.uid), "reboot")


@router.patch("/{vm_id}/specs")
def resize_vm(vm_id: str, body: VmSpecsIn,
              user: AuthenticatedUser = Depends(verify_bearer_token)):
    """Change the machine's Slices. Hypervisors only re-size virtual hardware
    while the guest is OFF, so this is rejected for running machines."""
    vm = _get_vm(vm_id, user.uid)
    s = _vm_session(vm)
    if _pve_status(s, vm["vmid"]) == "running":
        raise HTTPException(409, "Apaga la máquina para modificar sus Porciones.")
    _pve(s["ip"], f"/nodes/{s['pve_node']}/qemu/{vm['vmid']}/config",
         cookie=s["cookie"], csrf=s["csrf"],
         data={"cores": body.slices, "memory": body.slices * 1024})
    _vm_update(vm["id"], slices=body.slices,
               rate_cr_min=body.slices * RATE_CR_PER_SLICE_MIN, status="stopped")
    return _get_vm(vm_id, user.uid)


@router.delete("/{vm_id}", status_code=204)
def delete_vm(vm_id: str, user: AuthenticatedUser = Depends(verify_bearer_token)):
    vm = _get_vm(vm_id, user.uid)
    if vm["vmid"]:
        try:
            s = _vm_session(vm)
            if _pve_status(s, vm["vmid"]) == "running":
                _pve(s["ip"], f"/nodes/{s['pve_node']}/qemu/{vm['vmid']}/status/stop",
                     cookie=s["cookie"], csrf=s["csrf"], data={})
                deadline = time.time() + 20
                while time.time() < deadline and _pve_status(s, vm["vmid"]) != "stopped":
                    time.sleep(1.5)
            _pve(s["ip"], f"/nodes/{s['pve_node']}/qemu/{vm['vmid']}",
                 cookie=s["cookie"], csrf=s["csrf"], data=None, method="DELETE")
        except Exception:                   # noqa: BLE001 — row removal must win
            pass
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM vm WHERE id = %s::uuid", (vm_id,))
            conn.commit()
        finally:
            cur.close()
