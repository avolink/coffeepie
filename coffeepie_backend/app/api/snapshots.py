from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.utilities.vms.vms import ensure_vm_owned
from app.core.security import get_current_user
from app.models.snapshot_models import SnapshotCreate, SnapshotUpdate, SnapshotOut
from app.crud.snapshots import (
    create_snapshot as crud_create,
    get_snapshot as crud_get,
    list_snapshots as crud_list,
    update_snapshot as crud_update,
    delete_snapshot as crud_delete
)
from app.services.proxmox_service import (
    create_snapshot as prox_create_snapshot,
    list_snapshots as prox_list_snapshots,
    delete_snapshot as prox_delete_snapshot
)
from app.api.proxmox_routes import get_auth_headers
from app.crud.vms import get_vm as crud_get_vm
from datetime import datetime
import re

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

@router.post("/", response_model=SnapshotOut)
async def create_snapshot(snapshot: SnapshotCreate,current_user: dict = Depends(get_current_user)):
    data = snapshot.dict(exclude_unset=True)
    result = await crud_create(data)
    return SnapshotOut(**result, id=str(result["_id"]))

@router.get("/", response_model=List[SnapshotOut])
async def read_snapshots():
    items = await crud_list()
    return [SnapshotOut(**s, id=str(s["_id"])) for s in items]

@router.get("/{snapshot_id}", response_model=SnapshotOut)
async def read_snapshot(snapshot_id: str):
    s = await crud_get(snapshot_id)
    if not s:
        raise HTTPException(404, "Snapshot not found")
    return SnapshotOut(**s, id=str(s["_id"]))

@router.put("/{snapshot_id}", response_model=SnapshotOut)
async def update_snapshot(snapshot_id: str, snapshot: SnapshotUpdate):
    updated = await crud_update(snapshot_id, snapshot.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(404, "Snapshot not found or no changes")
    return SnapshotOut(**updated, id=str(updated["_id"]))

@router.delete("/{snapshot_id}")
async def delete_snapshot(snapshot_id: str):
    deleted = await crud_delete(snapshot_id)
    if not deleted:
        raise HTTPException(404, "Snapshot not found")
    return {"deleted": True}

@router.post("/Snapshot/create")
async def create_proxmox_snapshot(vm_id: str, description: str = "", current_user: dict = Depends(get_current_user), auth=Depends(get_auth_headers)):
    """Create a snapshot in Proxmox for a VM (only if user is owner)."""
    vm = await ensure_vm_owned(vm_id, current_user)
    vmid = vm["vmid"]
    node = vm["node"]
    # Generate snapshot name: {vmid}snapshot-{date}
    snapname = f"snap-{vmid}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
  
    # Proxmox: snapname must only have [A-Za-z0-9_-]
    snapname = re.sub(r"[^A-Za-z0-9_-]", "_", snapname)
    if description is None:
        description = ""
    # Check for existing snapshot names
    existing = prox_list_snapshots(node, vmid, auth["headers"], auth["cookies"])
    if any(s.get("name") == snapname for s in existing):
        raise HTTPException(status_code=400, detail=f"Snapshot name '{snapname}' already exists for this VM.")
    try:
        result = prox_create_snapshot(node, vmid, snapname, description, auth["headers"], auth["cookies"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Snapshot creation failed: {e}")
    return result

@router.get("/Snapshot/list")
async def list_proxmox_snapshots(node: str, vmid: int, current_user: dict = Depends(get_current_user), auth=Depends(get_auth_headers)):
    """List all snapshots for a VM in Proxmox (only if user is owner)."""
    await  ensure_vm_owned(vmid, current_user)
    result = prox_list_snapshots(node, vmid, auth["headers"], auth["cookies"])
    return result

@router.delete("/Snapshot/delete")
async def delete_proxmox_snapshot(node: str, vmid: int, snapname: str, current_user: dict = Depends(get_current_user), auth=Depends(get_auth_headers)):
    """Delete a snapshot in Proxmox for a VM (only if user is owner)."""
    await  ensure_vm_owned(vmid, current_user)
    result = prox_delete_snapshot(node, vmid, snapname, auth["headers"], auth["cookies"])
    return result
