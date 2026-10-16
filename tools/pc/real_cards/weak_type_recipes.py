#!/usr/bin/env python3
"""For every pair of types: which fusion recipes the weak monsters (ATK under --below, 1000 by default) have.

    python tools/pc/real_cards/weak_type_recipes.py [--below 1000 (99999 for every monster)] [--type Insect] [--md] [--retail]

A pair of monsters has a recipe when the "z" mod has a rule for it, else when the disc has one for
the pair (a copy of a disc monster fuses as its base). --retail leaves the mod out and reads the disc
alone. Prints, for each pair of types (a type with itself too): how many pairs of weak monsters
there are, how many have a recipe, and what they make (ATK, number of recipes), most often first;
then, for each type, how many of its weak monsters there are and with how many types it has any recipe.
A monster whose ATK the mod prints as "?" (unknown_stats) is left out, as are the gods.
"""
import argparse
import csv
import collections
import sys
from pathlib import Path

import modio

ROOT = Path(__file__).resolve().parents[3]
TABLES = ROOT / "notes" / "research" / "fusion-and-drop-tables"
NOT_MONSTERS = {"Magic", "Trap", "Equip", "Ritual"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--below", type=int, default=1000, help="a weak monster's ATK is under this (default 1000)")
    ap.add_argument("--type", help="only the pairs that include this type")
    ap.add_argument("--md", action="store_true", help="print Markdown tables")
    ap.add_argument("--retail", action="store_true", help="the disc's recipes alone, without the mod's cards and rules")
    args = ap.parse_args()

    cards = {}      # key -> (name, atk, type, base id)
    with open(ROOT / "notes" / "card-catalog.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["attack"] and r["type"] not in NOT_MONSTERS and r["attribute"]:
                cards[int(r["id"])] = (r["name"], int(r["attack"]), r["type"], int(r["id"]))
    disc = {}
    with open(TABLES / "fusions.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            disc[frozenset((int(r["material_a_id"]), int(r["material_b_id"])))] = int(r["result_id"])
    rules = {}
    if not args.retail:
        mod = modio.load(ROOT / "mods" / "z" / "mod.json")
        names = {v[0]: i for i, v in cards.items() if isinstance(i, int)}
        for c in mod["cards"]:
            if "attack" not in c or c.get("unknown_stats") or c["type"] in NOT_MONSTERS:
                continue
            base = c["copy"] if isinstance(c["copy"], int) else names.get(c["copy"])
            cards[f"{mod['id']}:{c['id']}:1"] = (c["name"], c["attack"], c["type"], base)
        for rule in mod["fusions"]:
            rules[frozenset(map(str, rule["with"]))] = rule["result"]

    def result_of(a, b):
        key = frozenset((str(a), str(b)))
        if key in rules:
            return rules[key], True
        base = frozenset((cards[a][3], cards[b][3]))
        return (disc.get(base), False) if None not in base else (None, False)

    def name_of(key):
        return cards[key][0] + f" ({cards[key][1]})" if key in cards else str(key)

    weak = [k for k, v in cards.items() if v[1] < args.below and v[1] >= 0]
    by_type = collections.defaultdict(list)
    for k in weak:
        by_type[cards[k][2]].append(k)
    types = sorted(by_type)
    rows = []
    reached = collections.defaultdict(set)
    for i, ta in enumerate(types):
        for tb in types[i:]:
            if args.type and args.type not in (ta, tb):
                continue
            total = made = from_mod = 0
            results = collections.Counter()
            for x, a in enumerate(by_type[ta]):
                for b in (by_type[tb][x + 1:] if ta == tb else by_type[tb]):
                    total += 1
                    res, new = result_of(a, b)
                    if res is not None:
                        made += 1
                        from_mod += new
                        results[name_of(res)] += 1
                        reached[ta].add(tb)
                        reached[tb].add(ta)
            rows.append((ta, tb, total, made, results, from_mod))

    def top(results, n=5):
        text = ", ".join(f"{name} x{count}" for name, count in sorted(results.items(), key=lambda kv: (-kv[1], kv[0]))[:n])
        return text + (f", and {len(results) - n} more" if len(results) > n else "")

    title = (f"Every monster ({len(cards)}): recipes by the types of the two materials" if args.below >= 99999 else
             f"Weak monsters (ATK under {args.below}): {len(weak)} of {len(cards)}; recipes by the types of the two materials")
    if args.md:
        print(f"# {title}\n")
        print("| Type + type | Pairs | With a recipe | Of them the mod's | Share | Makes |\n|---|---:|---:|---:|---:|---|")
        for ta, tb, total, made, results, from_mod in rows:
            print(f"| {ta} + {tb} | {total} | {made} | {from_mod} | {100 * made // max(total, 1)}% | {top(results) or '-'} |")
        print("\n| Type | Weak monsters | Types it has a recipe with |\n|---|---:|---|")
        for t in types:
            if not args.type or args.type == t or t in reached.get(args.type, ()):
                print(f"| {t} | {len(by_type[t])} | {len(reached[t])}: {', '.join(sorted(reached[t])) or '-'} |")
        return
    print(title)
    print(f"{'Type + type':<34}{'pairs':>6}{'recipes':>8}{'share':>7}  makes")
    for ta, tb, total, made, results, from_mod in rows:
        print(f"{ta + ' + ' + tb:<34}{total:>6}{made:>8}{100 * made // max(total, 1):>6}%  {top(results, 3)}")
    print()
    print(f"{'Type':<16}{'weak':>5}  types it has a recipe with")
    for t in types:
        if not args.type or args.type == t or t in reached.get(args.type, ()):
            print(f"{t:<16}{len(by_type[t]):>5}  {len(reached[t])}: {', '.join(sorted(reached[t])) or '-'}")


if __name__ == "__main__":
    main()
