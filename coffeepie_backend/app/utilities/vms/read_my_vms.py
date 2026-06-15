from app.crud.vms import list_vms as crud_list_vms
from app.models.vm_models import VMOut

async def read_my_vms(current_user):
    items = await crud_list_vms()
    user_id = str(current_user["_id"])
    my_vms = [v for v in items if v.get("ownerID") == user_id]
    return [VMOut(**v, id=str(v["_id"])) for v in my_vms]
