"""Bridge Python logging into LangGraph's custom stream.

Attaches `LangGraphStreamHandler` to the `coursegen` parent logger so selected
`logger.info(...)` calls inside graph nodes are forwarded as `custom` stream
events. Filter: pass all `coursegen.agents.*`; from `coursegen.utils`, pass
only the `content_cleaner total …` summary line (cleaning result is useful to
see in the log panel, but per-section cleaner noise is dropped).
"""

from __future__ import annotations

import logging
import time

from langgraph.config import get_stream_writer

ROOT_LOGGER = "coursegen"
AGENT_PREFIX = "coursegen.agents."
CONTENT_CLEANER_LOGGER = "coursegen.utils.content_cleaner"
CONTENT_CLEANER_ALLOWED_PREFIX = "content_cleaner total"


class LangGraphStreamHandler(logging.Handler):
    """Forward selected log records to the active LangGraph stream writer."""

    def emit(self, record: logging.LogRecord) -> None:
        if not self._should_forward(record):
            return

        try:
            writer = get_stream_writer()
        except RuntimeError:
            return

        if writer is None:
            return

        try:
            writer(
                {
                    "kind": "log",
                    "logger": record.name,
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "ts": time.time(),
                }
            )
        except Exception:
            self.handleError(record)

    @staticmethod
    def _should_forward(record: logging.LogRecord) -> bool:
        if record.name.startswith(AGENT_PREFIX):
            return True
        if record.name == CONTENT_CLEANER_LOGGER:
            return record.getMessage().startswith(CONTENT_CLEANER_ALLOWED_PREFIX)
        return False


def install(level: int = logging.INFO) -> LangGraphStreamHandler:
    handler = LangGraphStreamHandler(level=level)
    logging.getLogger(ROOT_LOGGER).addHandler(handler)
    return handler


def uninstall(handler: LangGraphStreamHandler) -> None:
    logging.getLogger(ROOT_LOGGER).removeHandler(handler)
