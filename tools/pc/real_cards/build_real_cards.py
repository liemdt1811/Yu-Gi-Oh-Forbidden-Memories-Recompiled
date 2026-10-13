#!/usr/bin/env python3
"""Build the "z" mod: real Yu-Gi-Oh! monsters the disc lacks.

    python tools/pc/real_cards/build_real_cards.py select   # API -> curated.json (100 cards)
    python tools/pc/real_cards/build_real_cards.py art      # download the art into mods/z/images
    python tools/pc/real_cards/build_real_cards.py build    # curated.json + targets.json -> mods/z/mod.json
    python tools/pc/real_cards/build_real_cards.py check    # validate mod.json

Data comes from the YGOPRODeck API (https://ygoprodeck.com/api-guide/). Study
project; the art is Konami's and is fetched to the user's machine, not stored
in git (see .gitignore). notes/real-cards.md documents the mapping rules.

targets.json is hand-written and `select` leaves it alone: stronger cards
(mostly 3000-4000 ATK) that only come from the fusion recipes listed with
each, so they never drop and no opponent deals them, and the materials those
recipes need that the disc lacks (an entry without "fusions", such as Cyber
Dragon), which are ordinary cards like curated.json's.
A target's "mass" rules ({"groups": [{type/attribute}, {type/attribute}], "max_atk", "min_one"}; a group may also name one card or an attribute alone) make it from
any two such monsters, as Twin-headed Thunder Dragon is on the disc. "max_atk" caps both materials and
"min_one" is the ATK at least one of them needs.
A target's "drop" ({"weight", "from": [opponents]}) puts it in those opponents' S/A rank prize pools.
spells.json holds Equip and Ritual cards (a copy of a retail one of the same kind; "equip":
"add"/"bonus"/"bonus_if"/"bonus_attack"/"bonus_defense" go to the mod's "equips", "ritual": "result" and
"tributes" to its "rituals"), with their own "drop".
A target's "steps" are recipes for a card made of three (Alpha + Beta + Gamma):
each [A, B, retail card] makes the card its "fusions" then take.
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
MOD = ROOT / "mods" / "z"
CATALOG = ROOT / "notes" / "card-catalog.csv"
DISC = ROOT / "notes" / "research" / "fusion-and-drop-tables" / "fusions.csv"
DISC = ROOT / "notes" / "research" / "fusion-and-drop-tables" / "fusions.csv"
BY_RESULT = ROOT / "notes" / "research" / "fusion-and-drop-tables" / "fusions_by_result.csv"
CURATED = HERE / "curated.json"
TARGETS = HERE / "targets.json"
SPELLS = HERE / "spells.json"
API = "https://db.ygoprodeck.com/api/v7/cardinfo.php?type=Normal%20Monster&misc=yes"
UA = "fm-recomp-study/1.0"
MOD_ID = "z"
COUNT = 100
MAX_ATK = 3000            # keeps new cards inside the disc's normal range
ERA_END = "2005"          # TCG release date before this
# Cards FM already has under a different spelling.
FM_ALIASES = ("fiendreflection", "trialofnightmare", "mechanicalchaser", "lajinnthemystical",
              "wingeddragonguardian", "twinlongrods", "redeyesblackdragon")
# Opponents a "drops" rule may name (notes/gameplay-tables.md lists all 39).
OPPONENTS = {"Teana 2nd", "Ocean Mage", "High Mage Secmeton", "Forest Mage", "High Mage Anubisius", "Mountain Mage",
             "High Mage Atenza", "Desert Mage", "High Mage Martis", "Meadow Mage", "High Mage Kepura", "Labyrinth Mage",
             "Seto 2nd", "Guardian Sebek", "Guardian Neku", "Heishin 2nd", "Seto 3rd", "DarkNite", "Nitemare", "Duel Master K"}
RITUAL_KEYS = {"card", "type", "fusion_group", "min_attack", "max_attack", "min_defense", "max_defense", "min_level",
               "max_level", "defense_gt_attack"}
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


def fetch_art(password, dest):
    """Download a card's picture from YGOPRODeck, cropped to the game's 102:96 shape at 4x (408x384)."""
    from PIL import Image
    import io
    url = f"https://images.ygoprodeck.com/images/cards_cropped/{int(password)}.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        img = Image.open(io.BytesIO(r.read())).convert("RGB")
    w, h = img.size
    ch = min(h, int(w * 96 / 102))
    top = (h - ch) // 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.crop((0, top, w, top + ch)).resize((408, 384), Image.LANCZOS).save(dest, optimize=True)


def art():
    out = MOD / "images"
    for c in (json.loads(CURATED.read_text(encoding="utf-8")) + json.loads(TARGETS.read_text(encoding="utf-8"))
              + json.loads(SPELLS.read_text(encoding="utf-8"))):
        dest = out / f"{slug(c['name'])}.png"
        if dest.exists():
            continue
        fetch_art(c["password"], dest)
        print("art", dest.name)
        time.sleep(0.15)


def build():
    cat = read_catalog()
    monsters = [r for r in cat if is_monster(r)]
    cards = json.loads(CURATED.read_text(encoding="utf-8"))
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))
    entries, nodes, extra, inter = [], [], [], []
    for c in cards + targets:
        target = "fusions" in c
        same = [m for m in monsters if m["type"] == c["type"] and m["atk"] <= MAX_ATK]
        base = min(same, key=lambda m: (abs(m["atk"] - c["attack"]) + abs(m["def"] - c["defense"])
                                        + 150 * abs(int(m["level"]) - c["level"]), m["id"]))
        cid = slug(c["name"])
        text = description(c["description"]) if c in targets else c["description"]
        e = {"id": cid, "copy": base["id"], "name": c["name"], "description": text,
             "type": c["type"], "attribute": c["attribute"], "level": c["level"],
             "attack": c["attack"], "defense": c["defense"], "password": c["password"],
             "drops": not target, "opponents": not target}
        if (MOD / "images" / f"{cid}.png").exists():
            e["art"] = f"images/{cid}.png"
        entries.append(e)
        if target:
            inter.append({"ref": f"{MOD_ID}:{cid}:1", "name": c["name"], "type": c["type"], "attribute": c["attribute"].title(),
                          "atk": c["attack"], "base": base["id"]})
        if not target:
            (nodes if c in cards else extra).append({"ref": f"{MOD_ID}:{cid}:1", "name": c["name"], "type": c["type"],
                          "attribute": c["attribute"].title(), "atk": c["attack"], "base": base["id"]})
    spells = json.loads(SPELLS.read_text(encoding="utf-8"))
    equips, rituals = spell_cards(spells, cat, entries, cards + targets)
    mod = {"id": MOD_ID, "name": "Z", "version": "0.1",
           "author": "community", "enabled": False,
           "description": f"{len(entries)} real Yu-Gi-Oh! cards the disc lacks, with fusions. "
                          "Study project; art is Konami's.",
           "cards": entries, "drops": target_drops(targets + spells), "fusions": target_fusions(targets, cards, monsters, fusions(nodes, monsters, extra), nodes + extra, inter)}
    if equips:
        mod["equips"] = equips
    if rituals:
        mod["rituals"] = rituals
    MOD.mkdir(parents=True, exist_ok=True)
    (MOD / "mod.json").write_text(json.dumps(mod, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"{len(entries)} cards, {len(mod['fusions'])} fusions -> {MOD / 'mod.json'}")


def spell_cards(spells, cat, entries, monsters):
    """spells.json -> card entries (a copy of a retail Equip / Ritual card) and the equips / rituals rules."""
    by_name = {r["name"]: r for r in cat}
    ref = {c["name"]: f"{MOD_ID}:{slug(c['name'])}:1" for c in monsters + spells}
    equips, rituals = [], []
    for s in spells:
        base = by_name[s["base"]]
        if base["type"] != s["kind"].title():
            raise SystemExit(f"spells.json: {s['name']}: base {s['base']!r} is a {base['type']}, not a {s['kind']}")
        cid = slug(s["name"])
        e = {"id": cid, "copy": base["id"], "name": s["name"], "description": description(s["description"]),
             "password": s["password"], "drops": False, "opponents": False}
        if (MOD / "images" / f"{cid}.png").exists():
            e["art"] = f"images/{cid}.png"
        entries.append(e)
        if s["kind"] == "equip":
            rule = {"card": ref[s["name"]], "replace": True, "add": s["add"]}
            for k in ("bonus", "bonus_if", "bonus_attack", "bonus_defense"):
                if k in s:
                    rule[k] = s[k]
            equips.append(rule)
        else:
            rituals.append({"card": ref[s["name"]], "result": ref[s["result"]], "tributes": s["tributes"]})
    return equips, rituals


def fusions(new, monsters, extra=()):
    """FM-style fusions: a result is always stronger than both materials.

    Partners of each new card: its 6 nearest-ATK retail monsters of the same
    type, 6 of the same attribute (other types) and 3 neighbours among the new
    cards (for targets.json's materials, the 3 new cards nearest in ATK, so
    curated.json's rules stay as they were). The result is the weakest obtainable fusion result that is at least
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

    for i, n in enumerate(list(new) + list(extra)):
        pn = {"atk": n["atk"], "type": n["type"], "attribute": n["attribute"]}
        for pool in (lambda m: m["type"] == n["type"],
                     lambda m: m["attribute"] == n["attribute"] and m["type"] != n["type"]):
            for m in sorted((m for m in monsters if pool(m)), key=lambda m: (abs(m["atk"] - n["atk"]), m["id"]))[:6]:
                add(n["ref"], m["id"], pn, {"atk": m["atk"], "type": m["type"], "attribute": m["attribute"]})
        near = ([new[(i + k) % len(new)] for k in (1, 2, 3)] if i < len(new) else
                sorted(new, key=lambda o: (abs(o["atk"] - n["atk"]), o["name"]))[:3])
        for o in near:
            add(n["ref"], o["ref"], pn, {"atk": o["atk"], "type": o["type"], "attribute": o["attribute"]})
    return rules


def target_drops(targets):
    """Prize pools: a target with {"drop": {"weight": W, "from": [opponents]}} is won, W in 2048,
    from each of those opponents on an S or A rank (POW and TEC); B, C and D ranks never give it."""
    drops = {}
    for t in targets:
        d = t.get("drop")
        if not d:
            continue
        for opponent in d["from"]:
            for pool in ("pow", "tec"):
                drops.setdefault(opponent, {}).setdefault(pool, {})[f"{MOD_ID}:{slug(t['name'])}:1"] = d["weight"]
    return drops


def target_fusions(targets, cards, monsters, rules, pool, inter=()):
    """Add targets.json's recipes; a recipe replaces a generated rule for the same pair.

    A target's "mass" rules are the disc's Twin-headed Thunder Dragon style: any
    monster of one group (type and/or attribute) with any of another, both up to
    "max_atk", makes the target. They only fill pairs that make nothing yet, on
    the disc (as the cards' bases) or in this mod, so no other recipe is lost,
    unless the rule says "override": true, which takes the pair over."""
    ref = {c["name"]: f"{MOD_ID}:{slug(c['name'])}:1" for c in cards + targets}
    retail = {m["name"]: m["id"] for m in monsters}

    def card(name):
        if name in ref:
            return ref[name]
        if name in retail:
            return retail[name]
        raise SystemExit(f"targets.json: unknown card {name!r}")

    own = []
    for t in targets:
        for a, b in t.get("fusions", []):
            own.append({"with": [card(a), card(b)], "result": ref[t["name"]]})
        for a, b, mid in t.get("steps", []):      # a three-card recipe: two fuse into a retail card first
            own.append({"with": [card(a), card(b)], "result": card(mid)})
    pairs = {frozenset(map(str, r["with"])) for r in own}
    rules = [r for r in rules if frozenset(map(str, r["with"])) not in pairs] + own
    taken = {frozenset(map(str, r["with"])) for r in rules}
    with open(DISC, encoding="utf-8", newline="") as f:
        disc = {frozenset((int(r["material_a_id"]), int(r["material_b_id"]))) for r in csv.DictReader(f)}
    mats = [{"key": m["id"], "base": m["id"], "name": m["name"], "type": m["type"], "attribute": m["attribute"], "atk": m["atk"]}
            for m in monsters] + [{"key": n["ref"], "base": n["base"], "name": n["name"], "type": n["type"],
                                   "attribute": n["attribute"], "atk": n["atk"]} for n in list(pool) + list(inter)]
    for t in targets:
        for rule in t.get("mass", []):
            ga, gb = rule["groups"]
            cap, floor = rule["max_atk"], rule.get("min_one", 0)

            def pick(g):
                return [m for m in mats if m["atk"] <= cap and all(m[k.lower()] == v for k, v in g.items())]

            for a in pick(ga):
                for b in pick(gb):
                    key = frozenset((str(a["key"]), str(b["key"])))
                    if max(a["atk"], b["atk"]) < floor:
                        continue
                    if key in pairs or not rule.get("override") and (key in taken or frozenset((a["base"], b["base"])) in disc):
                        continue
                    if key in taken:                 # "override": the pair's other recipe is replaced
                        rules = [r for r in rules if frozenset(map(str, r["with"])) != key]
                    taken.add(key)
                    rules.append({"with": [a["key"], b["key"]], "result": ref[t["name"]]})
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
        monster = "attack" in e
        kind = ids[e["copy"]]["type"] if e["copy"] in ids else None
        if kind is None or (monster and (kind not in TYPES or ids[e["copy"]]["atk"] is None))                 or (not monster and kind not in ("Equip", "Ritual")):
            errors.append(f"{where}: base")
        if any(ch not in FONT_OK for ch in e["name"]):
            errors.append(f"{where}: name has characters the font lacks")
        if monster and (e["type"] not in TYPES or not 0 <= e["level"] <= 12):
            errors.append(f"{where}: type/level")
        for k in ("attack", "defense"):
            if monster and (not 0 <= e[k] <= 5110 or e[k] % 10):
                errors.append(f"{where}: {k}")
        lines = e["description"].split("\n")
        if len(lines) > 8 or any(len(x) > 20 for x in lines) or any(ch not in FONT_OK | {"\n"} for ch in e["description"]):
            errors.append(f"{where}: description")
        if e["password"] in passwords or not re.fullmatch(r"\d{8}", e["password"]):
            errors.append(f"{where}: password")
        passwords.add(e["password"])
        if "art" in e and not (MOD / e["art"]).exists():
            errors.append(f"{where}: art missing")
    equip_cards = {f"{MOD_ID}:{e['id']}:1" for e in mod["cards"] if "attack" not in e and ids[e["copy"]]["type"] == "Equip"}
    ritual_cards = {f"{MOD_ID}:{e['id']}:1" for e in mod["cards"] if "attack" not in e and ids[e["copy"]]["type"] == "Ritual"}
    for r in mod.get("equips", []):
        if r["card"] not in equip_cards or not r.get("add") or any(t not in TYPES for t in r["add"]):
            errors.append(f"equips {r['card']}: card or types")
        if not any(k in r for k in ("bonus", "bonus_if", "bonus_attack", "bonus_defense")):
            errors.append(f"equips {r['card']}: no bonus")
    for r in mod.get("rituals", []):
        if r["card"] not in ritual_cards or r["result"] not in refs or "attack" not in refs[r["result"]]:
            errors.append(f"rituals {r['card']}: card or result")
        if len(r["tributes"]) != 3 or any(not t or set(t) - RITUAL_KEYS for t in r["tributes"]):
            errors.append(f"rituals {r['card']}: tributes")
        if any(t.get("type") not in TYPES for t in r["tributes"] if "type" in t):
            errors.append(f"rituals {r['card']}: tribute type")
    def stats(x):
        if isinstance(x, int):
            return ids[x]["atk"] if x in ids else None
        return refs[x]["attack"] if x in refs else None
    for opponent, pools in mod.get("drops", {}).items():
        if opponent not in OPPONENTS:
            errors.append(f"drops: no opponent {opponent!r}")
        for pool, cards in pools.items():
            if pool not in ("pow", "bcd", "tec"):
                errors.append(f"drops {opponent}: pool {pool!r}")
            for ref, weight in cards.items():
                if ref not in refs or not isinstance(weight, int) or not 0 < weight < 2048:
                    errors.append(f"drops {opponent} {pool}: {ref!r} {weight!r}")
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
