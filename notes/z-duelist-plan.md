# Z mod: plan to add the story's missing duelists

**Status:** Tier 1 (the original series) is built: Mako, Duke, Bonz, Espa Roba, Mokuba, Arkana, Panik, Yugi, Rishid, Marik, Yami Marik and Atemu (slots 40-51 in that order, Jaden moved to 60), with decks, drops, AI rows and an unlock chain (each needs the one before; Mako needs Jono 2nd; Marik has Ra only, Yami Marik all three Gods). They wear their base duelist's face until portraits are added. 13 cards were added to Z for them. Tier 2 is not started.

A plan, not done work. Nothing here is in `duelists.json` yet except Jaden Yuki.
The disc has 39 opponents (`notes/gameplay-tables.md`); about 14 are people from
the series and the rest are the game's own. This plan adds the series' other duelists,
each with a deck of the type they play.

**Confidence.** Decks are written from memory of the show and are not checked.
Each has a confidence mark (H/M/L). Step 0 below checks every one against a wiki
before anything is built. "Cards" counts are checked: they are how many of the
candidate cards the disc or the Z mod already has (`notes/card-catalog.csv`,
`targets.json`, `curated.json`, `spells.json`).

## What the mod system gives us (what a duelist is made of)

From `notes/more-duelists.md` and `tools/pc/real_cards/duelists.json`:

| Piece | How | Notes |
|---|---|---|
| Identity | `id`, `name`, `copy` (a retail duelist it builds on) | `copy` supplies portrait, deck, drops and AI until overridden |
| Place on the grid | `slot` 40-127 | 88 free places; none given means the lowest free one |
| Unlock | `unlock`: `beat` (a duelist), `wins`, `story`, `card` | all conditions must hold |
| Deck | `deck`: card -> weight, a **pool** (at least 14 distinct cards; 3 copies each at most) | weights are shares; a fixed 40-card deck is also possible |
| Drops | `drops`: `pow` (S/A POW), `tec` (S/A TEC), `bcd` | card -> weight, out of 2048 |
| AI | `ai`: 9 bytes (search depth, LP threshold, fusion depths...) or `copy` of a duelist's row | byte 0 (5-20) is the main difficulty dial |
| Score | `ranks`: 10 rules, each up to 5 `[threshold, change]` pairs | decides the S-D letter and so the drop pool |
| Face | `portrait_file` (a PNG beside the script) | the build copies it into the mod |

`build_real_cards.py` (`mod_duelists`) writes `id`, `copy`, `name`, `unlock`, `portrait`,
the deck and the drops. **It has to learn `slot`, `ai` and `ranks`** before step 3.

## Roster

Order below is also the order they unlock in (see Unlock chain). "Base" is the retail
duelist whose AI/portrait is copied until replaced.

### Tier 1: the original series (Duelist Kingdom, Battle City, Egypt)

| # | Duelist | Deck type | Signature cards (candidates) | Cards | Conf | Base |
|---|---|---|---|---|---|---|
| 1 | Yugi Muto | Spellcaster / Warrior "Magician" | Dark Magician, Dark Magician Girl, Summoned Skull, Gaia the Fierce Knight, Celtic Guardian, Kuriboh, Curse of Dragon, Black Luster Soldier, Buster Blader, Swords of Revealing Light, Exodia pieces | 11/12 (no Silent Swordsman) | H | Heishin 2nd |
| 2 | Mako Tsunami | Water: Fish, Sea Serpent, Aqua | Legendary Fisherman, Fortress Whale, Spike Seadra, Kairyu-shin, 7 Colored Fish, Aqua Madoor, Sea King Dragon, Giant Red Seasnake, Umi | 10/12 (no Legendary Fisherman, Mermaid Knight) | H | Seto |
| 3 | Duke Devlin | Dragon / Machine (dice and dragons) | Red-eyes B. Dragon, Black Skull Dragon, Dragon Master Knight, Cyber Commander, Gradius, Flame Swordsman, Dragon Piper, Big Eye | 7/12 (no Black Skull Dragon, Dark Sage, Parasite Paranoid; Red-Eyes is on the disc as "Red-eyes B. Dragon") | M | Mai Valentine |
| 4 | Bonz | Zombie | Dark Necrofear, Zombie Master, Armored Zombie, Pumpking the King of Ghosts, Vampire Lord, Ryu Kokki, Master Kyonshee, Dokurorider, Skull Servant | 9/12 (no Dark Necrofear, Zombie Master, Vampire Lord) | M | Weevil Underwood |
| 5 | Espa Roba | Mixed / psychic-style | Jirai Gumo, Pendulum Machine, Dark Elf, Beast of Talwar, Aqua Madoor, Mystic Clown | 8/12 (no Gil Garth, Hysteric Fairy, Spirit of the Pharaoh, Guardian Elma) | L | Rex Raptor |
| 6 | Mokuba Kaiba | Dragon / Machine (his brother's cards) | Blue-eyes White Dragon, Red-eyes B. Dragon, Gadget Soldier, Cyber Commander, Dragon Capture Jar, Battle Ox | 10/12 | L | Kaiba |
| 7 | Arkana | Spellcaster "Magician" | Dark Magician of Chaos, Magician of Black Chaos, Dark Magician, Dark Magician Girl, Illusionist Faceless Mage, Dark Elf, Skull Knight, Magical Ghost, Rogue Doll | 9/12 (no Dark Magician of Chaos, Silent Magician, Wall of Illusion) | M | Pegasus |
| 8 | Panik | Fiend / Dark | Dark Necrofear, Reaper of the Cards, Dark Gray, Doma The Angel of Silence, Dark Assailant, Mystic Clown, Fiend Reflection | 7/12 (no Dark Necrofear, Nightmare Wheel, Skull Dog Marron, Nightmare Steelcage, Fiend Reflection) | L | Bandit Keith |
| 9 | Marik Ishtar | Fiend / Spellcaster + the Egyptian Gods | The Winged Dragon of Ra, Slifer, Obelisk, Dark Necrofear, Fiend's Hand, Dark Magician, Magician of Black Chaos, Skull Knight, Judge Man | 9/12 (no Dark Necrofear, Gravekeeper's Servant, Mirage Dragon) | M | Nitemare |
| 10 | Rishid (Odion) | Gravekeeper (Spellcaster / Fiend) | Gravekeeper's Assailant, Guard, Spy, Servant, Necrovalley, Royal Tribute, Mystic Lamp, Reaper of the Cards, Dokurorider | 6/12 (no Gravekeeper's cards, Necrovalley, Royal Tribute) | M | Isis |

