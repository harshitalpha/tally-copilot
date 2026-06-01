"""Local filesystem adapter — used as ObjectStore in dev."""
import os, pathlib


class LocalFSStore:
    def __init__(self, base_path: str = "uploads/"):
        self.base = pathlib.Path(base_path).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> pathlib.Path:
        p = (self.base / key).resolve()
        # Don't allow escaping the base dir
        if not str(p).startswith(str(self.base)):
            raise ValueError("Invalid key")
        return p

    def upload(self, key: str, content: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

    def download(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def signed_url(self, key: str, ttl_seconds: int = 3600) -> str:
        # Local FS has no native signed URLs; just return the on-disk path.
        # The caller (documents.py GET /file) handles auth and streams the file.
        return str(self._path(key))

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def health_check(self) -> tuple[bool, str]:
        return self.base.exists(), str(self.base)
