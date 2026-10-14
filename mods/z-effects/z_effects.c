/* The Z effects mod (mod.json beside this file; notes/modding.md): effects of
 * the Z mod's cards that "monster_effects" cannot say.
 *  - Buster Blader: +500 ATK for each face-up Dragon on the opponent's side.
 *  - Dark Magician Girl: +300 ATK for each Dark Magician or Magician of Black
 *    Chaos destroyed this duel, either side's.
 *  - Slifer the Sky Dragon: ATK and DEF are 1000 for each card in its owner's hand.
 *    A monster the other side summons face up in Attack Position while Slifer is face
 *    up on the field loses 2000 ATK for as long as it stays there, and one whose ATK
 *    would drop to 0 is destroyed (with Crush Card's removal, MonsterEffects_Destroy). Monsters already on the field when Slifer comes are not touched; the
 *    summon is remembered per duel record (state.weak, with the card's id so a record
 *    that is emptied and refilled cannot inherit it).
 *  - The Winged Dragon of Ra: ATK and DEF are its owner's life points.
 * Forbidden Memories has no graveyard, so Buster Blader has no "or in the
 * Graveyard" half, and Dark Magician Girl's "graveyard" is a count of those
 * two monsters when they are destroyed (MEMORIES_MONSTER_DESTROYED: in a battle or by
 * an effect; not as a fusion material or a tribute). The count starts at 0
 * with each duel (Duel_InitScene) and is kept in save states.
 *
 * It wraps Duel_CalcCardStats, which every ATK and DEF the duel, the battle,
 * the traps and the CPU read goes through, and adds to the attack half of the
 * word it returns (defense in the high 16 bits, attack in the low 16). The
 * duel's monster zones are records 5-9 of each side's 15 in D_801A7AD8, as
 * src/pc/cards/monster_effects_duel.c reads them. A card's type is bits 26-30
 * of gDuel_adwCardStats[card_id - 1]. */
#include "types.h"
#include "game/card_constants.h"
#include "game/duel_card.h"
#include "game/duel_init_scene.h"
#include "game/duel_side_state.h"
#include "game/duel_card_record_lifecycle.h"
#include "pc/cards/monster_effects_duel.h"
#include "pc/mods/modapi.h"

#define BUSTER_BLADER "z:buster-blader:1"
#define DARK_MAGICIAN_GIRL "z:dark-magician-girl:1"
#define SLIFER "z:slifer-the-sky-dragon:1"
#define RA "z:the-winged-dragon-of-ra:1"
#define DARK_MAGICIAN 35            /* the disc's own cards */
#define MAGICIAN_OF_BLACK_CHAOS 722
#define PER_DRAGON 500
#define PER_MAGICIAN 300
#define PER_HAND_CARD 1000
#define SLIFER_LOSS 2000
#define SIDE_RECORDS 15
#define FIRST_MONSTER 5
#define LAST_MONSTER 9

enum { BUSTER, GIRL, SLIFER_CARD, RA_CARD, CARDS };
static const char *const identity[CARDS] = {BUSTER_BLADER, DARK_MAGICIAN_GIRL, SLIFER, RA};

static const MemoriesModHost *host;
static s32 (*original)(DuelCardRecord *card);
static void (*original_init)(void);
static int id[CARDS];       /* the cards' ids this run, 0 until the tables are built */
static int logged[CARDS];
static struct { int destroyed; short weak[2 * SIDE_RECORDS]; } state;     /* in save states: Magicians destroyed this duel; the cards Slifer weakened, by record */

static int is_dragon(const DuelCardRecord *card)
{
    return ((gDuel_adwCardStats[card->card_id - 1] >> CARD_STAT_TYPE_SHIFT) & CARD_STAT_TYPE_MASK) == CARD_TYPE_DRAGON;
}

static int hand_cards(int side)
{
    int n = 0, i;
    for (i = 0; i < HAND_SIZE; i++)
        if (D_800E9FF0[side].hand[i] >= 0) n++;
    return n;
}

/* The card's ATK, past the printed one and the equips and terrain in `now`, or -1 when none of the
 * effects is this card's. Slifer's and Ra's number replaces the printed DEF as well (the caller). */
static int effect_attack(const DuelCardRecord *card, int record, int now, int *which, int *value)
{
    int side = record / SIDE_RECORDS, zone, n;

    *value = -1;

    for (*which = 0; *which < CARDS; (*which)++)
        if (id[*which] && card->card_id == id[*which]) break;
    if (*which == CARDS) return -1;
    switch (*which) {
    case BUSTER:
        n = 0;
        for (zone = FIRST_MONSTER; zone <= LAST_MONSTER; zone++) {
            const DuelCardRecord *other = &D_801A7AD8[(1 - side) * SIDE_RECORDS + zone];
            if ((other->flags & DUEL_CARD_FLAG_OCCUPIED) && !(other->flags & DUEL_CARD_FLAG_FACE_DOWN) &&
                other->card_id > 0 && is_dragon(other))
                n++;
        }
        return n ? now + n * PER_DRAGON : -1;
    case GIRL:
        return state.destroyed > 0 ? now + state.destroyed * PER_MAGICIAN : -1;
    case SLIFER_CARD:      /* 1000 for each card in its owner's hand, whatever its printed ATK and DEF */
        *value = hand_cards(side) * PER_HAND_CARD;
        return now - card->attack + *value;
    default:               /* Ra: its owner's life points */
        *value = D_800E9FF0[side].life_points.signed_value;
        return now - card->attack + *value;
    }
}

