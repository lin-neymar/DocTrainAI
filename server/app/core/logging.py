"""结构化日志基座（阶段 4）。

零新依赖：手写 text/json 两种 Formatter，由 LOG_FORMAT 决定（缺省随 APP_ENV 推导）。
- JsonFormatter：一行一条 JSON，含 ts/level/logger/message；request_id 来自 contextvar，
  步骤 4 中间件负责写入，业务日志无需手动传。
- TextFormatter：开发可读，同样附带 request_id 便于本地联调肉眼关联请求。
- setup_logging：幂等装配到 root，摘除 uvicorn 自带 handler 汇入同一输出；
  不触碰第三方（pytest 等）安装的 handler。
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# 当前请求的 request_id：阶段 4 中间件写入，formatter 读取；无请求上下文时保持 "-"
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# LogRecord 自带属性：extra 传入的自定义字段不在此列，将透传到 JSON
_RESERVED_ATTRS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName",
    }
)

TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] request_id=%(request_id)s %(message)s"


class JsonFormatter(logging.Formatter):
    """一行一条 JSON，供采集器直接解析。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id != "-":
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """开发可读格式；request_id 注入为普通格式字段。"""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get()
        return super().format(record)


def setup_logging(fmt: str) -> None:
    """幂等装配 root logger。

    只替换本模块自己加过的 handler（打 _doctrain 标记），不清理第三方 handler，
    因此 pytest 的日志捕获不受影响；uvicorn.* 摘除自带 handler 后汇入 root，
    启动日志与业务日志同格式单流输出。
    """
    resolved = fmt.strip().lower()
    if resolved not in {"text", "json"}:
        resolved = "text"
    formatter: logging.Formatter
    if resolved == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter(TEXT_FORMAT)

    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_doctrain", False):
            root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler._doctrain = True
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True