"""存储后端工厂：阶段 1 仅 Local；S3 配置可预留但禁止在此实现。"""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorage


# 实现：按 STORAGE_BACKEND 返回后端；阶段 1 非 local 直接拒绝
def get_storage() -> StorageBackend:
    backend = (settings.storage_backend or "local").strip().lower()
    if backend in {"", "local"}:
        return LocalStorage(settings.file_storage_path)
    if backend in {"s3", "oss", "minio"}:
        raise RuntimeError(
            f"STORAGE_BACKEND={backend!r} 尚未实现；阶段 1 请使用 local"
        )
    raise RuntimeError(f"未知 STORAGE_BACKEND={backend!r}，阶段 1 仅支持 local")


# 实现：阶段 1 FileResponse 需要本地路径；非 Local 则拒绝
def require_local_path(storage_key: str) -> Path:
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise RuntimeError("当前存储后端不支持本地路径代下")
    return storage.path_for(storage_key)


__all__ = [
    "StorageBackend",
    "LocalStorage",
    "get_storage",
    "require_local_path",
]
