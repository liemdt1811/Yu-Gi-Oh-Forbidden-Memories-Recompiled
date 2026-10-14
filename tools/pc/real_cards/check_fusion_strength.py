#!/usr/bin/env python3
"""List every fusion A + B = C whose result C is not stronger than a material.

    python tools/pc/real_cards/check_fusion_strength.py [--retail] [--via-base] [--md]

Reads the "z" mod's fusion rules (mods/z/mod.json). By default only the rules the mod itself
makes are checked; --retail also checks the disc's own table (notes/research/fusion-and-drop-tables/
fusions.csv, where a pair the mod has a rule for is replaced by it), --via-base also checks what a
card of the mod does by its base: a copy with no rule of its own fuses as its retail base, so a card
stronger than its base can meet a recipe that makes something weaker (the game stops that fusion,
see CardRules_Fusion, but the data is worth knowing).

A fusion is listed when the ATK of A or of B is greater than or equal to the ATK of C. The ATK is
the card's own printed one; a card whose ATK the mod prints as "?" (unknown_stats) is taken at the
strength targets.json gives it. Exits with 1 when something is listed.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import modio

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MOD = ROOT / "mods" / "z" / "mod.json"
CATALOG = ROOT / "notes" / "card-catalog.csv"
DISC = ROOT / "notes" / "research" / "fusion-and-drop-tables" / "fusions.csv"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--retail", action="store_true", help="also check the disc's own fusion table")
    ap.add_argument("--via-base", action="store_true", help="also check recipes a mod card meets by its retail base")
    ap.add_argument("--summary", action="store_true", help="count the listed fusions by result instead of listing them")
    ap.add_argument("--md", action="store_true", help="print a Markdown table")
    args = ap.parse_args()

    name, atk = {}, {}
    with open(CATALOG, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            name[int(r["id"])] = r["name"]
            if r["attack"]:
                atk[int(r["id"])] = int(r["attack"])
    mod = modio.load(MOD)
    real = {c["name"]: c["attack"] for c in json.loads((HERE / "targets.json").read_text(encoding="utf-8"))}
    base = {}
    for c in mod["cards"]:
        ref = f"{mod['id']}:{c['id']}:1"
        name[ref] = c["name"]
        if "attack" in c:
            atk[ref] = real.get(c["name"], c["attack"]) if c.get("unknown_stats") else c["attack"]
            base[ref] = c["copy"] if isinstance(c["copy"], int) else next(
                (i for i, n in name.items() if isinstance(i, int) and n == c["copy"]), None)

    rules = {}                                   # frozenset of the two materials -> result
    if args.retail:
        with open(DISC, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rules[frozenset((int(r["material_a_id"]), int(r["material_b_id"])))] = (int(r["result_id"]), "retail")
    for r in mod["fusions"]:
        if r["result"]:
            rules[frozenset(r["with"])] = (r["result"], "mod")
        else:
            rules.pop(frozenset(r["with"]), None)

    found = []

    def check(a, b, c, source):
        if a in atk and b in atk and c in atk and max(atk[a], atk[b]) >= atk[c]:
            found.append((a, b, c, source))

    for pair, (c, source) in rules.items():
        a, b = (tuple(pair) * 2)[:2]
        check(a, b, c, source)
    if args.via_base:
        explicit = set(rules)
        for ref, root in base.items():
            for pair, (c, source) in list(rules.items()):
                if root not in pair or source != "mod":
                    continue
                other = next(iter(pair - {root})) if len(pair) == 2 else root
                if frozenset((ref, other)) in explicit:
                    continue
                check(ref, other, c, "via base")

    found.sort(key=lambda x: (x[3], -max(atk[x[0]], atk[x[1]]) + atk[x[2]], name[x[2]]))
    total = len(found)
    if args.summary:
        count = {}
        for a, b, c, source in found:
            kind = "the result is one of its materials" if c in (a, b) else "a material is as strong or stronger"
            count[(name[c], atk[c], kind)] = count.get((name[c], atk[c], kind), 0) + 1
        for (result, strength, kind), n in sorted(count.items(), key=lambda x: -x[1]):
            print(f"{n:6}  {result} ({strength}): {kind}")
        found = []
    if args.md:
        print("| Materials | Result | Where |\n|---|---|---|")
    for a, b, c, source in found:
        left = f"{name[a]} ({atk[a]}) + {name[b]} ({atk[b]})"
        right = f"{name[c]} ({atk[c]})"
        print(f"| {left} | {right} | {source} |" if args.md else f"[{source:8}] {left} = {right}")
    checked = len(rules)
    print(f"\n{total} of {checked} rules checked make a card that is not stronger than a material.",
          file=sys.stderr if args.md else sys.stdout)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
