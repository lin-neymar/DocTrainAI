"""上传文件校验与经 StorageBackend 落盘（storage_key）。

阶段 1：只校验扩展名 + 文件头 + 大小；不解析正文。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.core.exceptions import ValidationFailedError
from app.storage import get_storage, require_local_path

# PDF 魔数；md 无标准魔数，用「非 PDF + 非明显二进制」近似
_PDF_MAGIC = b"%PDF"


# 实现：从原始文件名取出小写扩展名（无点）；非法则 422
def extension_of(filename: str | None) -> str:
    if not filename or "." not in filename:
        raise ValidationFailedError("文件缺少扩展名")
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    if not ext:
        raise ValidationFailedError("文件缺少扩展名")
    if ext not in settings.allowed_extension_list:
        raise ValidationFailedError(f"不支持的文件类型: .{ext}")
    return ext


# 实现：按扩展名校验文件头，防止只改后缀绕过
def assert_magic_matches(ext: str, head: bytes) -> None:
    if ext == "pdf":
        if not head.startswith(_PDF_MAGIC):
            raise ValidationFailedError("文件内容不是合法 PDF")
        return
    if ext == "md":
        if head.startswith(_PDF_MAGIC):
            raise ValidationFailedError("Markdown 文件内容与扩展名不符")
        # 简单二进制探测：前 1KB 含 NUL 则拒绝
        sample = head[:1024]
        if b"\x00" in sample:
            raise ValidationFailedError("Markdown 文件不能为二进制内容")
        return
    raise ValidationFailedError(f"不支持的文件类型: .{ext}")


# 实现：校验大小不超过 FILE_MAX_MB
def assert_size_ok(size_bytes: int) -> None:
    max_bytes = settings.file_max_mb * 1024 * 1024
    if size_bytes <= 0:
        raise ValidationFailedError("文件为空")
    if size_bytes > max_bytes:
        raise ValidationFailedError(f"文件超过大小限制（{settings.file_max_mb}MB）")


# 实现：生成相对 storage_key（按月分子目录，避免单目录过大）
def build_storage_key(ext: str) -> str:
    now = datetime.now(timezone.utc)
    return f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}.{ext}"


# 实现：校验后经存储后端写入，返回 (storage_key, size_bytes, sha256)
def save_upload_bytes(*, content: bytes, ext: str) -> tuple[str, int, str]:
    assert_size_ok(len(content))
    assert_magic_matches(ext, content[:1024])

    storage_key = build_storage_key(ext)
    sha = hashlib.sha256(content).hexdigest()
    get_storage().put(storage_key, content)
    return storage_key, len(content), sha


# 实现：阶段 1 解析本地绝对路径（FileResponse / 兼容旧调用）
def resolve_stored_path(storage_key: str) -> Path:
    return require_local_path(storage_key)


# 实现：删除存储对象（DB 失败回滚时清理半成品等）
def delete_stored(storage_key: str) -> None:
    get_storage().delete(storage_key)
