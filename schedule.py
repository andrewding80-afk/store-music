"""What should be playing right now.

This file does the deciding. It talks to nothing and needs no network, so it can be
tested completely on its own, which is the point: the part most likely to be wrong is
the part that can be checked without a speaker in the room.

Everything it knows comes from config.json. There is no store, time or playlist name
written into this code.

Precedence, highest first:
    what this particular system calls it  >  holiday  >  season  >  the default slot playlist

That first one exists because Andrew's home speakers hold different playlists from the
stores. A store entry in config.json may carry its own "playlists" block naming what to
play for a slot on that system. When it does, that name wins, because a name that is not
saved on that system cannot be played at all.
"""

import json
import os
import random
from datetime import datetime, date, time

CONFIG = os.path.join(os.path.dirname(__file__), 'config.json')

# A fixed point to count days from, so the order never depends on when this ran.
EPOCH = datetime(2026, 1, 1)


def local_now(cfg):
    """The time where the speakers are, whatever clock the machine is set to.

    This matters more than it looks. GitHub's machines run on UTC. Andrew's laptop runs
    on New York time. Without this the same code decides two different things, and the
    stores would start the lunch playlist at half past seven in the morning. The clock
    that counts is the one in the room, so it is named in config.json rather than
    inherited from whatever happens to be running this.
    """
    name = cfg.get('timezone')
    if not name:
        return datetime.now()
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        return datetime.now()
    return datetime.now(ZoneInfo(name))


def load(path=CONFIG):
    with open(path, encoding='utf-8') as f:
        return _apply_stored_ids(json.load(f))


# The name and the speaker group of a Sonos system are identifiers rather than keys, but
# they name Andrew's actual house, so they are kept out of this file and put in GitHub's
# secure storage instead. That is what lets the settings be readable by anyone without
# saying whose speakers these are.
#
# On his own machine nothing is set, so whatever is written in the file is used. That
# keeps the checks runnable on the laptop with no setup at all.
HOUSEHOLD_PREFIX = 'SONOS_HOUSEHOLD_'
GROUP_PREFIX = 'SONOS_GROUP_'


SPEAKER_PREFIX = 'SONOS_SPEAKER_'


def stored_id_names(store_id):
    """The three names to look for. Same shape as the pass: system id in capitals.

    SPEAKER is the one that does not expire. GROUP is kept as a fallback for a store
    that has not been switched over yet, and so nothing breaks during the change.
    """
    key = store_id.upper().replace('-', '_')
    return HOUSEHOLD_PREFIX + key, GROUP_PREFIX + key, SPEAKER_PREFIX + key


IDS_FILE = os.path.join(os.path.dirname(__file__), 'ids.json')


def _apply_stored_ids(cfg):
    # On a machine of Andrew's own, the identifiers sit in ids.json beside this file,
    # which is on the ignore list. On GitHub they arrive as settings on the job. A
    # setting on the job wins over the file, so nothing surprising happens if both exist.
    local = {}
    if os.path.exists(IDS_FILE):
        with open(IDS_FILE, encoding='utf-8') as f:
            local = json.load(f)
    for store in cfg.get('stores', []):
        household_name, group_name, speaker_name = stored_id_names(store['id'])
        mine = local.get(store['id'], {})
        for field, name in (('household', household_name), ('group', group_name),
                            ('speaker', speaker_name)):
            value = os.environ.get(name) or mine.get(field)
            if value:
                store[field] = value
    return cfg


# What a system's identifier says when it has not been filled in anywhere. Either it is
# waiting to be connected, or it lives in the secure storage and this machine cannot see
# it. Neither is a fault, and neither can be acted on.
def not_connected(store):
    household = (store or {}).get('household') or ''
    return (not household) or household.startswith('PENDING') or household.startswith('KEPT_')


def _hhmm(text):
    """'11:30' -> time(11, 30)

    '24:00' means the end of the day. Written that way because a slot that runs to
    midnight has to end after 23:59 and there is no such thing as time(24, 0).
    """
    if text.strip() == '24:00':
        return time(23, 59, 59, 999999)
    h, m = text.split(':')
    return time(int(h), int(m))


def _mmdd_in_range(when, start, end):
    """Is this date inside a 'MM-DD' to 'MM-DD' range, wrapping across new year?"""
    sm, sd = (int(x) for x in start.split('-'))
    em, ed = (int(x) for x in end.split('-'))
    cur = (when.month, when.day)
    lo, hi = (sm, sd), (em, ed)
    if lo <= hi:
        return lo <= cur <= hi
    # range wraps the new year, e.g. winter 12-01 to 02-28
    return cur >= lo or cur <= hi


DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def slots_for(cfg, store):
    """The timetable that applies to this system.

    A system may carry its own list of slots instead of the shared one. Andrew's home
    needs this: it plays Calm Radio rather than Spotify, because Spotify only plays in
    one place at a time and a job running on a schedule would cut off whatever he is
    listening to on his phone. The stores never hit that, since each has its own
    Spotify account.
    """
    own = (store or {}).get('slots')
    return own if own else cfg['slots']


def _slot_runs_today(slot, now):
    """A slot may be limited to certain days. No list means every day."""
    days = slot.get('days')
    if not days:
        return True
    return DAYS[now.weekday()] in days


def current_slot(cfg, now, store=None):
    """The slot this moment falls in, or None when nothing should be playing.

    The first slot that matches wins, so a slot that covers only some days should be
    listed above the everyday one it overlaps.
    """
    t = now.time()
    for slot in slots_for(cfg, store):
        if not _slot_runs_today(slot, now):
            continue
        start, end = _hhmm(slot['from']), _hhmm(slot['to'])
        if start <= t < end:
            return slot
    return None


def active_holiday(cfg, when):
    for hol in cfg.get('holidays', []):
        if _mmdd_in_range(when, hol['from'], hol['to']):
            return hol
    return None


def active_season(cfg, when):
    for name, season in cfg.get('seasons', {}).items():
        if _mmdd_in_range(when, season['from'], season['to']):
            return name, season
    return None, None


