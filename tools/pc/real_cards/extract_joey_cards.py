#!/usr/bin/env python3
"""Extract the cards of "Joey the Passion - Card Lists.md" (a Yu-Gi-Oh! Power of Chaos - Joey the Passion card list by
vrapong) into one list per section:

    3.1 Normal Monster Cards   3.2 Effect Monster Cards   3.3 Fusion Monster Cards
    3.4 Ritual Monster Cards   3.5 Spell Cards            3.6 Trap Cards

Each card is "--Name-- [n/350]" followed by "Key: value" lines; a Description goes on over the indented lines under it.
Monsters have Level, Attribute, Type, Attack, Defense; a Spell or Trap card has Type (Normal, Equip, Continuous, ...).

    python tools/pc/real_cards/extract_joey_cards.py [--source FILE] [--json OUT.json] [--md OUT.md] [--equips]

--json writes {"3.1 Normal Monster Cards": [{"number": 3, "name": ..., ...}, ...], ...}; --md writes the lists as
Markdown (name and stats, one card a line, a section a heading); --equips prints the Equip spells with their text.
With neither --json nor --md, the section counts are printed.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "Joey the Passion - Card Lists.md"
SECTIONS = ["3.1 Normal Monster Cards", "3.2 Effect Monster Cards", "3.3 Fusion Monster Cards",
            "3.4 Ritual Monster Cards", "3.5 Spell Cards", "3.6 Trap Cards"]
NUMBERS = {"Level", "Attack", "Defense"}
CARD = re.compile(r"^--(.+?)-{1,2}\s*\[(\d+)/(\d+)\]\s*$")     # one card of the source (Lightning Conger) closes with one dash
FIELD = re.compile(r"^(Level|Attribute|Type|Attack|Defense|Description):\s*(.*)$")


def sections(lines):
    """Line ranges of the six sections: the heading at the start of a line, its dashes under it, the next heading
    (the table of contents at the top has them indented, so it never matches)."""
    starts = []
    for i, line in enumerate(lines):
        for name in SECTIONS:
            if line.rstrip() == name and i + 1 < len(lines) and lines[i + 1].startswith("---"):
                starts.append((name, i + 2))
    starts.append((None, len(lines)))
    for (name, begin), (_, end) in zip(starts, starts[1:]):
        # the next heading is preceded by a dashed line of its own
        while end > begin and (lines[end - 1].startswith("---") or not lines[end - 1].strip()):
            end -= 1
        yield name, lines[begin:end]


def cards(lines):
    card = None
    last = None
    for line in lines:
        m = CARD.match(line)
        if m:
            if card:
                yield card
            card = {"number": int(m.group(2)), "name": m.group(1).strip()}
            last = None
            continue
        if card is None:
            continue
        f = FIELD.match(line)
        if f:
            key, value = f.group(1), f.group(2).strip()
            card[key.lower()] = int(value) if key in NUMBERS and value.isdigit() else value
            last = key.lower()
        elif line.strip() and last == "description":
            card["description"] += " " + line.strip()
    if card:
        yield card


def extract(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    found = {name: list(cards(body)) for name, body in sections(lines)}
    missing = [name for name in SECTIONS if not found.get(name)]
    if missing:
        raise SystemExit(f"{path}: no cards found in {', '.join(missing)}")
    for rows in found.values():
        for card in rows:
            card["description"] = re.sub(r"\s+", " ", card.get("description", "")).strip()
    return found


def markdown(found):
    out = ["# Yu-Gi-Oh! Power of Chaos - Joey the Passion: cards", ""]
    for name in SECTIONS:
        rows = found[name]
        out += [f"## {name} ({len(rows)})", ""]
        for c in rows:
            if "attack" in c:
                out.append(f"- {c['name']} ({c.get('attribute', '?')} {c.get('type', '?')}, Lv{c.get('level', '?')}, "
                           f"{c['attack']}/{c.get('defense', '?')})")
            else:
                out.append(f"- {c['name']} ({c.get('type', '?')})")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", type=Path, default=SOURCE)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--md", type=Path)
    ap.add_argument("--equips", action="store_true", help="print the Equip spell cards with their text")
    args = ap.parse_args()
    found = extract(args.source)
    if args.json:
        args.json.write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.md:
        args.md.write_text(markdown(found), encoding="utf-8")
    if args.equips:
        equips = [c for c in found["3.5 Spell Cards"] if c.get("type", "").lower() == "equip"]
        print(f"{len(equips)} Equip cards")
        for c in equips:
            print(f"- {c['name']}: {c['description']}")
    if not (args.json or args.md or args.equips):
        for name in SECTIONS:
            print(f"{name}: {len(found[name])}")
        print(f"total: {sum(len(r) for r in found.values())}")
    types = {}
    for c in found["3.5 Spell Cards"]:
        types[c.get("type", "?")] = types.get(c.get("type", "?"), 0) + 1
    print("Spell types:", ", ".join(f"{k} {v}" for k, v in sorted(types.items())), file=sys.stderr)


if __name__ == "__main__":
    main()
