"""Read the Z mod's manifest with its "drops" and "decks" as the tables they name (a file of the mod's, drops.json and decks.json)."""
import json
from pathlib import Path


def load(path):
    path = Path(path)
    mod = json.loads(path.read_text(encoding="utf-8"))
    for key in ("drops", "decks", "packs"):
        if isinstance(mod.get(key), str):
            mod[key] = json.loads((path.parent / mod[key]).read_text(encoding="utf-8"))
    return mod