def deal_from_pool(slot, now):
    """Pick one playlist from a list, like dealing from a shuffled deck.

    Why a deck and not a dice. This runs every fifteen minutes, so a fresh random
    choice each time would change the music four times an hour. And true randomness
    repeats: five playlists rolled daily gives the same one twice in a week more often
    than people expect. A deck deals each playlist once before any of them comes round
    again, in a different order every cycle.

    It remembers nothing. The order is worked out from the date, so every run on the
    same day reaches the same answer.
    """
    pool = list(slot['playlist_pool'])
    size = len(pool)
    if size == 1:
        return pool[0], 'the only one in the list'

    # How many blocks have passed since a fixed starting point. One per day by default.
    hours = slot.get('reshuffle_every_hours')
    if hours:
        elapsed = int((datetime.combine(now.date(), time(0, 0)) - EPOCH).total_seconds() // 3600)
        block = (elapsed + now.hour) // int(hours)
        unit = 'every %s hours' % hours
    else:
        block = (now.date() - EPOCH.date()).days
        unit = 'today'

    cycle, position = divmod(block, size)

    # Shuffle the deck the same way every time for a given cycle, so the order is
    # settled rather than remembered. A different cycle deals a different order.
    deck = _deck_for(slot['name'], pool, cycle)

    # A shuffled deck can deal its last card and then the next deck's first card, which
    # would play the same station two days running. Look at what the previous deck
    # ended on and, if the new one starts with it, move that card back one place.
    if size > 2:
        previous = _deck_for(slot['name'], pool, cycle - 1)
        if deck[0] == previous[-1]:
            deck[0], deck[1] = deck[1], deck[0]

    return deck[position], ('number %d of %d in this round, %s' % (position + 1, size, unit))


def _deck_for(name, pool, cycle):
    """The order this round is dealt in. Same answer every time it is asked."""
    deck = list(pool)
    random.Random('%s|%s' % (name, cycle)).shuffle(deck)
    return deck


def decide(cfg, now, store=None):
    """What should be playing, and why.

    Returns a dict. 'playlist' is None when nothing should be playing.
    'reason' always explains the choice in plain words, because a schedule that
    cannot say why it did something is not auditable.
    """
    slot = current_slot(cfg, now, store)
    if slot is None:
        return {
            'playing': False,
            'slot': None,
            'playlist': None,
            'volume': None,
            'reason': 'Outside service hours. Nothing should be playing.',
            'needs_attention': None,
            'speakers': None,
            'slot_playlists': [],
        }

    # A slot may name one playlist, a different one for each day of the week, or a list
    # to be dealt from. All three are how a week avoids sounding the same without the
    # software having to remember anything between runs.
    by_day = slot.get('playlist_by_day')
    pool = slot.get('playlist_pool')
    if by_day:
        today = DAYS[now.weekday()]
        playlist = by_day.get(today, slot.get('playlist'))
        source = 'what this slot plays on a %s' % today
    elif pool:
        playlist, source = deal_from_pool(slot, now)
    else:
        playlist = slot['playlist']
        source = 'the default for this slot'

    # Every name that belongs to this slot, not only the one picked for this moment.
    # The leave-it-off rule needs the whole list. Found the hard way on the evening of
    # 2026-09-08: a pause at home was overridden within the minute, because the paused
    # playlist was compared with the single dealt pick and the deal named a different
    # member of the same evening list. Any member of the slot's list is this slot's
    # own music.
    belongs = set()
    if by_day:
        belongs.update(v for v in by_day.values() if v)
    if pool:
        belongs.update(pool)
    if slot.get('playlist'):
        belongs.add(slot['playlist'])

    season_name, season = active_season(cfg, now.date())
    if season and slot['name'] in season.get('overrides', {}):
        playlist = season['overrides'][slot['name']]
        source = 'the %s override' % season_name

    holiday = active_holiday(cfg, now.date())
    if holiday and slot['name'] in holiday.get('overrides', {}):
        playlist = holiday['overrides'][slot['name']]
        source = 'the %s override' % holiday['name']

    # What this particular system calls it wins over everything above, because a name
    # that is not saved on that system cannot be played there at all.
    own = (store or {}).get('playlists', {})
    if slot['name'] in own:
        playlist = own[slot['name']]
        source = "what %s calls it" % (store.get('name') or store.get('id'))

    # Whatever won the argument above belongs to the slot too, so an override name
    # still counts as this slot's own music.
    belongs.add(playlist)

    # A system may set each speaker separately rather than the whole group at one level.
    # Only speakers named here get their own number. Everything else on that system is
    # set to the slot volume, so no speaker is ever left sitting at last night's level.
    speakers = (store or {}).get('speaker_volumes', {}).get(slot['name'])

    # A playlist may carry its own volume, which beats the slot's. Andrew asked for
    # AMBIENT CALM to play at 15 wherever it comes up, quieter than the rest of that
    # slot, so the level belongs to the playlist rather than to the hour.
    volume = slot['volume']
    own_volume = (slot.get('volume_by_playlist') or {}).get(playlist)
    if own_volume is not None:
        volume = own_volume
        source = '%s, at its own level of %d' % (source, own_volume)
        if speakers:
            # A room that was meant to be silent stays silent. Every room that was going
            # to play moves to this playlist's own level.
            speakers = dict((room, (own_volume if level > 0 else 0))
                            for room, level in speakers.items())

    # A placeholder is marked by the word NEEDS and nothing else. An earlier version also
    # treated any name in capitals as a placeholder, which was fine while the only capitals
    # were "NEEDS A VOCAL PLAYLIST" and wrong the moment Andrew's Calm Radio stations
    # arrived, since every one of those is named BACH, MOZART, VIVALDI and so on.
    attention = None
    if 'NEEDS' in playlist:
        attention = ('No playlist is set for %s. It is named %r in the config, which is a '
                     'placeholder rather than a real playlist.' % (slot['name'], playlist))

    return {
        'playing': True,
        'slot': slot['name'],
        'playlist': playlist,
        'volume': volume,
        'reason': '%s, %s to %s, using %s' % (slot['name'], slot['from'], slot['to'], source),
        'needs_attention': attention,
        'speakers': speakers,
        'slot_playlists': sorted(belongs),
    }


def day_plan(cfg, when, store=None):
    """Every change point for one day. Useful for showing a whole day at a glance."""
    out = []
    for slot in slots_for(cfg, store):
        if not _slot_runs_today(slot, datetime.combine(when, time(12, 0))):
            continue
        moment = datetime.combine(when, _hhmm(slot['from']))
        out.append((slot['from'], decide(cfg, moment, store)))
    return out


if __name__ == '__main__':
    import sys
    cfg = load()
    when = datetime.now()
    if len(sys.argv) > 1:
        when = datetime.fromisoformat(sys.argv[1])
    print('Plan for %s' % when.date())
    for at, d in day_plan(cfg, when):
        note = ('   <-- %s' % d['needs_attention']) if d['needs_attention'] else ''
        print('  %s  %-14s  vol %s  %s%s' % (at, d['slot'], d['volume'], d['playlist'], note))
