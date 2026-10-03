"""Journal des assets générés (VibeStarter/library.json), écrit de façon atomique."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class Library:
    def __init__(self, path: Path):
        self._path = path

    def all(self) -> dict[str, dict[str, Any]]:
        if not self._path.is_file():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def get(self, name: str) -> dict[str, Any] | None:
        return self.all().get(name)

    def put(self, name: str, entry: dict[str, Any]) -> None:
        data = self.all()
        data[name] = entry
        self._write(data)

    def update(self, name: str, **fields: Any) -> dict[str, Any]:
        data = self.all()
        entry = {**data.get(name, {}), **fields}
        data[name] = entry
        self._write(data)
        return entry

    def _write(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
            os.replace(tmp, self._path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
