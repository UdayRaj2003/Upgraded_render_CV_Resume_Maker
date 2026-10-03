"""One structured log file per run. Never store prompts or intermediate JSON."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path


class RunLogger:
    def __init__(self, logs_dir: Path) -> None:
        logs_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        self.path = logs_dir / f"run_{stamp}.log"
        self._logger = logging.getLogger(f"resume_engine.{stamp}")
        self._logger.setLevel(logging.INFO)
        self._logger.handlers.clear()
        self._logger.propagate = False
        handler = logging.FileHandler(self.path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
        )
        self._logger.addHandler(handler)

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)

    def error(self, message: str) -> None:
        self._logger.error(message)

    def close(self) -> None:
        for handler in list(self._logger.handlers):
            handler.close()
            self._logger.removeHandler(handler)
