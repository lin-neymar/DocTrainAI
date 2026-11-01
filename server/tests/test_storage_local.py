"""LocalStorage 单元测试（不依赖 Postgres）。"""

from pathlib import Path

import pytest

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.storage.local import LocalStorage


def test_local_put_read_exists_delete(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    key = "2026/11/demo.md"
    storage.put(key, b"# hello\n")
    assert storage.exists(key)
    assert storage.read(key) == b"# hello\n"
    assert storage.path_for(key).is_file()
    storage.delete(key)
    assert not storage.exists(key)


def test_local_rejects_path_escape(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    with pytest.raises(ValidationFailedError):
        storage.path_for("../outside.txt")


def test_local_read_missing(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    with pytest.raises(NotFoundError):
        storage.read("missing/nope.pdf")
