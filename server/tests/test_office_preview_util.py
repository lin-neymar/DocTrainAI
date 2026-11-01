"""LibreOffice 探测与转换工具单测（不依赖本机是否安装）。"""

import pytest

from app.core.exceptions import ValidationFailedError
from app.utils import office_preview


def test_convert_without_soffice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(office_preview, "resolve_soffice_bin", lambda: None)
    with pytest.raises(ValidationFailedError, match="LibreOffice"):
        office_preview.convert_office_to_pdf(content=b"PK", ext="docx")
