The eight themed packs (Dark Magician, Red-Eyes, Blue-Eyes, Gaia & Warriors, Harpies & Wings, Zombie Horde, Cyber Machines, Elemental Heroes), taken out of packs.json for now.
To bring them back: copy the entries of packs.json here into ../../packs.json and the art (images/) into mods/z/images/packs/, then run build_real_cards.py build.
Their pack art is ../../../../../mods/z/images/packs/<id>.png once restored (the 'set' key of each entry names the YGOPRODeck picture; build_real_cards.py art fetches it).
