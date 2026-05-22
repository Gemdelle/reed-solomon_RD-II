import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4


class FileStorage:
    def __init__(self, base_path: str):
        self._files = Path(base_path) / "files"
        self._meta = Path(base_path) / "meta"
        self._files.mkdir(parents=True, exist_ok=True)
        self._meta.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, filename: str = "") -> dict:
        file_id = str(uuid4())
        meta = {
            "file_id": file_id,
            "filename": filename or file_id,
            "sha256": sha256(data).hexdigest(),
            "size": len(data),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (self._files / file_id).write_bytes(data)
        (self._meta / f"{file_id}.json").write_text(json.dumps(meta))
        return meta

    def get_bytes(self, file_id: str) -> bytes | None:
        path = self._files / file_id
        return path.read_bytes() if path.exists() else None

    def get_meta(self, file_id: str) -> dict | None:
        path = self._meta / f"{file_id}.json"
        return json.loads(path.read_text()) if path.exists() else None

    def delete(self, file_id: str) -> bool:
        f = self._files / file_id
        if not f.exists():
            return False
        f.unlink()
        m = self._meta / f"{file_id}.json"
        if m.exists():
            m.unlink()
        return True

    def list_all(self) -> list[dict]:
        return [json.loads(p.read_text()) for p in self._meta.glob("*.json")]
