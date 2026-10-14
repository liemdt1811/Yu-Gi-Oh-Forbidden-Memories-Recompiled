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
"min_one" is the ATK at least one of them needs; a rule may name a middle card with "result" (a retail card, for a three-card combo), a group may also have "min_atk" for its own monsters, and "name_has" / "not_name_has" for a word in the name.
A card's "unknown_stats": true prints its ATK and DEF as 0 and keeps them out of the raised/lowered tint (an
effect gives the real ones); its "attack" and "defense" still say how strong a fusion treats it.
A card's "frame" is its mod "frame" colour (notes/more-cards.md#frame-colour).
A card's "effects" are its mod "monster_effects" (notes/more-cards.md#monster-effects); put them in its description too.
A target's "drop" ({"weight", "from": [opponents]}) puts it in those opponents' S/A rank prize pools.
spells.json holds Equip and Ritual cards (a copy of a retail one of the same kind; "equip":
"add"/"bonus"/"bonus_if"/"bonus_attack"/"bonus_defense" go to the mod's "equips", "ritual": "result" and
"tributes" to its "rituals"), with their own "drop".
duelists.json holds opponents with their own deck and prize pools (the mod's "duelists", "decks"
and "drops"; card names there become the mod's cards, other names the disc's), a "copy" base and
an "unlock"; "portrait_from" names a card whose art becomes its face, "portrait_file" an image beside this script (portraits/).
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

import modio

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MOD = ROOT / "mods" / "z"
CATALOG = ROOT / "notes" / "card-catalog.csv"
DISC = ROOT / "notes" / "research" / "fusion-and-drop-tables" / "fusions.csv"
DISC = ROOT / "notes" / "research" / "fusion-and-drop-tables" / "fusions.csv"
BY_RESULT = ROOT / "notes" / "research" / "fusion-and-drop-tables" / "fusions_by_result.csv"
CURATED = HERE / "curated.json"
TARGETS = HERE / "targets.json"
PACKS = HERE / "packs.json"
SPELLS = HERE / "spells.json"
DUELISTS = HERE / "duelists.json"
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
# The disc's 39 opponents a duelist may copy or be unlocked by (the ones this tool names).
# All 39 of the disc's opponents (notes/gameplay-tables.md): a duelist may copy one, be unlocked by one, or borrow its AI row.
OPPONENTS_ALL = OPPONENTS | {"Simon Muran", "Teana", "Jono", "Villager 1", "Villager 2", "Villager 3", "Seto", "Heishin",
                             "Rex Raptor", "Weevil Underwood", "Mai Valentine", "Bandit Keith", "Shadi", "Yami Bakura",
                             "Pegasus", "Isis", "Kaiba", "Mage Soldier", "Jono 2nd", "Seto 2nd", "Heishin 2nd", "Seto 3rd"}
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


def fetch_pack_image(url, dest):
    """A picture of a pack or its box from a URL, cut to what it shows: to the opaque part when it has a
    transparent background (kept so), else to what is not white."""
    from PIL import Image, ImageChops
    import io
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        img = Image.open(io.BytesIO(r.read()))
    if img.mode in ("RGBA", "LA", "P") and img.convert("RGBA").getchannel("A").getextrema()[0] < 255:
        img = img.convert("RGBA")
        box = img.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    else:
        img = img.convert("RGB")
        box = ImageChops.difference(img, Image.new("RGB", img.size, (255, 255, 255))).convert("L").point(
            lambda v: 255 if v > 24 else 0).getbbox()
    if box:
        img = img.crop(box)
    img.thumbnail((600, 600), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, optimize=True)


