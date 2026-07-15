"""Browser streaming — broker a Proxmox VM's VNC console into the user's browser.

Two endpoints:
  POST /stream/session   (Big_Package tier only)
        Scheduler picks an available QFDM node, authenticates to its Proxmox
        with the stored (decrypted) root credentials, ensures the target VM is
        running, requests a short-lived VNC console ticket, and returns a
        session id + the RFB password for the browser's noVNC client.
  WS   /stream/vnc/{sid}
        Transparent byte relay between the browser noVNC websocket and
        Proxmox's vncwebsocket endpoint (the backend holds the auth cookie and
        talks TLS to the node; the browser only ever talks to us).

Why a backend relay: the browser cannot reach the node's Proxmox directly
(self-signed cert, cross-origin cookie, CORS). The orchestrator brokering the
console is exactly the OpenUDS/guacamole pattern, done here for Proxmox noVNC.

MVP scope, honestly labelled:
  * "closest node with space" scheduling is a stub over the single registered
    node (real ping/capacity ranking is future work);
  * target VM is chosen by STREAM_TARGET_VMID or a test-desktop name match, and
    is started if stopped — it deliberately avoids an already-running VM;
  * no COFP metering of the served minutes yet.
"""
from __future__ import annotations

import asyncio
import json
import os
import ssl
import time
import urllib.parse
import urllib.request
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket

from app.auth.identity import AuthenticatedUser
from app.auth.node_credentials import decrypt_password
from app.auth.rbac import verify_bearer_token
from app.db import get_conn

router = APIRouter(prefix="/stream", tags=["stream"])

# sid -> session dict. In-memory is fine for the MVP (single backend process);
# the Proxmox VNC ticket itself expires in ~30s so sessions are short-lived.
_SESSIONS: dict[str, dict] = {}
_SESSION_TTL = 120  # seconds the sid stays valid to open the relay ws


def _ssl_ctx() -> ssl.SSLContext:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE  # Proxmox nodes use self-signed certs
    return c


def _pve(ip, path, cookie=None, csrf=None, data=None, method=None):
    headers = {}
    if cookie:
        # Proxmox tickets must be sent RAW in the cookie (do not url-encode).
        headers["Cookie"] = "PVEAuthCookie=" + cookie
    if csrf:
        headers["CSRFPreventionToken"] = csrf
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(f"https://{ip}:8006/api2/json{path}", data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20, context=_ssl_ctx()) as r:
        return json.load(r).get("data")


def _authenticate(ip, user, pw):
    realm_user = user if "@" in (user or "") else f"{user}@pam"
    d = _pve(ip, "/access/ticket", data={"username": realm_user, "password": pw})
    return d["ticket"], d["CSRFPreventionToken"]


def _pick_node():
    """Scheduler stub: closest node with space. MVP = first active node that has
    stored root credentials. Note this spans ALL providers' nodes (the QFDM
    Network), not the caller's own — consumers stream from the network."""
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT name, host(public_ip), root_username, root_password_enc "
                "FROM node WHERE status = 'active' AND root_password_enc IS NOT NULL "
                "ORDER BY created_at LIMIT 1"
            )
            row = cur.fetchone()
        finally:
            cur.close()
    if not row:
        raise HTTPException(503, "No hay nodos disponibles en la Red QFDM.")
    name, ip, ruser, penc = row
    return {"name": name, "ip": ip, "user": ruser, "pw": decrypt_password(penc)}


def _select_vm(vms):
    """Pick the VM to stream. Env override, else a disposable test desktop by
    name, else the first stopped VM — never grabs an already-running VM blind."""
    want = os.getenv("STREAM_TARGET_VMID")
    if want:
        for v in vms:
            if str(v["vmid"]) == str(want):
                return v
    for kw in ("mint", "test", "temp", "desktop", "demo"):
        for v in vms:
            if kw in (v.get("name", "") or "").lower():
                return v
    stopped = [v for v in vms if v.get("status") != "running"]
    return (stopped or vms)[0] if vms else None


