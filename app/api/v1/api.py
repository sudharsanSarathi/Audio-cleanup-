from fastapi import APIRouter
from app.api.v1.endpoints import auth, files, processing

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(processing.router, prefix="/processing", tags=["processing"])