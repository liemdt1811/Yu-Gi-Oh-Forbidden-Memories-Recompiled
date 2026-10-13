#!/usr/bin/env python3
"""Download card art by card name, in the size the game takes (408x384, 4x of 102x96).

    python tools/pc/real_cards/download_art.py "Dark Paladin" "Cyber End Dragon"
    python tools/pc/real_cards/download_art.py --file names.txt --force
    python tools/pc/real_cards/download_art.py --out some/dir "Blue-Eyes White Dragon"

Each picture is saved as <out>/<slug of the card's name>.png, the file name the
"z" mod looks for (default <out>: mods/z/images). A name must
match one card exactly (case ignored); otherwise the closest names are listed.
The art is Konami's and is fetched to your machine, not stored in git.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import build_real_cards as b

API = "https://db.ygoprodeck.com/api/v7/cardinfo.php?"


def lookup(query):
    req = urllib.request.Request(API + query, headers={"User-Agent": b.UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["data"]
    except urllib.error.HTTPError as e:
        if e.code == 400:                   # the API answers 400 for "no card found"
            return []
        raise


def find(name):
    """The one card called name, or None (the candidates are printed)."""
    cards = lookup("name=" + urllib.parse.quote(name))
    if cards:
        return cards[0]
    cards = lookup("fname=" + urllib.parse.quote(name))
    exact = [c for c in cards if c["name"].lower() == name.lower()]
    if exact:
        return exact[0]
    if len(cards) == 1:
        return cards[0]
    print(f"  {name!r}: " + ("no card with that name" if not cards else
          "which one? " + "; ".join(c["name"] for c in cards[:8])))
    return None


def main():
    ap = argparse.ArgumentParser(description="Download card art by name.")
    ap.add_argument("names", nargs="*", help="card names, as YGOPRODeck spells them")
    ap.add_argument("--file", help="a text file with one card name per line")
    ap.add_argument("--out", default=str(b.MOD / "images"), help="output directory")
    ap.add_argument("--force", action="store_true", help="download again over an existing file")
    args = ap.parse_args()
    names = list(args.names)
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            names += [x.strip() for x in f if x.strip() and not x.startswith("#")]
    if not names:
        ap.error("give at least one card name")
    out = b.Path(args.out)
    failed = 0
    for name in names:
        try:
            card = find(name)
            if not card:
                failed += 1
                continue
            dest = out / f"{b.slug(b.fold(card['name']))}.png"
            if dest.exists() and not args.force:
                print(f"  {card['name']}: {dest.name} exists (--force to replace)")
                continue
            b.fetch_art(card["id"], dest)
            print(f"  {card['name']} -> {dest}")
        except (urllib.error.URLError, OSError) as e:
            print(f"  {name!r}: {e}")
            failed += 1
        time.sleep(0.15)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
