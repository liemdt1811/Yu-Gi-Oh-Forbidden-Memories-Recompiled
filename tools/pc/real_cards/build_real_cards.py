#!/usr/bin/env python3
"""Build the "real-cards" mod: real Yu-Gi-Oh! monsters the disc lacks.

    python tools/pc/real_cards/build_real_cards.py select   # API -> curated.json (100 cards)
    python tools/pc/real_cards/build_real_cards.py art      # download the art into mods/real-cards/images
    python tools/pc/real_cards/build_real_cards.py build    # curated.json -> mods/real-cards/mod.json
    python tools/pc/real_cards/build_real_cards.py check    # validate mod.json

Data comes from the YGOPRODeck API (https://ygoprodeck.com/api-guide/). Study
project; the art is Konami's and is fetched to the user's machine, not stored
in git (see .gitignore). notes/real-cards.md documents the mapping rules.
"""
import csv
import json
import re
import sys
import textwrap
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MOD = ROOT / "mods" / "real-cards"
CATALOG = ROOT / "notes" / "card-catalog.csv"
BY_RESULT = ROOT / "notes" / "research" / "fusion-and-drop-tables" / "fusions_by_result.csv"
CURATED = HERE / "curated.json"
API = "https://db.ygoprodeck.com/api/v7/cardinfo.php?type=Normal%20Monster&misc=yes"
UA = "fm-recomp-study/1.0"
MOD_ID = "real-cards"
COUNT = 100
MAX_ATK = 3000            # keeps new cards inside the disc's normal range
ERA_END = "2005"          # TCG release date before this
# Cards FM already has under a different spelling.
FM_ALIASES = ("fiendreflection", "trialofnightmare", "mechanicalchaser", "lajinnthemystical",
              "wingeddragonguardian", "twinlongrods", "redeyesblackdragon")
# Fixed Cards the game treats specially; never used as a base or a fusion partner.
SPECIAL_IDS = {17, 18, 19, 20, 21, 22, 777}

TYPES = {"Dragon", "Spellcaster", "Zombie", "Warrior", "Beast-Warrior", "Beast", "Winged Beast",
         "Fiend", "Fairy", "Insect", "Dinosaur", "Reptile", "Fish", "Sea Serpent", "Machine",
         "Thunder", "Aqua", "Pyro", "Rock", "Plant"}
TYPE_MAP = {"Psychic": "Spellcaster", "Wyrm": "Dragon", "Divine-Beast": "Fiend"}
FONT_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 !\"#$%&'()*+,-./:<>?")
FOLD = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
        "…": "...", "★": "*", "×": "x", "α": "A", "β": "B", "γ": "G",
        ";": ",", "é": "e", "ü": "u", "ö": "o"}


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def fold(text):
    text = "".join(FOLD.get(c, c) for c in text)
    return "".join(c if c in FONT_OK or c == "\n" else " " for c in text)


def slug(name):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def fm_type(race):
    race = TYPE_MAP.get(race, race)
    if race not in TYPES:
        raise SystemExit(f"unmapped race {race!r}: add it to TYPE_MAP")
    return race


