# ═══════════════════════════════════════════════════════════════
# fte_sdk / logging.py
#
# PURPOSE: Centralized JSON logging. Sab agents structured JSON
#          format mein log karte hain — log aggregators (e.g.,
#          ELK, Datadog) easily parse kar sakte hain.
#
# USED BY: ALL — har agent aur backend setup_logging() call karega
# ═══════════════════════════════════════════════════════════════

import logging
import json
import sys
from datetime import datetime, timezone


def setup_logging(service_name: str, level: str = "INFO"):
    """Call once at agent startup — enables JSON logging to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service_name))
    logging.basicConfig(level=getattr(logging, level), handlers=[handler])


class JsonFormatter(logging.Formatter):
    """Formats log records as machine-parseable JSON lines."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        })