def _wait_running(ip, cookie, node, vmid, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = _pve(ip, f"/nodes/{node}/qemu/{vmid}/status/current", cookie=cookie)
        if st and st.get("status") == "running":
            return True
        time.sleep(1.5)
    return False


def _wait_task(ip, cookie, node, upid, timeout=60):
    """Poll a Proxmox task (UPID) until it finishes; return True on success."""
    deadline = time.time() + timeout
    q = urllib.parse.quote(upid, safe="")
    while time.time() < deadline:
        st = _pve(ip, f"/nodes/{node}/tasks/{q}/status", cookie=cookie)
        if st and st.get("status") == "stopped":
            return st.get("exitstatus") == "OK"
        time.sleep(1.5)
    return False


def _clone_template(ip, cookie, csrf, node, template_vmid, label):
    """Clone a template into a fresh throwaway VM (linked clone = fast). Returns
    the new vmid. The clone is destroyed when the session's relay closes."""
    newid = _pve(ip, "/cluster/nextid", cookie=cookie)
    upid = _pve(ip, f"/nodes/{node}/qemu/{template_vmid}/clone", cookie=cookie, csrf=csrf,
                data={"newid": newid, "name": label, "full": 0})
    if not _wait_task(ip, cookie, node, upid, timeout=90):
        raise HTTPException(502, "No se pudo clonar la plantilla del escritorio.")
    return int(newid)


def _destroy_vm(ip, cookie, csrf, node, vmid):
    """Best-effort stop + delete of a per-session clone (cleanup)."""
    try:
        _pve(ip, f"/nodes/{node}/qemu/{vmid}/status/stop", cookie=cookie, csrf=csrf, data={})
        for _ in range(15):
            st = _pve(ip, f"/nodes/{node}/qemu/{vmid}/status/current", cookie=cookie)
            if st and st.get("status") == "stopped":
                break
            time.sleep(1)
        _pve(ip, f"/nodes/{node}/qemu/{vmid}", cookie=cookie, csrf=csrf, data=None, method="DELETE")
    except Exception:
        pass


def _pick_owned_vm(vm_id: str, owner_uid: str):
    """Resolve a consumer-owned VM row → (node creds, proxmox vmid, name).
    Used when the panel streams a specific machine rather than a throwaway."""
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT v.proxmox_vmid, v.name, v.status, n.name, host(n.public_ip), "
                "       n.root_username, n.root_password_enc "
                "FROM vm v JOIN node n ON n.id = v.node_id "
                "WHERE v.id = %s::uuid AND v.owner_id = %s::uuid",
                (vm_id, owner_uid))
            row = cur.fetchone()
        finally:
            cur.close()
    if not row:
        raise HTTPException(404, "Máquina no encontrada.")
    pvmid, vname, vstatus, nname, ip, ruser, penc = row
    if not pvmid:
        raise HTTPException(409, "La máquina aún se está creando.")
    if not penc:
        raise HTTPException(503, "El nodo de esta máquina no está disponible.")
    node = {"name": nname, "ip": ip, "user": ruser, "pw": decrypt_password(penc)}
    return node, int(pvmid), vname


