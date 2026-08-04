from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_permission
from app.core.database import get_session
from app.models.admin import AdminUser
from app.providers.object_storage import (
    MediaFileTooLargeError,
    ObjectStorageNotConfiguredError,
    ObjectStorageProvider,
    UnsupportedMediaTypeError,
    get_object_storage,
)
from app.schemas.store_content import UploadTicketRequest, UploadTicketResponse
from app.services.upload_service import UploadService, UploadStoreNotFoundError

router = APIRouter(prefix="/media", tags=["admin-media"])
ContentManager = Annotated[
    AdminUser,
    Depends(require_permission("store_content:manage")),
]


@router.post(
    "/upload-tickets",
    response_model=UploadTicketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_upload_ticket(
    payload: UploadTicketRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[ObjectStorageProvider, Depends(get_object_storage)],
    current_admin: ContentManager,
) -> UploadTicketResponse:
    try:
        return await UploadService(session, storage).create_ticket(
            payload,
            current_admin,
        )
    except UploadStoreNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error
    except ObjectStorageNotConfiguredError as error:
        raise HTTPException(
            status_code=503,
            detail="对象存储尚未配置，无法上传媒体",
        ) from error
    except UnsupportedMediaTypeError as error:
        raise HTTPException(status_code=415, detail="不支持该媒体格式") from error
    except MediaFileTooLargeError as error:
        raise HTTPException(
            status_code=413,
            detail=f"文件超过 {error.max_size_bytes} 字节限制",
        ) from error
