#!/usr/bin/env python3
"""For every duelist: the strongest monster their deck can fuse into (and, for comparison,
the strongest card in the deck as it is).

    python tools/pc/real_cards/duelist_best_fusion.py [--mod] [--hand 5]

Takes each duelist's deck pool (the cards their deck is dealt from, with weights) and
closes it under the fusion table: a fusion of two cards costs the cards they cost
together, and only chains that fit in --hand cards (default 5, the starting hand) count.
Retail fusions come from notes/research/fusion-and-drop-tables/fusions.csv; --mod adds the
"z" mod's fusions (they replace a retail recipe for the same pair) and its duelists' decks.
Equips, rituals and the game's same-type fallbacks are not counted.
"""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TABLES = ROOT / "notes" / "research" / "fusion-and-drop-tables"
MOD = ROOT / "mods" / "z" / "mod.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mod", action="store_true", help="include the z mod's cards, fusions and duelists")
    ap.add_argument("--md", action="store_true", help="print a Markdown table instead of plain columns")
    ap.add_argument("--sort-atk", action="store_true", help="strongest first instead of the game's duelist order")
    ap.add_argument("--hand", type=int, default=5, help="most cards one fusion chain may use")
    args = ap.parse_args()

    cat = {}
    with open(ROOT / "notes" / "card-catalog.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["attack"]:
                cat[int(r["id"])] = (r["name"], int(r["attack"]))
    fuse = {}
    with open(TABLES / "fusions.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            fuse[frozenset((int(r["material_a_id"]), int(r["material_b_id"])))] = int(r["result_id"])

    decks = {}
    with open(TABLES / "drops.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["pool"] == "deck" and int(r["duelist_id"]) > 0:
                d = decks.setdefault(r["duelist"], {})
                d[int(r["card_id"])] = int(r["weight"])

    if args.mod:
        mod = json.loads(MOD.read_text(encoding="utf-8"))
        for c in mod["cards"]:
            if "attack" in c:
                cat[f"{mod['id']}:{c['id']}:1"] = (c["name"], c["attack"])
        for rule in mod["fusions"]:
            fuse[frozenset(rule["with"])] = rule["result"]
        names = {d["id"]: d["name"] for d in mod.get("duelists", [])}
        for did, deck in mod["decks"].items():
            # a non-replacing entry adds to the duelist's retail pool
            pool = {} if deck.get("replace") or names.get(did, did) not in decks else decks[names.get(did, did)]
            pool = dict(pool)
            for card, w in deck.items():
                if card != "replace":
                    pool[card] = w
            decks[names.get(did, did)] = pool

    by_card = {}
    for pair, res in fuse.items():
        for a in pair:
            by_card.setdefault(a, []).append((pair, res))

    rows = []
    for duelist, pool in decks.items():
        cost = {c: 1 for c in pool if c in cat}        # fewest cards a chain to this card needs
        how = {c: None for c in cost}
        changed = True
        while changed:
            changed = False
            for a in list(cost):
                for pair, res in by_card.get(a, ()):
                    b = next(iter(pair - {a})) if len(pair) == 2 else a
                    if b not in cost or res not in cat:
                        continue
                    n = cost[a] + cost[b]
                    if n <= args.hand and n < cost.get(res, 99):
                        cost[res], how[res] = n, (a, b)
                        changed = True

        def chain(c):
            if how[c] is None:
                return cat[c][0]
            return f"({chain(how[c][0])} + {chain(how[c][1])})"

        fused = [c for c in cost if cost[c] > 1]
        best = max(fused, key=lambda c: (cat[c][1], -cost[c])) if fused else None
        raw = max((c for c in cost if cost[c] == 1), key=lambda c: cat[c][1])
        rows.append((cat[best][1] if best else 0, duelist, cat[best][0] if best else "-", cost[best] if best else 0,
                     chain(best) if best else "", cat[raw][0], cat[raw][1]))

    if args.sort_atk:                       # rows are otherwise in the game's duelist order
        rows.sort(key=lambda r: (-r[0], r[1]))
    if args.md:
        print("| Duelist | Strongest fusion | ATK | Cards | Recipe | Strongest card in deck |")
        print("|---|---|---|---|---|---|")
        for atk, duelist, name, n, recipe, raw, rawatk in rows:
            print(f"| {duelist} | {name} | {atk} | {n} | {recipe or '-'} | {raw} ({rawatk}) |")
        return
    print(f"{'ATK':>5}  {'Duelist':<26} {'Strongest fusion':<36} cards  recipe  |  strongest card in deck")
    for atk, duelist, name, n, recipe, raw, rawatk in rows:
        print(f"{atk:>5}  {duelist:<26} {name:<36} {n:>5}  {recipe or '(none)'}  |  {raw} {rawatk}")


if __name__ == "__main__":
    main()
