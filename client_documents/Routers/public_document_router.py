from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from client_documents.Schemas.public_document_schema import PublicRequestView
from client_documents.Services import public_document_service as service
from client_documents.dependencies import upload_token_hash

router = APIRouter(prefix="/public/document-requests", tags=["Public Documents"])


def _no_store(payload):
    return JSONResponse(content=payload, headers={"Cache-Control": "no-store"})


@router.get("")
def read_request(auth=Depends(upload_token_hash)):
    token_hash, db = auth
    view = PublicRequestView.model_validate(service.public_view(db, token_hash))
    return _no_store(view.model_dump(mode="json"))


@router.post("/uploads")
async def upload(
    item_id: int = Form(...),
    file: UploadFile = File(...),
    auth=Depends(upload_token_hash),
):
    token_hash, db = auth
    return _no_store(await service.stage_upload(db, token_hash, item_id, file))


@router.post("/submit")
def submit(background_tasks: BackgroundTasks, auth=Depends(upload_token_hash)):
    token_hash, db = auth
    result = service.submit_request(db, token_hash)
    if result.get("email_job_id"):
        from Email.Services.email_task_service import process_email_job
        background_tasks.add_task(process_email_job, result["email_job_id"])
    return _no_store(result)