### Tier 2: Noah, the Orichalcos and the Waking of the Dragons

| # | Duelist | Deck type | Signature cards (candidates) | Cards | Conf | Base |
|---|---|---|---|---|---|---|
| 11 | Leon von Schroeder | Thunder / Dragon | Thunder Dragon, Twin-headed Thunder Dragon, Thunder Dragon Titan, Gagagigo, Kairyu-shin, Zaborg the Thunder Monarch, Spark Blaster | 8/12 (no Zaborg, Ancient Gear Golem, Spark Blaster, Thunder Nyan Nyan) | L | Mai Valentine |
| 12 | Zigfried von Schroeder | Machine / Cyber | Cyber Dragon, Cyber End Dragon, Cyber Twin Dragon, Cyber Commander, Machine King, Cyber Ogre, Fusionist | 11/12 (no Cyber Harpie Lady) | M | Kaiba |
| 13 | Noah Kaiba | Dragon / Machine (his stepfather's wealth) | Blue-eyes White Dragon, Blue-eyes Ultimate Dragon, Gaia the Dragon Champion, Machine King, Red-eyes B. Dragon | 10/12 | L | Seto 3rd |
| 14 | Dartz | Water / Dragon: Atlantis, the Orichalcos | Divine Dragon Ragnarok, Orichalcos Shunoros, Kyutora, Deuteros, Atlantean Dragoons, Legendary Atlantean Fish, Sea King Dragon, Leviathan, Poseidon | **3/12: this one needs a card set of its own** | M | Duel Master K |
| 15 | Raphael | Beast-Warrior / Gladiator | Gladiator Beast Heraklinos, Leogun, Beast King Barbaros, Chimera the Flying Mythical Beast, Garvas, Baby Dragon | 8/12 (no Gem-Knight Fusion, Winged Dragon Guardian of the Fortress #1, Gryphon Wing, Lord of D.) | L | Rex Raptor |
| 16 | Valon | Dragon / Warrior: Armed Dragon | Armed Dragon LV7 / LV5 / LV3, Alligator's Sword Dragon, Dark Blade, Flame Swordsman, Gearfried the Iron Knight | 6/12 (no LV5, LV3, Gearfried, Rocket Warrior, Armor Ninja) | M | Nitemare |
| 17 | Alister | Beast / Warrior | Gaia the Fierce Knight, Chimera the Illusion Beast, Beast King Barbaros, Dark Magician, Baby Dragon, Sphinx Teleia | 8/12 (no Mad Sword Beast, Iron Blacksmith Kotetsu, Gladiator Beast Augustus) | L | Heishin 2nd |

Not in this plan: Tristan Taylor, Gozaburo Kaiba, Lumis and Umbra, Strings, Ryo Bakura (the human
one: Yami Bakura is already on the disc), Jaden's GX classmates and the rest of GX. Each is
a candidate for a later pass; add them once step 0 confirms a deck and a face exist.

## Decks: how each is built

- **A pool of 24-30 cards** per duelist (Jaden has 26): the theme's core at weight 100-120,
  the stronger cards at 30-60, the signature boss at 20-40, a few Equip/Ritual cards at 30.
  The game needs 14 or more distinct cards.
- **Only cards that exist.** A deck uses disc cards and Z cards. Where a signature card is
  missing the first choice is a card the disc already has that plays the same part (a
  "Magician of Black Chaos" for "Dark Magician of Chaos"); a missing card is added to Z only when
  the deck is hollow without it.
- **Fusions must be real.** Each deck is run through `duelist_best_fusion.py --mod` to
  check what it can fuse into, so a deck's best fusion is a card of its theme.
- **Weight vs. ATK.** No duelist outside the last three tiers may hold a 3500+ ATK card
  in its pool. The boss is reached through fusion or a rare draw, as with the disc's own.

### Cards to add to Z

From the checks above, in the order they are needed (a card is added only if its duelist stays in the plan):

| For | Cards | How many |
|---|---|---|
| Panik, Marik, Bonz | Dark Necrofear, Zombie Master, Vampire Lord | 3 |
| Rishid | Gravekeeper's Assailant, Guard, Spy, Servant, Necrovalley, Royal Tribute | 6 |
| Valon | Armed Dragon LV5, LV3, Gearfried the Iron Knight, Armor Ninja | 4 |
| Dartz | Orichalcos Shunoros, Kyutora, Deuteros, Atlantean Dragoons, Legendary Atlantean Fish, Atlantean Heavy Infantry, Divine Dragon Ragnarok, Leviathan, Poseidon | 9 |
| Raphael, Alister | Gem-Knight Fusion, Gryphon Wing, Lord of D., Mad Sword Beast, Gladiator Beast Augustus, Iron Blacksmith Kotetsu | 6 |
| Arkana, Yugi | Dark Magician of Chaos, Silent Magician, Silent Swordsman, Wall of Illusion | 4 |
| Others | Mermaid Knight, Legendary Fisherman, Black Skull Dragon (Duke), Zaborg the Thunder Monarch | about 4 |

About **36** new cards, each from the YGOPRODeck data as every Z card is: stats from the data,
a description in the card's own words, and the fusion recipes by the Z rules (mass rules
where the card is a family, e.g. every Gravekeeper).

## AI, score and unlock

- **Difficulty tiers.** Byte 0 of `ai` (search depth): Tier 1 8-14, Tier 2 14-20. Marik and
  Dartz use `ai.copy` of Nitemare's row, the disc's hardest. Tier 1's weak duelists
  (Bonz, Espa Roba, Panik) keep their base's row.
- **Hand-made rules.** Marik (the three Gods), Rishid (Gravekeeper) and Dartz get their own
  `ai` rows; the others use `ai.copy` of a duelist of similar strength.
- **`ranks`.** Left as the disc's for Tier 1. Tier 2 is scored harder (turns: -40 past 20 turns, remaining LP: +12 at 8000) so
  a quick, clean win is what gives a S/A drop.
- **Unlock chain** (Jaden's is `beat: Jono 2nd`): Tier 1 opens one after another from Free Duel:
  Mako needs Jono 2nd; Marik has Ra only, Yami Marik all three Gods, Duke needs Mako, Bonz Duke and so on up to Marik (needs Panik)
  and Rishid (needs Marik); Tier 2 needs Seto 3rd and the one before it. The aim is a
  campaign-like order. The exact order is open (step 0 can reorder it).
- **Drops.** Each duelist drops its own deck's boss at weight 3-5 (S/A POW) and its
  tech cards at 6-10 (S/A TEC). Marik's drops include one of the Gods at weight 2.

## Faces

Portraits are 408x384 PNG (a card crop) beside the build script (`tools/pc/real_cards/portraits/`).
Art comes from the series' own pictures (the same way Jaden's did); the user supplies or approves the
source for each. A duelist with no picture yet wears its base's face until one is added.
Art is Konami's, not stored beyond what the repository already holds for Z.

## Work, in order

0. **Check** every deck and duelist against a wiki; fix the table above. Decide the roster
   (drop the L-confidence ones if a deck cannot be confirmed). *Output: the final table.*
1. **Builder.** Teach `mod_duelists` to write `slot`, `ai` and `ranks`; run `check`; add a
   check that every deck pool has at least 14 cards and every card name resolves.
2. **Cards.** Add the 36 cards to `targets.json` (`curated.json` for plain ones), with
   art (`build_real_cards.py art`) and recipes; keep each family's mass rule in one place.
3. **Duelists.** Fill `duelists.json` tier by tier, each: `id`, `name`, `copy`, `slot`, `unlock`,
   `ai`, `deck`, `drops`, face. Run the build and the fusion check after each tier.
4. **Faces.** Add a portrait per duelist as pictures are chosen.
5. **Notes.** Add the new rosters to `z-list.md` and
   `z-duelist-best-fusion.md` (regenerated by their scripts).
6. **Play-test.** For each duelist: it appears, unlocks as planned, its deck plays as its theme
   (not a pile), its best fusion is reachable, and the drop pools look right. This is done
   in the game, by you; the tools here only check the data.

## Size and risk

- **Data:** 17 duelists, about 36 cards, about 17 decks of 24-30 cards: large but mechanical.
- **The risk is accuracy, not code:** the decks. Step 0 is the guard, and the "Conf" column
  says where it matters most (Espa Roba, Mokuba, Noah, Panik, Leon, Raphael, Alister are
  the weakest).
- **Balance** is the other: new strong cards land in AI decks. A duelist whose AI plays its
  boss every game is a wall; the weights and the tier rules above are what keep it fair.
- **Not covered by tools here:** how a duelist feels to fight. Expect one tuning pass per tier
  after you have played it.
