#!/usr/bin/env python3
"""Write notes/z-cards-packs.md: the Z mod's card packs, their cards by rarity and what unlocks them.

    python tools/pc/real_cards/list_packs.py

Reads mods/z/mod.json (and the packs.json it names), packs.json for the packs made from a real set's list
(sets/*.json: the set's own rarity of each card, and the cards the disc and the mod lack).
"""
import csv
import json
import re
from pathlib import Path

import modio

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "notes" / "z-cards-packs.md"


def norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def main():
    mod = modio.load(ROOT / "mods" / "z" / "mod.json")
    source = {p["id"]: p for p in json.loads((HERE / "packs.json").read_text(encoding="utf-8"))}
    atk, name = {}, {}
    with open(ROOT / "notes" / "card-catalog.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            name[r["name"]] = r["name"]
            if r["attack"]:
                atk[r["name"]] = int(r["attack"])
    for c in mod["cards"]:
        ref = f"{mod['id']}:{c['id']}:1"
        name[ref] = c["name"]
        if "attack" in c:
            atk[ref] = c["attack"]

    def label(card):
        text = name.get(card, card)
        return f"{text} ({atk[card]})" if card in atk else text

    out = ["# Z mod: card packs", "",
           f"{len(mod['packs'])} packs, sold on the Password screen behind the triangle button (`mods/z/packs.json`, made by "
           "`tools/pc/real_cards/list_packs.py` from `packs.json`). Every pack costs "
           f"{mod['packs'][0]['price']} starchips and opens when the save has beaten the duelist named under *Unlocks*; "
           "a locked pack is listed face down with its condition. ATK in brackets.", ""]
    for p in mod["packs"]:
        src = source.get(p["id"], {})
        out += [f"## {p['name']}", "", p.get("description", ""), "",
                f"- Price: {p['price']} starchips; {p['count']} cards",
                "- Unlocks: " + " or ".join(f"beat **{u['beat']}**" for u in (p["unlock"] if isinstance(p["unlock"], list) else [p["unlock"]]))]
        if "slots" in p:
            out.append(f"- Slots: {p['count'] - 1} of the common tier, then one by the odds " +
                       ", ".join(f"{t} {w / 10:g}%" for t, w in p["slots"][-1]["tiers"].items()))
        else:
            odds = {t: v["odds"] for t, v in p["tiers"].items()}
            out.append("- Each card by tier odds: " + ", ".join(f"{t} {w / 10:g}%" for t, w in odds.items()))
            if p.get("guarantee"):
                out.append("- Guarantee: " + ", ".join(f"at least {n} {t} or better" for t, n in p["guarantee"].items()))
        out.append("")
        rarity = {}
        if "set_list" in src:
            alias = {norm(k): v for k, v in src.get("aliases", {}).items()}
            for code, card, kind in json.loads((HERE / src["set_list"]).read_text(encoding="utf-8")):
                rarity[norm(alias.get(norm(card), card))] = kind
        for tier, entry in p["tiers"].items():
            cards = sorted(entry["cards"], key=lambda c: (-atk.get(c, -1), name.get(c, c)))
            title = entry.get("label", "").rstrip("!").title() or tier.title()
            out += [f"### {tier.title()} ({len(cards)} cards)", ""]
            for card in cards:
                kind = rarity.get(norm(name.get(card, card)))
                if "set_list" in src and tier != "common":     # the pack's own rarity may differ from the set's
                    kind = {"rare": "Rare", "super": "Super Rare", "ultra": "Ultra Rare", "secret": "Secret Rare"}[tier]
                elif "set_list" in src and not kind:
                    kind = "Common"
                out.append(f"- {label(card)}" + (f" - {kind}" if kind else ""))
            out.append("")
        if "set_list" in src:
            have = {norm(name.get(c, c)) for e in p["tiers"].values() for c in e["cards"]}
            alias = {norm(k): norm(v) for k, v in src.get("aliases", {}).items()}
            missing = [(card, kind) for _, card, kind in json.loads((HERE / src["set_list"]).read_text(encoding="utf-8"))
                       if alias.get(norm(card), norm(card)) not in have]
            out += [f"### Left out: not in the disc or the mod ({len(missing)})", ""]
            out += [f"- {card} - {kind}" for card, kind in missing] + [""]
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"{len(mod['packs'])} packs -> {OUT}")


if __name__ == "__main__":
    main()
