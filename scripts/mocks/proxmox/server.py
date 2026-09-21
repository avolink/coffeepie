"""Coffee Pie Proxmox Mock Server.
Responds to DC Agent API calls with fake but realistic data
so developers can test without a real Proxmox hypervisor.
"""
import os
import random
import time
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="Proxmox Mock", version="0.1.0")

MOCK_NODES = int(os.getenv("MOCK_NODES", "4"))
MOCK_VMS = int(os.getenv("MOCK_VMS_PER_NODE", "16"))
AUTH_TOKEN = os.getenv("MOCK_AUTH_TOKEN", "dev-agent-token")

node_names = [f"pve-{chr(65+i)}" for i in range(MOCK_NODES)]


def make_vm(node: str, vmid: int) -> dict:
    states = ["running", "running", "running", "stopped", "paused"]
    return {
        "vmid": vmid,
        "name": f"coffeepie-vm-{vmid:04d}",
        "status": random.choice(states),
        "node": node,
        "cpus": 4,
        "maxcpus": 8,
        "mem_mb": 4096,
        "maxmem_mb": 8192,
        "disk_gb": 40,
        "net_mbps": 100,
        "uptime_sec": random.randint(60, 86400 * 7),
        "template": random.choice(["debian-12-coffeepie", "win11-coffeepie"]),
    }


@app.get("/api2/json/nodes")
async def list_nodes(authorization: str = Header(None)):
    return {"data": [{"node": n, "status": "online"} for n in node_names]}


@app.get("/api2/json/nodes/{node}/qemu")
async def list_vms(node: str):
    if node not in node_names:
        raise HTTPException(404, "Node not found")
    return {"data": [make_vm(node, 100 + i) for i in range(MOCK_VMS)]}


@app.get("/api2/json/nodes/{node}/qemu/{vmid}/status/current")
async def vm_status(node: str, vmid: int):
    return {"data": make_vm(node, vmid)}


@app.post("/api2/json/nodes/{node}/qemu/{vmid}/status/start")
async def vm_start(node: str, vmid: int):
    return {"data": "UPID:pve:00000000:00000000:00000000:qmstart:0:root@pam:"}


@app.post("/api2/json/nodes/{node}/qemu/{vmid}/status/stop")
async def vm_stop(node: str, vmid: int):
    return {"data": "UPID:pve:00000000:00000000:00000000:qmstop:0:root@pam:"}


@app.post("/api2/json/nodes/{node}/qemu/{vmid}/status/reset")
async def vm_reset(node: str, vmid: int):
    return {"data": "UPID:pve:00000000:00000000:00000000:qmreset:0:root@pam:"}


@app.post("/api2/json/nodes/{node}/qemu")
async def create_vm(node: str):
    return {"data": f"UPID:pve:00000000:00000000:{random.randint(100000,999999)}:qmcreate:{random.randint(200,999)}:root@pam:"}


@app.delete("/api2/json/nodes/{node}/qemu/{vmid}")
async def delete_vm(node: str, vmid: int):
    return {"data": "UPID:pve:00000000:00000000:00000000:qmdestroy:0:root@pam:"}


@app.get("/health")
async def health():
    return {"status": "ok", "mock": True, "nodes": MOCK_NODES, "vms_per_node": MOCK_VMS}
