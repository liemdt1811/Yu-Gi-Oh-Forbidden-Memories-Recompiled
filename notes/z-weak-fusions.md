# Z mod: more fusions for the weak monsters

`build_real_cards.py` (`weak_fusions()`, set by `tools/pc/real_cards/weak_fusions.json`) gives every monster with
ATK under 1500 more fusion partners among the weak monsters of the type pairs `type_pairs` names, until `coverage`
(40%) of its possible pairs have a recipe. A pair that already has one (the disc's, a mod recipe, or a copy's retail base)
is left as it is, and two monsters of the same type never get one. Only the types the disc leaves short of partners are given
some: Insect, Beast-Warrior, Reptile, Pyro, Dinosaur and Sea Serpent, each with a few types that suit it.

| Key | Meaning |
|---|---|
| `weak_below` | a weak monster's ATK is under this (1500) |
| `min_atk`, `max_atk` | a new recipe makes a card of this ATK (1000 to 1800) |
| `min_gap` | and at least this much above both materials (100) |
| `type_pairs` | the pairs of types that get recipes (26): each of the six short types with a few partner types. Aqua, Warrior, Machine... and their pairs are left as the disc has them |
| `coverage` | the share of the other-type weak pairs each weak monster should have a recipe with (0.4) |
| `include` | retail monsters with no recipe on the disc (Beaver Warrior, Mountain Warrior) that are given some |
| `exclude` | monsters left alone |
| `fixed_results` | a pair of types whose card is named: `["Machine", "Pyro", "Robotic Knight"]` makes Robotic Knight whatever the other rules would pick |
| `result_exclude` | mod cards that are never a result |

Each pair of types has **one** result (Aqua + Beast always makes the same card), and it is always a card **this mod
adds** (not one of the disc's): the weakest of three of a type of the pair, within `min_atk` to `max_atk`, that is strong
enough (`min_gap` above both materials) for 4 in 5 of the pairs of those types still without a recipe; the three take
turns by type pair, so one card does not get every pair. A pair it is not strong enough for (two strong weak monsters) gets
no recipe. Monsters with the fewest partners go first, and a partner of the same attribute before another. A Level Up!
line's card (`LV` in its name) and the names in `result_exclude` are never a result.

To give a type more results, add cards for it to `targets.json` with `"fusions": []` and `"bridge": true`: a card
only a fusion makes. Add one only for a type pair that picks it (or name it in `fixed_results`): a bridge card that
no recipe makes cannot be had at all. The ones there now are Insect Knight, Blazewing Butterfly, Venom Boa, Molten
Zombie, Element Saurus and Rampaging Rhynos, and each is made by at least 46 recipes.

What it adds, by the types of the materials, is in [z-weak-fusions-list.md](z-weak-fusions-list.md), rewritten by each
`build`.

Checks: `check_fusion_strength.py` (a result is stronger than both materials), `duelist_best_fusion.py --mod`
(what a deck can reach), and the coverage line `build` prints (`weak fusions: ...`).
