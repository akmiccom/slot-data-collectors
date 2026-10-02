"""Small, offline PScube hall configuration loader."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "pscube.json"


@dataclass(frozen=True)
class PscubeHall:
    key: str
    name: str
    hall_code: str
    base_url: str

    def machine_list_url(self, cd_ps: int = 2) -> str:
        if type(cd_ps) is not int or cd_ps not in (1, 2):
            raise ValueError("cd_ps must be 1 or 2")
        return f"{self.base_url}cgi-bin/nc-v03-001.php?cd_ps={cd_ps}"


def load_halls(path: Path = DEFAULT_CONFIG) -> dict[str, PscubeHall]:
    """Read and validate all halls, indexed by their unique key."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("source") != "pscube":
        raise ValueError("Expected PScube configuration")
    rows = payload.get("halls")
    if not isinstance(rows, list):
        raise ValueError("halls must be a list")
    halls: dict[str, PscubeHall] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Hall must be an object")
        for field in ("key", "name", "hall_code", "base_url"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"Invalid hall field: {field}")
        if row["key"] in halls:
            raise ValueError("Duplicate hall key")
        url = row["base_url"]
        parts = urlsplit(url)
        # Keep the hall root canonical, without credentials or request parameters.
        if (parts.scheme not in ("http", "https") or not parts.hostname
                or parts.username is not None or parts.password is not None
                or parts.query or parts.fragment or parts.port is not None
                or any(c.isspace() or ord(c) < 32 for c in url) or "\\" in url
                or not re.fullmatch(r"[A-Za-z0-9.-]+", parts.hostname)
                or parts.path != f"/h/{row['hall_code']}/"
                or not re.fullmatch(r"[A-Za-z0-9_-]+", row["hall_code"])):
            raise ValueError("Invalid hall base_url")
        halls[row["key"]] = PscubeHall(**{field: row[field] for field in
                                        ("key", "name", "hall_code", "base_url")})
    return halls


def get_hall(key: str, path: Path = DEFAULT_CONFIG) -> PscubeHall:
    """Resolve a configured hall; unknown keys are configuration errors."""
    halls = load_halls(path)
    if key not in halls:
        raise ValueError("Unknown hall key")
    return halls[key]