def read_catalog():
    with open(CATALOG, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["id"] = int(r["id"])
        r["atk"] = int(r["attack"]) if r["attack"] else None
        r["def"] = int(r["defense"]) if r["defense"] else None
    return rows


def is_monster(r):
    return r["atk"] is not None and r["id"] not in SPECIAL_IDS and r["attribute"]


def description(desc):
    desc = re.sub(r"\s+", " ", desc.strip().strip("'\"").strip())
    desc = fold(desc)
    lines = textwrap.wrap(desc, 20, break_long_words=True)
    if len(lines) > 8:                       # cut at the last full sentence that fits
        fit = " ".join(lines[:8])
        cut = max(fit.rfind(". "), fit.rfind("! "), fit.rfind("? "))
        fit = fit[:cut + 1] if cut > 40 else fit.rsplit(" ", 1)[0] + "..."
        lines = textwrap.wrap(fit, 20, break_long_words=True)[:8]
    return "\n".join(lines)


def select():
    req = urllib.request.Request(API, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)["data"]
    have = {norm(c["name"]) for c in read_catalog()}
    pool = []
    for x in data:
        n = norm(x["name"])
        info = x["misc_info"][0]
        if (x["frameType"] != "normal" or n in have or any(a in n for a in FM_ALIASES)
                or "level" not in x or x["atk"] > MAX_ATK or (info.get("tcg_date") or "9") >= ERA_END
                or x["attribute"] in ("DIVINE",)):
            continue
        pool.append((info.get("views", 0), x))
    pool.sort(key=lambda p: -p[0])
    out = []
    for _, x in pool[:COUNT]:
        out.append({"password": f"{x['id']:08d}", "name": fold(x["name"]).strip(),
                    "type": fm_type(x["race"]), "attribute": x["attribute"].title(),
                    "level": x["level"], "attack": x["atk"], "defense": x["def"],
                    "description": description(x["desc"]), "date": x["misc_info"][0]["tcg_date"]})
    CURATED.write_text(json.dumps(out, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"{len(out)} cards -> {CURATED}")


def art():
    from PIL import Image
    import io
    out = MOD / "images"
    out.mkdir(parents=True, exist_ok=True)
    for c in json.loads(CURATED.read_text(encoding="utf-8")):
        dest = out / f"{slug(c['name'])}.png"
        if dest.exists():
            continue
        url = f"https://images.ygoprodeck.com/images/cards_cropped/{int(c['password'])}.jpg"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            img = Image.open(io.BytesIO(r.read())).convert("RGB")
        w, h = img.size                      # crop to the card picture's 102:96 shape, 4x = 408x384
        ch = min(h, int(w * 96 / 102))
        top = (h - ch) // 2
        img.crop((0, top, w, top + ch)).resize((408, 384), Image.LANCZOS).save(dest, optimize=True)
        print("art", dest.name)
        time.sleep(0.15)


def build():
    cat = read_catalog()
    monsters = [r for r in cat if is_monster(r)]
    cards = json.loads(CURATED.read_text(encoding="utf-8"))
    entries, nodes = [], []
    for c in cards:
        same = [m for m in monsters if m["type"] == c["type"] and m["atk"] <= MAX_ATK]
        base = min(same, key=lambda m: (abs(m["atk"] - c["attack"]) + abs(m["def"] - c["defense"])
                                        + 150 * abs(int(m["level"]) - c["level"]), m["id"]))
        cid = slug(c["name"])
        e = {"id": cid, "copy": base["id"], "name": c["name"], "description": c["description"],
             "type": c["type"], "attribute": c["attribute"], "level": c["level"],
             "attack": c["attack"], "defense": c["defense"], "password": c["password"],
             "drops": True, "opponents": True}
        if (MOD / "images" / f"{cid}.png").exists():
            e["art"] = f"images/{cid}.png"
        entries.append(e)
        nodes.append({"ref": f"{MOD_ID}:{cid}:1", "name": c["name"], "type": c["type"],
                      "attribute": c["attribute"].title(), "atk": c["attack"]})
    mod = {"id": MOD_ID, "name": "Real cards", "version": "0.1",
           "author": "community", "enabled": False,
           "description": f"{len(entries)} real Yu-Gi-Oh! monsters the disc lacks, with fusions. "
                          "Study project; art is Konami's.",
           "cards": entries, "fusions": fusions(nodes, monsters)}
    MOD.mkdir(parents=True, exist_ok=True)
    (MOD / "mod.json").write_text(json.dumps(mod, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"{len(entries)} cards, {len(mod['fusions'])} fusions -> {MOD / 'mod.json'}")


def fusions(new, monsters):
    """FM-style fusions: a result is always stronger than both materials.

    Partners of each new card: its 6 nearest-ATK retail monsters of the same
    type, 6 of the same attribute (other types) and 3 neighbours among the new
    cards. The result is the weakest obtainable fusion result that is at least
    200 ATK above both and shares a type or attribute with a material; ties
    rotate so one result does not take every recipe.
    """
    with open(BY_RESULT, encoding="utf-8", newline="") as f:
        result_ids = {int(r["result_id"]) for r in csv.DictReader(f)}
    results = sorted((m for m in monsters if m["id"] in result_ids), key=lambda m: (m["atk"], m["id"]))
    rules, seen = [], set()

    def add(a, b, pa, pb):
        need = max(pa["atk"], pb["atk"]) + 200
        ok = [r for r in results if r["atk"] >= need and r["id"] not in (a, b)
              and (r["type"] in (pa["type"], pb["type"]) or r["attribute"] in (pa["attribute"], pb["attribute"]))]
        if not ok:
            return
        low = [r for r in ok if r["atk"] <= ok[0]["atk"] + 300][:3]
        pick = low[(len(rules)) % len(low)]
        key = frozenset((str(a), str(b)))
        if key not in seen:
            seen.add(key)
            rules.append({"with": [a, b], "result": pick["id"]})

    for i, n in enumerate(new):
        pn = {"atk": n["atk"], "type": n["type"], "attribute": n["attribute"]}
        for pool in (lambda m: m["type"] == n["type"],
                     lambda m: m["attribute"] == n["attribute"] and m["type"] != n["type"]):
            for m in sorted((m for m in monsters if pool(m)), key=lambda m: (abs(m["atk"] - n["atk"]), m["id"]))[:6]:
                add(n["ref"], m["id"], pn, {"atk": m["atk"], "type": m["type"], "attribute": m["attribute"]})
        for k in (1, 2, 3):
            o = new[(i + k) % len(new)]
            add(n["ref"], o["ref"], pn, {"atk": o["atk"], "type": o["type"], "attribute": o["attribute"]})
    return rules


def check():
    mod = json.loads((MOD / "mod.json").read_text(encoding="utf-8"))
    cat = read_catalog()
    ids = {c["id"]: c for c in cat}
    passwords = {c["password"] for c in cat if c["password"]}
    errors, names = [], set()
    refs = {f"{MOD_ID}:{e['id']}:1": e for e in mod["cards"]}
    for e in mod["cards"]:
        where = e["id"]
        if len(e["id"]) > 63 or e["id"] in names:
            errors.append(f"{where}: id")
        names.add(e["id"])
        if e["copy"] not in ids or ids[e["copy"]]["atk"] is None:
            errors.append(f"{where}: base")
        if any(ch not in FONT_OK for ch in e["name"]):
            errors.append(f"{where}: name has characters the font lacks")
        if e["type"] not in TYPES or not 0 <= e["level"] <= 12:
            errors.append(f"{where}: type/level")
        for k in ("attack", "defense"):
            if not 0 <= e[k] <= 5110 or e[k] % 10:
                errors.append(f"{where}: {k}")
        lines = e["description"].split("\n")
        if len(lines) > 8 or any(len(x) > 20 for x in lines) or any(ch not in FONT_OK | {"\n"} for ch in e["description"]):
            errors.append(f"{where}: description")
        if e["password"] in passwords or not re.fullmatch(r"\d{8}", e["password"]):
            errors.append(f"{where}: password")
        passwords.add(e["password"])
        if "art" in e and not (MOD / e["art"]).exists():
            errors.append(f"{where}: art missing")
    def stats(x):
        if isinstance(x, int):
            return ids[x]["atk"] if x in ids else None
        return refs[x]["attack"] if x in refs else None
    pairs = set()
    for r in mod["fusions"]:
        a, b = r["with"]
        sa, sb, sr = stats(a), stats(b), stats(r["result"])
        if None in (sa, sb, sr) or sr <= max(sa, sb):
            errors.append(f"fusion {a}+{b}->{r['result']}: unknown card or result not stronger")
        key = frozenset((str(a), str(b)))
        if key in pairs:
            errors.append(f"fusion {a}+{b}: duplicate")
        pairs.add(key)
    print(f"{len(mod['cards'])} cards, {len(mod['fusions'])} fusions, {len(errors)} errors")
    for e in errors[:40]:
        print(" ", e)
    return 1 if errors else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"select": select, "art": art, "build": build, "check": check}.get(cmd)
    if not fn:
        raise SystemExit(__doc__)
    sys.exit(fn() or 0)
