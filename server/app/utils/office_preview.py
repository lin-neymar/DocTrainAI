"""Office 文档转 PDF（LibreOffice headless），供阶段 1 预览。

非 pip 依赖：本机需安装 LibreOffice / soffice。缺失时抛出明确业务错误。
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import settings
from app.core.exceptions import ValidationFailedError

logger = logging.getLogger(__name__)

OFFICE_EXTENSIONS = frozenset({"docx", "xlsx", "pptx"})

_CANDIDATE_BINS = (
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
    "/usr/local/bin/soffice",
)


# 实现：解析可用的 soffice 可执行文件路径
def resolve_soffice_bin() -> str | None:
    configured = (settings.libreoffice_path or "").strip()
    if configured:
        path = Path(configured)
        if path.is_file():
            return str(path)
        which = shutil.which(configured)
        if which:
            return which
        return None
    for candidate in _CANDIDATE_BINS:
        path = Path(candidate)
        if path.is_file():
            return str(path)
        which = shutil.which(candidate)
        if which:
            return which
    return None


# 实现：将 office 字节流转为 PDF 字节；失败 → 422 明确文案
def convert_office_to_pdf(*, content: bytes, ext: str) -> bytes:
    ext = ext.lower().lstrip(".")
    if ext not in OFFICE_EXTENSIONS:
        raise ValidationFailedError(f"不支持预览转换的类型: .{ext}")

    soffice = resolve_soffice_bin()
    if soffice is None:
        raise ValidationFailedError(
            "未检测到 LibreOffice，无法生成办公文档预览；请安装后重试，或先下载原件"
        )

    timeout = max(5, int(settings.libreoffice_timeout_seconds))
    with tempfile.TemporaryDirectory(prefix="dt_preview_") as tmp:
        tmp_path = Path(tmp)
        # 独立 UserInstallation，避免多进程抢同一 profile
        profile = tmp_path / "profile"
        profile.mkdir()
        src = tmp_path / f"input.{ext}"
        src.write_bytes(content)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        cmd = [
            soffice,
            "--headless",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(src),
        ]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValidationFailedError(
                f"文档预览转换超时（>{timeout}s），请稍后重试或下载原件"
            ) from exc

        pdf_path = out_dir / "input.pdf"
        if completed.returncode != 0 or not pdf_path.is_file():
            stderr = (completed.stderr or b"").decode("utf-8", errors="replace")[:500]
            logger.warning("libreoffice convert failed: code=%s %s", completed.returncode, stderr)
            raise ValidationFailedError("文档预览转换失败，请下载原件查看")
        return pdf_path.read_bytes()
