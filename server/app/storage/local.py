"""本地目录存储：根目录为 FILE_STORAGE_DIR。"""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """将 storage_key 映射到 root 下的相对路径；禁止跳出根目录。"""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    # 实现：解析并校验 storage_key → 绝对路径
    def path_for(self, storage_key: str) -> Path:
        key = (storage_key or "").strip().lstrip("/")
        if not key or ".." in Path(key).parts:
            raise ValidationFailedError("非法存储路径")
        path = (self._root / key).resolve()
        if not str(path).startswith(str(self._root)):
            raise ValidationFailedError("非法存储路径")
        return path

    def put(self, storage_key: str, content: bytes) -> None:
        dest = self.path_for(storage_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_bytes(content)
        except OSError as exc:
            if dest.exists():
                dest.unlink(missing_ok=True)
            raise ValidationFailedError("文件保存失败") from exc

    def read(self, storage_key: str) -> bytes:
        path = self.path_for(storage_key)
        if not path.is_file():
            raise NotFoundError("文件不存在")
        return path.read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self.path_for(storage_key)
        path.unlink(missing_ok=True)

    def exists(self, storage_key: str) -> bool:
        return self.path_for(storage_key).is_file()