static void resolve_ids(void)
{
    int which;
    for (which = 0; which < CARDS; which++) {
        if (!id[which]) {
            id[which] = host->card_id(host, identity[which]);
            if (id[which] < 0) id[which] = 0;
            if (id[which]) host->log(host, "z-effects: %s is card %d", identity[which], id[which]);
        }
    }
}

/* Whether the other side has a face-up Slifer on its field. */
static int slifer_opposes(int record)
{
    int side = record / SIDE_RECORDS, zone;

    if (!id[SLIFER_CARD]) return 0;
    for (zone = FIRST_MONSTER; zone <= LAST_MONSTER; zone++) {
        const DuelCardRecord *other = &D_801A7AD8[(1 - side) * SIDE_RECORDS + zone];
        if ((other->flags & DUEL_CARD_FLAG_OCCUPIED) && !(other->flags & DUEL_CARD_FLAG_FACE_DOWN) &&
            other->card_id == id[SLIFER_CARD])
            return 1;
    }
    return 0;
}

/* Whether this monster was summoned weakened and is still the one that was. */
static int slifer_weakened(const DuelCardRecord *card, int record)
{
    return record >= 0 && record < 2 * SIDE_RECORDS && state.weak[record] && state.weak[record] == card->card_id &&
           !(card->flags & DUEL_CARD_FLAG_FACE_DOWN);
}

static s32 calc_card_stats(DuelCardRecord *card)
{
    s32 packed = original(card);
    int record = (int)(card - D_801A7AD8), attack, defense, cap, which, value;

    resolve_ids();
    if (!(card->flags & DUEL_CARD_FLAG_OCCUPIED) || (card->flags & DUEL_CARD_FLAG_FACE_DOWN) || card->card_id <= 0 ||
        record < 0 || record >= 2 * SIDE_RECORDS || record % SIDE_RECORDS < FIRST_MONSTER ||
        record % SIDE_RECORDS > LAST_MONSTER)
        return packed;
    attack = effect_attack(card, record, packed & 0xFFFF, &which, &value);
    defense = (int)((u32)packed >> 16);
    if (attack < 0) {
        attack = packed & 0xFFFF;
        which = -1;
    } else {
        cap = (int)host->limit(host, "attack");
        if (attack > cap) attack = cap;
        if (value >= 0) {               /* Slifer and Ra: the DEF is the same number, past the printed DEF */
            defense = defense - card->defense + value;
            if (defense < 0) defense = 0;
            cap = (int)host->limit(host, "defense");
            if (defense > cap) defense = cap;
        }
    }
    if (slifer_weakened(card, record)) {
        attack -= SLIFER_LOSS;
        if (attack < 0) attack = 0;
        if (which < 0) which = SLIFER_CARD;     /* only to log it once */
    } else if (which < 0) {
        return packed;
    }
    if (!logged[which]) {
        logged[which] = 1;
        host->log(host, "z-effects: %s (record %d) has %d ATK, %d DEF", identity[which], record, attack, defense);
    }
    return (defense << 16) | attack;
}

static void reset(void)
{
    int i;
    for (i = 0; i < CARDS; i++) id[i] = 0;     /* the card tables may differ in a loaded state */
}

/* Every duel starts with an empty "graveyard". */
static void init_scene(void)
{
    int i;
    state.destroyed = 0;
    for (i = 0; i < 2 * SIDE_RECORDS; i++) state.weak[i] = 0;
    original_init();
}

static void monster_event(MemoriesModEvent *event)
{
    if (event->phase != MEMORIES_AFTER) return;
    resolve_ids();
    if (event->c == MEMORIES_MONSTER_DESTROYED) {
        if (event->a == DARK_MAGICIAN || event->a == MAGICIAN_OF_BLACK_CHAOS) state.destroyed++;
    } else if (event->c == MEMORIES_MONSTER_SUMMON && event->b >= 0 && event->b < 2 * SIDE_RECORDS) {
        /* Slifer: a monster summoned in Attack Position whose ATK would drop to 0 is destroyed. */
        DuelCardRecord *card = &D_801A7AD8[event->b];
        state.weak[event->b] = 0;
        if (slifer_opposes(event->b) && !(card->flags & (DUEL_CARD_FLAG_FACE_DOWN | DUEL_CARD_FLAG_DEFENSE_POSITION))) {
            state.weak[event->b] = (short)card->card_id;
            if ((int)(original(card) & 0xFFFF) <= SLIFER_LOSS) {
                host->log(host, "z-effects: Slifer destroys the summoned card %d (record %d)", card->card_id, event->b);
                state.weak[event->b] = 0;
                /* Crush Card's removal on it, as a trap or a "destroy" effect shows a monster go; when
                 * that is busy, the card just comes off the field. */
                if (!MonsterEffects_Destroy(event->b)) DuelCard_RemoveFromField(card);
            }
        }
    }
}

int MemoriesModInit(const MemoriesModHost *from, MemoriesMod *mod)
{
    host = from;
    if (!host->hook(host, (void *)Duel_CalcCardStats, (void *)calc_card_stats, (void **)&original)) {
        host->log(host, "z-effects: could not hook Duel_CalcCardStats");
        return 0;
    }
    host->log(host, "z-effects: hooked Duel_CalcCardStats");
    if (!host->hook(host, (void *)Duel_InitScene, (void *)init_scene, (void **)&original_init) ||
        !host->subscribe(host, MEMORIES_EVENT_MONSTER, 0, monster_event) ||
        !host->register_state(host, &state, sizeof(state), 2)) {
        host->log(host, "z-effects: could not set up the Magician count");
        return 0;
    }
    mod->api = MEMORIES_MOD_API;
    mod->reset = reset;
    return 1;
}
