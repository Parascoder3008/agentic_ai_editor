"""Machine settings: where things live on this computer, so no code has a machine path written into it.

Read from aie.local.json at the repo root (git-ignored; copy aie.local.example.json), or from the file named by the
AIE_LOCAL environment variable. Every key is optional and relative paths resolve against the repo root.
Job files refer to footage outside the repo as "@<root>/rest/of/path", where <root> is a name under "roots".
"""
import json
import os
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOCAL = "aie.local.json"
DEFAULTS = {
    "roots": {},
    "fonts": "fonts",
    "templates": "templates",
    "effects": "effects",
    "hyperframes": "hyperframes@0.8.111",
    "hyperframes_base": "aie/hyperframes_base",
    "avatar_rotation": "shorts/avatar_rotation.json",
    "video_use": None,
    "herk_kit": None,
}
PATH_KEYS = [k for k in DEFAULTS if k not in ("roots", "hyperframes")]


class SettingsError(ValueError):
    pass


@dataclass
class Settings:
    data: dict
    source: Path | None          # the file the settings came from, or None when only defaults apply

    def path(self, key: str) -> Path | None:
        v = self.data.get(key)
        if v is None:
            return None
        p = Path(v)
        return p if p.is_absolute() else REPO / p

    def resolve(self, ref: str, base: Path) -> Path:
        """A path from a job file: "@root/rest" -> that root, absolute -> as is, relative -> under base."""
        if ref.startswith("@"):
            name, _, rest = ref[1:].partition("/")
            roots = self.data["roots"]
            if name not in roots:
                where = self.source or REPO / LOCAL
                raise SettingsError(f'"{ref}": no root named "{name}" under "roots" in {where}')
            return Path(roots[name]) / rest
        p = Path(ref)
        return p if p.is_absolute() else base / p


def load_settings(path: str | Path | None = None) -> Settings:
    if path is None:
        path = os.environ.get("AIE_LOCAL") or REPO / LOCAL
    path = Path(path)
    if not path.exists():
        return Settings(dict(DEFAULTS, roots={}), None)
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SettingsError(f"{path}: not valid JSON ({e})") from None
    unknown = sorted(set(user) - set(DEFAULTS))
    if unknown:
        raise SettingsError(f"{path}: unknown keys {unknown}; allowed: {sorted(DEFAULTS)}")
    roots = user.get("roots", {})
    if not isinstance(roots, dict) or not all(isinstance(v, str) for v in roots.values()):
        raise SettingsError(f'{path}: "roots" must map names to folder paths')
    return Settings({**DEFAULTS, **user, "roots": roots}, path)
