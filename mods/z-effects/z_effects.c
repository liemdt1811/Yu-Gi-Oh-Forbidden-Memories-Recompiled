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
#include <stdarg.h>
#include "types.h"
#include <string.h>
#include "game/card_constants.h"
#include "game/duel_card.h"
#include "game/duel_init_scene.h"
#include "game/duel_side_state.h"
#include "game/duel_card_record_lifecycle.h"
#include "game/duel_battle_stats.h"
#include "game/display_object.h"
#include "game/display_object_work_slots.h"
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

/* A line in z-effects.txt in the mod's data folder (mod-data/z-effects, beside the saves), while the game's "mods" log channel is on (MEMORIES_TRACE=mods): the first 600 lines of a run, to see what the duel works from. */
static int traced;
static char last_line[200];
static void trace(const char *format, ...)
{
    char line[200];
    FILE *file;
    va_list arguments;
    int n;
    if (traced >= 600 || !host->log_enabled(host)) return;     /* only when the "mods" log channel is on */
    va_start(arguments, format);
    n = vsnprintf(line, sizeof(line) - 1, format, arguments);
    va_end(arguments);
    if (n <= 0) return;
    line[n < (int)sizeof(line) - 2 ? n : (int)sizeof(line) - 2] = 0;
    if (!strcmp(line, last_line)) return;       /* the same line as the one before is not news */
    strcpy(last_line, line);
    if (!(file = host->open_data(host, "z-effects.txt", traced ? "a" : "w"))) return;
    traced++;
    {
        fwrite(line, 1, strlen(line), file);
        fwrite("\n", 1, 1, file);
    }
    fclose(file);
}
static s32 (*original)(DuelCardRecord *card);
static void (*original_init)(void);
static int id[CARDS];       /* the cards' ids this run, 0 until the tables are built */
static int logged[CARDS];
static struct { int destroyed; short weak[2 * SIDE_RECORDS]; } state;     /* in save states: Magicians destroyed this duel; the cards Slifer weakened, by record */

/* A fighter of the battle on screen. The battle takes both fighters' records off the field (DuelCard_DeactivateRecord
 * clears DUEL_CARD_FLAG_OCCUPIED, and the record keeps no display object either) and shows them as its own objects,
 * D_800E9EF0[0] (the attacker) and [1] (the defender): to the battle, a card is there by its id alone. */
static int in_battle(int record)
{
    return (D_800E9EF0[0] && D_800E9EF0[0]->field_6A == record) || (D_800E9EF0[1] && D_800E9EF0[1]->field_6A == record);
}

/* A monster is on the field when its record is occupied or has an object, or while it is fighting. */
static int present(const DuelCardRecord *card, int record)
{
    return (card->flags & DUEL_CARD_FLAG_OCCUPIED) || card->object != 0 || in_battle(record);
}

/* Face up: a fighter's flags are not worth reading (the one that attacks face down turns face up as it does). */
static int face_up(const DuelCardRecord *card, int record)
{
    return !(card->flags & DUEL_CARD_FLAG_FACE_DOWN) || in_battle(record);
}

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
            if (present(other, (1 - side) * SIDE_RECORDS + zone) && face_up(other, (1 - side) * SIDE_RECORDS + zone) &&
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
        if (present(other, (1 - side) * SIDE_RECORDS + zone) && face_up(other, (1 - side) * SIDE_RECORDS + zone) &&
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
    if (card->card_id <= 0 || record < 0 || record >= 2 * SIDE_RECORDS || record % SIDE_RECORDS < FIRST_MONSTER ||
        record % SIDE_RECORDS > LAST_MONSTER || !present(card, record) || !face_up(card, record)) {
        for (which = 0; which < CARDS && record % SIDE_RECORDS >= FIRST_MONSTER; which++)    /* not a hand card */
            if (id[which] && card->card_id == id[which])
                trace("calc %s skipped: record %d flags %04x object %d", identity[which], record, card->flags, card->object != 0);
        return packed;
    }
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
    if (which >= SLIFER_CARD) trace("calc %s record %d flags %04x: %d ATK %d DEF", identity[which], record, card->flags, attack, defense);
    return (defense << 16) | attack;
}

/* The battle's own number: the damage a direct attack deals, or the difference of a fight. Logged for Slifer and Ra,
 * to see what the duel works from. */
static s32 (*original_battle)(DisplayObject *left, DisplayObject *right);
static s32 battle_result(DisplayObject *left, DisplayObject *right)
{
    s32 result = original_battle(left, right);
    if (left) {
        const DuelCardRecord *card = &D_801A7AD8[left->field_6A];
        if ((id[SLIFER_CARD] && card->card_id == id[SLIFER_CARD]) || (id[RA_CARD] && card->card_id == id[RA_CARD]))
            trace("battle result %d (%s) attacker record %d flags %04x stats %08x", (int)result, right ? "fight" : "direct",
                  (int)left->field_6A, card->flags, (unsigned)original(card));
        if (id[SLIFER_CARD] && card->card_id == id[SLIFER_CARD])
            host->log(host, "z-effects: Slifer battle result %d (%s)", (int)result, right ? "fight" : "direct");
        else if (id[RA_CARD] && card->card_id == id[RA_CARD])
            host->log(host, "z-effects: Ra battle result %d (%s)", (int)result, right ? "fight" : "direct");
    }
    return result;
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
    host->hook(host, (void *)func_8001EFD4, (void *)battle_result, (void **)&original_battle);
    mod->api = MEMORIES_MOD_API;
    mod->reset = reset;
    return 1;
}