def fetch_set_image(code, dest):
    """A booster pack's picture from YGOPRODeck (images/sets/<code>.jpg), kept at its own size."""
    from PIL import Image
    import io
    req = urllib.request.Request(f"https://images.ygoprodeck.com/images/sets/{code}.jpg", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        img = Image.open(io.BytesIO(r.read())).convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, optimize=True)


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
    if PACKS.exists():
        for p in json.loads(PACKS.read_text(encoding="utf-8")):
            dest = MOD / "images" / "packs" / f"{p['id']}.png"
            if p.get("image_url") and not dest.exists():
                fetch_pack_image(p["image_url"], dest)
                print("art", f"packs/{dest.name}")
            elif p.get("set") and not dest.exists():
                fetch_set_image(p["set"], dest)
                print("art", f"packs/{dest.name}")
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
        if "effects" in c:
            e["monster_effects"] = c["effects"]
        if c.get("unknown_stats"):               # a rule gives its real ATK and DEF: it prints 0 and 0 (cards.h)
            e["unknown_stats"] = True
            e["attack"] = e["defense"] = 0       # "attack" here stays the strength fusions are built from
        if c.get("no_fusion"):                   # a god: fuses with no card, and Polymerization does not take it
            e["no_fusion"] = True
        if "copy_limit" in c:                    # a god: one in a deck
            e["copy_limit"] = c["copy_limit"]
        if "frame" in c:                         # "Orange" is an effect monster's, as in the card game
            e["frame"] = c["frame"]
        if (MOD / "images" / f"{cid}.png").exists():
            e["art"] = f"images/{cid}.png"
        entries.append(e)
        if target:
            inter.append({"ref": f"{MOD_ID}:{cid}:1", "name": c["name"], "type": c["type"], "attribute": c["attribute"].title(),
                          "atk": c["attack"], "base": base["id"], "level": c["level"]})
        if not target:
            (nodes if c in cards else extra).append({"ref": f"{MOD_ID}:{cid}:1", "name": c["name"], "type": c["type"],
                          "attribute": c["attribute"].title(), "atk": c["attack"], "base": base["id"], "level": c["level"]})
    spells = json.loads(SPELLS.read_text(encoding="utf-8"))
    equips, rituals = spell_cards(spells, cat, entries, cards + targets)
    mod = {"id": MOD_ID, "name": "Z", "version": "0.1",
           "author": "community", "enabled": False,
           "description": f"{len(entries)} real Yu-Gi-Oh! cards the disc lacks, with fusions. "
                          "Study project; art is Konami's.",
           "cards": entries, "drops": target_drops(targets + spells), "fusions": target_fusions(targets, cards, monsters, fusions(nodes, monsters, extra), nodes + extra, inter)}
    duelists = json.loads(DUELISTS.read_text(encoding="utf-8"))
    mod_duelists(mod, duelists, cards + targets + spells)
    packs = mod_packs(monsters, cards, targets, spells)
    if packs:
        mod["packs"] = packs
    if equips:
        mod["equips"] = equips
    if rituals:
        mod["rituals"] = rituals
    MOD.mkdir(parents=True, exist_ok=True)
    # "drops" and "decks" are files of the mod's (tables.c read_pools): the manifest names them
    for key in ("drops", "decks", "packs"):
        if key not in mod:
            continue
        (MOD / f"{key}.json").write_text(json.dumps(mod[key], indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
        mod[key] = f"{key}.json"
    (MOD / "mod.json").write_text(json.dumps(mod, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"{len(entries)} cards, {len(mod['fusions'])} fusions -> {MOD / 'mod.json'}")


def pack_pool(pack, tier, monsters, cards, targets, spells):
    """The cards one tier of a themed pack deals: the disc's monsters and the mod's whose type or name the pack
    names, within the tier's ATK. A card that fuses with nothing (the gods) or has no drop (made by a ritual)
    is not in one; a pack's "rare_extra" spell cards are in its rare tier."""
    def fits(name, kind, atk):
        return (tier.get("min_atk", 0) <= atk <= tier.get("max_atk", 4000)
                and (kind in pack["type"] or any(w in name for w in pack["names"])))
    pool = {}
    for m in monsters:
        if fits(m["name"], m["type"], m["atk"]):
            pool[m["name"]] = 1
    for c in cards + targets:
        if c.get("no_fusion") or ("fusions" in c and not c.get("drop")):
            continue
        if fits(c["name"], c["type"], c["attack"]):
            pool[f"{MOD_ID}:{slug(c['name'])}:1"] = 1
    if tier["id"] == "rare":
        for name in pack.get("rare_extra", []):
            pool[f"{MOD_ID}:{slug(name)}:1"] = 1
    return pool


def game_name(card, cards, targets, spells):
    """A card as the packs name it (the disc's name, or the mod card's) as its name."""
    if not card.startswith(f"{MOD_ID}:"):
        return card
    for c in cards + targets + spells:
        if f"{MOD_ID}:{slug(c['name'])}:1" == card:
            return c["name"]
    return card


def set_pack(pack, monsters, cat, cards, targets, spells):
    """A pack made from a real set's card list (sets/*.json: code, name, rarity): the cards the disc or the mod has,
    in tiers by rarity, as the set's pack dealt them (a slot of the rarest cards last). Returns the pack's tiers
    and slots, and the names of the set's cards that are in neither."""
    norm = lambda text: re.sub(r"[^a-z0-9]", "", text.lower())
    alias = {norm(k): v for k, v in pack.get("aliases", {}).items()}
    game = {norm(r["name"]): r["name"] for r in cat}
    mine = {norm(c["name"]): f"{MOD_ID}:{slug(c['name'])}:1" for c in cards + targets + spells}
    tier_of = {"Common": "common", "Short Print": "common", "Super Short Print": "common", "Rare": "rare",
               "Super Rare": "super", "Ultra Rare": "ultra", "Secret Rare": "secret"}
    weight = {"Common": 4, "Short Print": 2, "Super Short Print": 1}
    pools, missing = {name: {} for name in ("common", "rare", "super", "ultra", "secret")}, []
    rarity_of, missing_lists = {}, []
    for code, name, rarity in json.loads((HERE / pack["set_list"]).read_text(encoding="utf-8")):
        key = norm(alias.get(norm(name), name))
        card = game.get(key) or mine.get(key)
        if not card:
            missing.append((code, name, rarity))
            continue
        pools[tier_of[rarity]][card] = pools[tier_of[rarity]].get(card, 0) + weight.get(rarity, 1)
        rarity_of[card] = rarity
    also = pack.get("also")
    if also:                 # cards beyond the set's list: a duelist's deck, or names; their rarity by ATK
        ladder = [("Common", 0)] + [(kind, floor) for floor, kind in also["rarity_by_atk"]]
        have = {c for pool in pools.values() for c in pool}
        by_id = {int(r["id"]): r for r in cat}
        extra = {}
        with open(ROOT / "notes" / "research" / "fusion-and-drop-tables" / "drops.csv", encoding="utf-8", newline="") as handle:
            for r in csv.DictReader(handle):
                if r["pool"] == "deck" and r["duelist"] in also.get("duelists", ()) and int(r["card_id"]) in by_id:
                    row = by_id[int(r["card_id"])]
                    extra[row["name"]] = int(row["attack"]) if row["attack"] else 0
        for row in cat:
            if row["name"] in also.get("cards", ()):
                extra[row["name"]] = int(row["attack"]) if row["attack"] else 0
            if any(w in row["name"] for w in also.get("names", ())) and row["attack"]:
                extra[row["name"]] = int(row["attack"])
        for c in cards + targets:
            if c["name"] in also.get("cards", ()):
                extra[f"{MOD_ID}:{slug(c['name'])}:1"] = c["attack"]
            if (any(w in c["name"] for w in also.get("names", ())) and not c.get("no_fusion")
                    and not ("fusions" in c and not c.get("drop"))):
                extra[f"{MOD_ID}:{slug(c['name'])}:1"] = c["attack"]
        for card, strength in extra.items():
            if card in have or strength > 4000:
                continue
            kind = [name for name, floor in ladder if strength >= floor][-1]
            tier = tier_of[kind]
            pools[tier][card] = pools[tier].get(card, 0) + weight.get(kind, 1)
            rarity_of[card] = kind
    listed = set()           # "lists": more sets' card lists; only the cards the pack lacks, at the list's rarity
    for source in (also or {}).get("lists", ()):
        have = {c for pool in pools.values() for c in pool}
        for code, name, rarity in json.loads((HERE / source).read_text(encoding="utf-8")):
            key = norm(alias.get(norm(name), name))
            card = game.get(key) or mine.get(key)
            if not card:
                missing_lists.append((code, name, rarity))
            elif card not in have:
                pools[tier_of[rarity]][card] = weight.get(rarity, 1)
                rarity_of[card] = rarity
                listed.add(card)
                have.add(card)
    # a rarity of the pack's own: its spell cards' ("spells_are"), then card by card ("rarity_overrides")
    kinds = {c["name"]: c["kind"] for c in spells}
    spell_type = {r["name"] for r in cat if r["type"] in ("Magic", "Trap", "Ritual", "Equip")}
    spell_ref = {f"{MOD_ID}:{slug(c['name'])}:1" for c in spells}
    named = {norm(k): v for k, v in pack.get("rarity_overrides", {}).items()}
    for card in list(rarity_of):
        label = game_name(card, cards, targets, spells)
        kind = named.get(norm(label)) or (pack.get("spells_are") if (card in spell_type or card in spell_ref)
                                          and card not in listed else None)
        if not kind or kind == rarity_of[card]:
            continue
        pools[tier_of[rarity_of[card]]].pop(card, None)
        pools[tier_of[kind]][card] = weight.get(kind, 1)
        rarity_of[card] = kind
    tiers = {}
    for name, entry in pack["tiers"].items():
        if pools[name]:
            tiers[name] = {**entry, "cards": pools[name]}
    last = {"tiers": {name: tiers[name]["odds"] for name in tiers if name != "common"}}
    return tiers, ["common"] * (pack["count"] - 1) + [last], missing + [(c, n, f"{r} (list)") for c, n, r in missing_lists]


def mod_packs(monsters, cards, targets, spells):
    """packs.json -> the mod's "packs": one themed pack each (disc cards and mod cards), 50 starchips, opened one
    at a time by beating a duelist, with the pack's own picture (images/packs, "set" in packs.json)."""
    if not PACKS.exists():
        return []
    out, cat = [], read_catalog()
    for p in json.loads(PACKS.read_text(encoding="utf-8")):
        tiers = {}
        if "set_list" in p:
            tiers, slots, missing = set_pack(p, monsters, cat, cards, targets, spells)
            print(f"pack {p['name']}: {sum(len(t['cards']) for t in tiers.values())} cards of the set; "
                  f"{len(missing)} not in the disc or the mod: " + ", ".join(f"{n} ({r})" for _, n, r in missing))
            pack = {k: p[k] for k in ("id", "name", "description", "price", "count") if k in p}
            pack.update({"tiers": tiers, "slots": slots, "unlock": {"beat": p["beat"]}, "locked": "shown"})
            if (MOD / "images" / "packs" / f"{p['id']}.png").exists():
                pack["image"] = f"images/packs/{p['id']}.png"
                pack["image_style"] = "full"
            out.append(pack)
            continue
        for t in p["tiers"]:
            entry = {"odds": t["odds"], "cards": pack_pool(p, t, monsters, cards, targets, spells)}
            for key in ("label", "color"):
                if key in t:
                    entry[key] = t[key]
            if entry["cards"]:
                tiers[t["id"]] = entry
        pack = {k: p[k] for k in ("id", "name", "description", "price", "count", "guarantee") if k in p}
        pack["tiers"] = tiers
        pack["unlock"] = {"beat": p["beat"]}
        pack["locked"] = "shown"
        if (MOD / "images" / "packs" / f"{p['id']}.png").exists():
            pack["image"] = f"images/packs/{p['id']}.png"
            pack["image_style"] = "full"
        out.append(pack)
    return out


def mod_duelists(mod, duelists, known):
    """duelists.json -> the mod's "duelists", "decks" and "drops" entries, and each portrait."""
    ref = {c["name"]: f"{MOD_ID}:{slug(c['name'])}:1" for c in known}
    name = lambda n: ref.get(n, n)
    mod["duelists"], mod["decks"] = [], {}
    for d in duelists:
        entry = {"id": d["id"], "copy": d["copy"], "name": d["name"]}
        for key in ("unlock", "slot", "ai", "ranks"):
            if key in d:
                entry[key] = d[key]
        if "portrait_file" in d or "portrait_from" in d:
            src = (HERE / d["portrait_file"] if "portrait_file" in d
                   else MOD / "images" / f"{slug(d['portrait_from'])}.png")
            if src.exists():
                (MOD / "portraits").mkdir(parents=True, exist_ok=True)
                (MOD / "portraits" / f"{d['id']}.png").write_bytes(src.read_bytes())
                entry["portrait"] = f"portraits/{d['id']}.png"
        mod["duelists"].append(entry)
        mod["decks"][d["id"]] = {"replace": True, **{name(c): w for c, w in d["deck"].items()}}
        mod["drops"][d["id"]] = {pool: {name(c): w for c, w in cards.items()} for pool, cards in d["drops"].items()}


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
            if s.get("fusion"):      # a Polymerization: two monsters of the field fuse by the fusion rules
                # "poly" on a target: three (or two) monsters of the field that Polymerization fuses into it directly
                recipes = [{"materials": [m if isinstance(m, (int, dict)) else ref.get(m, m) for m in mats], "result": ref[t["name"]]}
                           for t in monsters for mats in t.get("poly", [])]
                # "recipes" on the spell itself: the same for a retail result (names of retail cards)
                recipes += [{"materials": [m if isinstance(m, dict) else ref.get(m, m) for m in r["materials"]], "result": ref.get(r["result"], r["result"])}
                            for r in s.get("recipes", [])]
                rituals.append({"card": ref[s["name"]], "fusion": True, **({"recipes_only": True} if s.get("recipes_only") else {}),
                                **({"recipes": recipes} if recipes else {})})
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
    retail.update({r["name"]: r["id"] for r in read_catalog() if r["type"] == "Equip"})   # Metalmorph fuses with a monster

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
    mats = [{"key": m["id"], "base": m["id"], "name": m["name"], "type": m["type"], "attribute": m["attribute"], "atk": m["atk"],
             "level": int(m["level"])} for m in monsters] + [{"key": n["ref"], "base": n["base"], "name": n["name"], "type": n["type"],
                                   "attribute": n["attribute"], "atk": n["atk"],
                                   "level": n.get("level")} for n in list(pool) + list(inter)]
    for t in targets:
        for rule in t.get("mass", []):
            ga, gb = rule["groups"]
            # a result is stronger than both materials: never take a material as strong as the result,
            # nor the result itself
            strength = (next(m["atk"] for m in monsters if m["name"] == rule["result"]) if "result" in rule
                        else t["attack"])
            cap, floor = min(rule["max_atk"], strength - 10), rule.get("min_one", 0)

            def fits(m, g):
                for k, v in g.items():
                    if k == "name_has":
                        ok = v in m["name"]
                    elif k == "not_name_has":
                        ok = v not in m["name"]
                    elif k == "min_atk":
                        ok = m["atk"] >= v
                    else:
                        ok = m[k] == v
                    if not ok:
                        return False
                return True

            def pick(g):
                return [m for m in mats if m["atk"] <= cap and ("result" in rule or m["name"] != t["name"]) and fits(m, g)]

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
                    rules.append({"with": [a["key"], b["key"]], "result": card(rule["result"]) if "result" in rule else ref[t["name"]]})
    return rules


def check():
    mod = modio.load(MOD / "mod.json")
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
        if r.get("fusion"):
            if r["card"] not in ritual_cards:
                errors.append(f"rituals {r['card']}: card")
            continue
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
    cardrefs = set(refs) | {r["name"] for r in cat}
    for d in mod.get("duelists", []):
        if d["copy"] not in OPPONENTS_ALL:
            errors.append(f"duelist {d['id']}: copy {d['copy']!r}")
        added = {x["id"] for x in mod["duelists"]}
        if d.get("unlock", {}).get("beat") not in (None, *OPPONENTS_ALL, *added):
            errors.append(f"duelist {d['id']}: unlock {d['unlock']['beat']!r}")
        if "portrait" in d and not (MOD / d["portrait"]).exists():
            errors.append(f"duelist {d['id']}: portrait missing")
        deck = mod["decks"].get(d["id"], {})
        if len(deck) - ("replace" in deck) < 14:
            errors.append(f"duelist {d['id']}: deck needs 14 cards")
        for c, w in deck.items():
            if c != "replace" and (c not in cardrefs or not isinstance(w, int) or not 0 < w < 2048):
                errors.append(f"duelist {d['id']} deck: {c!r} {w!r}")
    for opponent, pools in mod.get("drops", {}).items():
        if opponent not in OPPONENTS and opponent not in {d["id"] for d in mod.get("duelists", [])}:
            errors.append(f"drops: no opponent {opponent!r}")
        for pool, cards in pools.items():
            if pool not in ("pow", "bcd", "tec"):
                errors.append(f"drops {opponent}: pool {pool!r}")
            for ref, weight in cards.items():
                if ref not in cardrefs or not isinstance(weight, int) or not 0 < weight < 2048:
                    errors.append(f"drops {opponent} {pool}: {ref!r} {weight!r}")
    pairs = set()
    for r in mod["fusions"]:
        a, b = r["with"]
        sa, sb, sr = stats(a), stats(b), stats(r["result"])
        if None in (sa, sb, sr) or sr < max(sa, sb):
            errors.append(f"fusion {a}+{b}->{r['result']}: unknown card or result weaker")
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
