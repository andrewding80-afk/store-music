"""Telling a person's change from the job's own, so a hand change at home is left alone.

Andrew, 2026-10-05: at home, a room turned up or down by hand stays there until
midnight, as does music picked by hand and a pause; untouched rooms still follow the
schedule; and each morning everything resets and any split-off room rejoins the group.

Until now the job remembered nothing between runs, so it could not tell its own levels
from a person's and put everything back within fifteen minutes. This keeps a small
memory: what each speaker was at, and what music was on, at the end of the last run.
A difference the job did not make was made by a person (or, by Andrew's answer 6, by the
speaker itself) and is held until the day changes.

Two guards keep a bad memory from doing harm. A level that already matches the schedule
is never held, and a room with nothing remembered is never held. So a lost or stale
memory can only ever fall back to the old behaviour, never freeze the house at a level
nobody chose.

Nothing here talks to Sonos. run.py does the reading and setting; memory.py the storing.
"""


def fresh(day):
    return {'day': day, 'held': {}, 'set': {}, 'music': None, 'playing': False,
            'music_held': None, 'paused_held': False, 'morning_done': False}


def start_day(mem, day):
    """A new day forgets every hand change and owes the morning reset.

    Returns (memory, whether it reset). The day is the local date, so it turns at
    midnight, which is when Andrew asked for the reset.
    """
    if not mem or mem.get('day') != day:
        return fresh(day), True
    out = fresh(day)
    out.update(mem)
    return out, False


def find_hand_levels(mem, actual, wanted):
    """Rooms whose level the job did not set. Adds them to mem['held']; returns the new ones."""
    new = []
    for name, level in sorted(actual.items()):
        if name in mem['held']:
            continue
        if name not in mem['set']:
            continue                    # nothing remembered, so no evidence
        if level == mem['set'][name]:
            continue                    # where the job left it
        if level == wanted.get(name):
            continue                    # matches the schedule anyway
        mem['held'][name] = level
        new.append(name)
    return new


def levels_to_set(mem, wanted):
    """The schedule's levels, less every room held by hand."""
    held = (mem or {}).get('held') or {}
    return dict((n, v) for n, v in wanted.items() if n not in held)


def find_hand_music(mem, container, is_playing, want_playlist):
    """A pause or a playlist the job did not start. Sets music_held or paused_held."""
    if mem.get('music') is None:
        return                          # no evidence of what the job left on
    if not is_playing:
        if mem.get('playing'):
            mem['paused_held'] = True
        return
    if container and container != mem['music'] and container != want_playlist:
        mem['music_held'] = container


def skip_ramp(mem, speaker):
    return bool(mem) and speaker in (mem.get('held') or {})


def remember(mem, actual, container, is_playing):
    """What the house was left at, for the next run to compare against."""
    mem['set'] = dict(actual)
    mem['music'] = container
    mem['playing'] = bool(is_playing)
