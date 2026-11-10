"""阶段 4：结构化日志基座测试（formatter 输出、request_id 透传、装配幂等）。"""

import json
import logging
import sys

from app.core.logging import (
    JsonFormatter,
    TextFormatter,
    job_id_var,
    request_id_var,
    setup_logging,
)


def _record(level: int, msg: str, args: tuple = (), exc_info=None) -> logging.LogRecord:
    return logging.LogRecord(
        name="app.test", level=level, pathname=__file__, lineno=1,
        msg=msg, args=args, exc_info=exc_info,
    )


def test_json_formatter_outputs_expected_fields() -> None:
    payload = json.loads(
        JsonFormatter().format(_record(logging.INFO, "上传完成 %s", ("a.pdf",)))
    )
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "上传完成 a.pdf"
    assert "+" in payload["ts"]  # UTC 毫秒时间戳
    assert "request_id" not in payload  # 无请求上下文时不输出


def test_json_formatter_attaches_request_id_and_extra() -> None:
    token = request_id_var.set("req-123")
    try:
        record = _record(logging.INFO, "解析开始")
        record.job_id = "job-9"  # 模拟业务 logger.info(..., extra={"job_id": ...})
        payload = json.loads(JsonFormatter().format(record))
        assert payload["request_id"] == "req-123"
        assert payload["job_id"] == "job-9"
    finally:
        request_id_var.reset(token)


def test_json_formatter_includes_exc_info() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record(logging.ERROR, "任务失败", exc_info=sys.exc_info())
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError" in payload["exc_info"]


def test_text_formatter_includes_request_id() -> None:
    token = request_id_var.set("req-77")
    try:
        line = TextFormatter(
            "%(levelname)s %(message)s request_id=%(request_id)s"
        ).format(_record(logging.INFO, "hello"))
        assert "request_id=req-77" in line
    finally:
        request_id_var.reset(token)


def test_setup_logging_idempotent() -> None:
    setup_logging("text")
    before = list(logging.getLogger().handlers)
    setup_logging("text")  # 重入：替换自家 handler，不新增也不清空第三方 handler
    after = list(logging.getLogger().handlers)
    assert len(after) == len(before)  # 第三方（pytest 等）handler 不受影响
    assert sum(1 for h in after if getattr(h, "_doctrain", False)) == 1  # 自家只有一份

def test_json_formatter_attaches_job_id() -> None:
    token = job_id_var.set("job-42")
    try:
        payload = json.loads(JsonFormatter().format(_record(logging.INFO, "解析中")))
        assert payload["job_id"] == "job-42"
    finally:
        job_id_var.reset(token)


def test_json_formatter_omits_job_id_when_unset() -> None:
    payload = json.loads(JsonFormatter().format(_record(logging.INFO, "无任务上下文")))
    assert "job_id" not in payload


def test_worker_settings_import_and_setup() -> None:
    """阶段 4：worker 入口可导入（结构化日志装配不炸），任务绑定不变。"""
    from app.workers.settings import WorkerSettings
    from app.workers.tasks import parse_document

    assert WorkerSettings.functions == [parse_document]