"""上传文件校验与落盘（相对 FILE_STORAGE_DIR 的 storage_key）。

阶段 1：只校验扩展名 + 文件头 + 大小；不解析正文。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.core.exceptions import ValidationFailedError

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


# 实现：写入磁盘并返回 (storage_key, size_bytes, sha256)；失败时尽量清理半成品
def save_upload_bytes(*, content: bytes, ext: str) -> tuple[str, int, str]:
    assert_size_ok(len(content))
    assert_magic_matches(ext, content[:1024])

    storage_key = build_storage_key(ext)
    dest = settings.file_storage_path / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)

    sha = hashlib.sha256(content).hexdigest()
    try:
        dest.write_bytes(content)
    except OSError as exc:
        if dest.exists():
            dest.unlink(missing_ok=True)
        raise ValidationFailedError("文件保存失败") from exc

    return storage_key, len(content), sha


# 实现：把 storage_key 解析为绝对路径（禁止跳出存储根目录）
def resolve_stored_path(storage_key: str) -> Path:
    root = settings.file_storage_path.resolve()
    path = (root / storage_key).resolve()
    if not str(path).startswith(str(root)):
        raise ValidationFailedError("非法存储路径")
    return path