@router.post("/session")
def create_session(vm_id: str | None = None,
                   user: AuthenticatedUser = Depends(verify_bearer_token)):
    tier = str((user.claims.get("app_metadata") or {}).get("tier", "free")).lower()
    if tier != "big_package":
        raise HTTPException(403, "El acceso por navegador requiere el Paquete Grande.")

    sid = uuid.uuid4().hex

    if vm_id:
        # Stream one of the caller's OWN machines: never cloned, never
        # destroyed on disconnect — "Mantener Encendida" controls its power.
        node, pvmid, vname = _pick_owned_vm(vm_id, user.uid)
        cookie, csrf = _authenticate(node["ip"], node["user"], node["pw"])
        pve_node = _pve(node["ip"], "/nodes", cookie=cookie)[0]["node"]

        st = _pve(node["ip"], f"/nodes/{pve_node}/qemu/{pvmid}/status/current", cookie=cookie)
        if not st or st.get("status") != "running":
            _pve(node["ip"], f"/nodes/{pve_node}/qemu/{pvmid}/status/start",
                 cookie=cookie, csrf=csrf, data={})
            _wait_running(node["ip"], cookie, pve_node, pvmid)
        with get_conn() as conn:
            cur = conn.cursor()
            try:
                cur.execute("UPDATE vm SET status = 'running' WHERE id = %s::uuid", (vm_id,))
                conn.commit()
            finally:
                cur.close()

        vp = _pve(node["ip"], f"/nodes/{pve_node}/qemu/{pvmid}/vncproxy",
                  cookie=cookie, csrf=csrf, data={"websocket": 1})
        _SESSIONS[sid] = {
            "ip": node["ip"], "node": pve_node, "vmid": pvmid,
            "port": vp["port"], "vncticket": vp["ticket"], "cookie": cookie, "csrf": csrf,
            "is_clone": False, "exp": time.time() + _SESSION_TTL, "uid": user.uid,
        }
        return {"session_id": sid, "vnc_password": vp["ticket"],
                "node": node["name"], "vmid": pvmid, "vm_name": vname}

    node = _pick_node()
    cookie, csrf = _authenticate(node["ip"], node["user"], node["pw"])

    pve_node = _pve(node["ip"], "/nodes", cookie=cookie)[0]["node"]
    vms = _pve(node["ip"], f"/nodes/{pve_node}/qemu", cookie=cookie)
    target = _select_vm(vms)
    if not target:
        raise HTTPException(503, "El nodo no tiene máquinas virtuales disponibles.")

    is_clone = False
    vm_label = target.get("name")
    if target.get("template") == 1:
        # Golden template → clone a fresh throwaway VM for this session (VDI model).
        vmid = _clone_template(node["ip"], cookie, csrf, pve_node, target["vmid"], f"cp-{sid[:10]}")
        is_clone = True
    else:
        vmid = target["vmid"]

    st = _pve(node["ip"], f"/nodes/{pve_node}/qemu/{vmid}/status/current", cookie=cookie)
    if not st or st.get("status") != "running":
        _pve(node["ip"], f"/nodes/{pve_node}/qemu/{vmid}/status/start", cookie=cookie, csrf=csrf, data={})
        _wait_running(node["ip"], cookie, pve_node, vmid)

    vp = _pve(node["ip"], f"/nodes/{pve_node}/qemu/{vmid}/vncproxy",
              cookie=cookie, csrf=csrf, data={"websocket": 1})

    _SESSIONS[sid] = {
        "ip": node["ip"], "node": pve_node, "vmid": vmid,
        "port": vp["port"], "vncticket": vp["ticket"], "cookie": cookie, "csrf": csrf,
        "is_clone": is_clone, "exp": time.time() + _SESSION_TTL, "uid": user.uid,
    }
    return {
        "session_id": sid,
        "vnc_password": vp["ticket"],  # RFB password for noVNC
        "node": node["name"], "vmid": vmid, "vm_name": vm_label,
    }


@router.websocket("/vnc/{sid}")
async def vnc_relay(ws: WebSocket, sid: str):
    sess = _SESSIONS.get(sid)
    if not sess or sess["exp"] < time.time():
        await ws.close(code=4404)
        return
    # Only select a subprotocol the client actually offered — selecting one it
    # didn't (e.g. forcing "binary" when noVNC offers none) makes the browser
    # abort the handshake with 1006.
    offered = ws.scope.get("subprotocols") or []
    await ws.accept(subprotocol="binary" if "binary" in offered else None)

    import websockets

    url = (f"wss://{sess['ip']}:8006/api2/json/nodes/{sess['node']}/qemu/{sess['vmid']}"
           f"/vncwebsocket?port={sess['port']}&vncticket={urllib.parse.quote(sess['vncticket'], safe='')}")
    headers = {"Cookie": "PVEAuthCookie=" + sess["cookie"]}  # raw ticket

    try:
        async with websockets.connect(
            url, additional_headers=headers, subprotocols=["binary"],
            ssl=_ssl_ctx(), max_size=None, open_timeout=15,
        ) as pve:
            async def browser_to_pve():
                try:
                    while True:
                        await pve.send(await ws.receive_bytes())
                except Exception:
                    pass

            async def pve_to_browser():
                try:
                    async for msg in pve:
                        await ws.send_bytes(msg if isinstance(msg, (bytes, bytearray)) else msg.encode())
                except Exception:
                    pass

            # First task to finish (either side disconnecting) ends the session.
            done, pending = await asyncio.wait(
                {asyncio.create_task(browser_to_pve()), asyncio.create_task(pve_to_browser())},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
    except Exception:
        pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
        # Tear down the per-session clone so VMs don't accumulate on the node.
        _SESSIONS.pop(sid, None)
        if sess.get("is_clone"):
            await asyncio.to_thread(
                _destroy_vm, sess["ip"], sess["cookie"], sess["csrf"], sess["node"], sess["vmid"]
            )
