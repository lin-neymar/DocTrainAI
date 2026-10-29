"""F0：分页 Schema 与 offset 工具（不连库）。"""

import pytest
from pydantic import ValidationError

from app.schemas.common import PageQuery, page_data
from app.utils.pagination import page_offset


def test_page_query_defaults() -> None:
    q = PageQuery()
    assert q.page == 1
    assert q.page_size == 20


def test_page_query_rejects_oversized_page_size() -> None:
    with pytest.raises(ValidationError):
        PageQuery(page=1, page_size=101)


def test_page_query_rejects_page_zero() -> None:
    with pytest.raises(ValidationError):
        PageQuery(page=0, page_size=20)


def test_page_offset() -> None:
    assert page_offset(1, 20) == 0
    assert page_offset(2, 20) == 20
    assert page_offset(3, 10) == 20


def test_page_data_shape() -> None:
    body = page_data(items=[{"id": 1}], total=1, page=1, page_size=20)
    assert body == {
        "items": [{"id": 1}],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }
