"""Checks the fade in Andrew asked for on 2026-09-12: at home the music comes on
from silence and rises to its level, ten minutes on weekend mornings and two minutes
for every other slot. The shops start at once, as before.

Nothing here talks to Sonos or waits. It answers in place of Sonos and records every
sleep instead of taking it, so a ten minute fade is checked in a blink.
"""

import sys
import types
import datetime

STATE = {'playing': False, 'container': None, 'played': [], 'played_at': [],
         'levels': [], 'slept': [], 'speakers': {}}

ROOMS = {'Bedroom': 'P-bed', 'Dressing Room': 'P-dress', 'Kitchen': 'P-kit',
         'Sunroom': 'P-sun', 'TV Room': 'P-tv'}

SHOP_ROOMS = {'Dining Room': 'P-dining', 'Dining Room 2': 'P-dining-2'}
PAIR_ROOMS = {'Dining Room Left Speaker': 'P-left', 'Dining Room Right Speaker': 'P-right'}
ONE_ROOM = {'Dining Room': 'P-ch'}
ALL_PLAYERS = (list(ROOMS.values()) + list(SHOP_ROOMS.values())
               + list(PAIR_ROOMS.values()) + list(ONE_ROOM.values()))


def fake_sonos():
    m = types.ModuleType('sonos')

    class SonosError(Exception):
        pass

    def set_player_volume(s, p, v):
        STATE['levels'].append((p, v))
        STATE['speakers'][p] = v

    m.SonosError = SonosError
    m.now_playing = lambda s, g: {'container': {'name': STATE['container']}}
    m.playback_status = lambda s, g: {
        'playbackState': 'PLAYBACK_STATE_PLAYING' if STATE['playing'] else 'PLAYBACK_STATE_PAUSED'}
    m.find_favourite = lambda s, h, n: {'id': 'fav-%s' % n, 'name': n}
    m.play_favourite = lambda s, g, f: (STATE['played'].append(f),
                                        STATE['played_at'].append(len(STATE['levels'])),
                                        STATE.update(playing=True))
    m.pause = lambda s, g: STATE.update(playing=False)
    m.set_volume = lambda s, g, v: STATE['levels'].append(('group', v))
    # A one speaker group's volume is that speaker's, as on a real Sonos.
    m.group_volume = lambda s, g: {'volume': STATE['speakers'].get('P-ch', 30)
                                   if s == 'central-harlem' else 30}
    # West Harlem sets each of its two speakers separately from 2026-09-14, so it has
    # to answer with them, or the run waits for speakers that never reply.
    m.players = lambda s, h: dict(ROOMS) if s == 'home' else (
        dict(SHOP_ROOMS) if s == 'west-harlem' else (
            dict(PAIR_ROOMS) if s == 'hells-kitchen' else (
                dict(ONE_ROOM) if s == 'central-harlem' else {})))
    m.player_volume = lambda s, p: {'volume': STATE['speakers'].get(p, 30)}
    m.set_player_volume = set_player_volume
    m.groups = lambda s, h: {'groups': []}
    return m


sys.modules['sonos'] = fake_sonos()

import run        # noqa: E402
import schedule   # noqa: E402

run.time.sleep = lambda secs: STATE['slept'].append(secs)

fails = []


def check(ok, what):
    print('%s %s' % ('PASS' if ok else 'FAIL', what))
    if not ok:
        fails.append(what)


def store_called(cfg, store_id):
    store = [s for s in cfg['stores'] if s['id'] == store_id][0]
    store['household'] = 'Sonos_pretend_household'
    store['group'] = 'RINCON_pretend_group:1'
    return store


def fresh(container=None, playing=False):
    STATE.update(playing=playing, container=container, played=[], played_at=[],
                 levels=[], slept=[], speakers=dict((p, 30) for p in ALL_PLAYERS))


def levels_of(player_id):
    return [v for p, v in STATE['levels'] if p == player_id]


def main():
    cfg = schedule.load('config.json')
    home = store_called(cfg, 'home')

    # 1. Saturday morning, the ten o'clock start. The house is silent from midnight.
    sat = datetime.datetime(2026, 9, 12, 10, 5)          # a Saturday
    want = schedule.decide(cfg, sat, home)
    check(want['fade_in_seconds'] == 600, 'weekend morning at home fades in over ten minutes')
    check(want['speakers']['Bedroom'] == 20, 'and the Bedroom tops out at 20 on a weekend morning')

    fresh()
    lines, trouble, pending, acted = run.check_store(cfg, home, sat, True)
    text = '\n'.join(lines)
    bed = levels_of('P-bed')
    check(bool(STATE['played']), 'the music was started')
    check(bed and bed[0] == 0, 'the Bedroom was silenced before the music started')
    first_set = STATE['levels'].index(('P-bed', 0))
    check(STATE['played'] and first_set < len(STATE['levels']) - 1,
          'the silencing came before the fade, not after')
    check(bed[-1] == 20, 'and it ended at 20')
    check(max(bed) == 20, 'and never went above 20 on the way up')
    check(bed == sorted(bed), 'and only ever went up')
    check(len(set(bed)) > 5, 'in more than a handful of steps, so it is a fade and not a jump')
    check(abs(sum(STATE['slept']) - 600) < 1, 'taking about ten minutes in all')
    check(levels_of('P-kit')[-1] == 28, 'the Kitchen rose to its own level at the same time')
    # A silent house at the start of a slot is already reported as silent by the code
    # that finds it, before the music is started. That is existing behaviour and not
    # the fade's to change, so only the outstanding flag is pinned here.
    check(not pending, 'and nothing was left outstanding')
    check('faded up' in text, 'and the report says it faded up')

    # 2. A weekday evening start at six, coming off the daytime station.
    mon_eve = datetime.datetime(2026, 9, 14, 18, 5)      # a Monday
    want = schedule.decide(cfg, mon_eve, home)
    check(want['fade_in_seconds'] == 120, 'every other home slot fades in over two minutes')
    fresh(container='BACH', playing=True)
    run.check_store(cfg, home, mon_eve, True)
    bed = levels_of('P-bed')
    at_play = STATE['played_at'][0] if STATE['played_at'] else 0
    bed_down = [v for p, v in STATE['levels'][:at_play] if p == 'P-bed']
    check(bed_down and bed_down[0] < 30 and bed_down[-1] == 0,
          'the daytime station fades down to nothing first')
    check(bed and bed[-1] == want['speakers']['Bedroom'],
          'then the evening rises to its level')
    check(abs(sum(STATE['slept']) - (120 + run.CHANGE_FADE_OUT_SECONDS)) < 1,
          'taking the short fade out plus home\'s own two minute fade in')
    tv = levels_of('P-tv')
    check(tv and tv[-1] == 0 and tv == sorted(tv, reverse=True),
          'a room meant to be silent this slot fades down and stays silent')

    # 3. Music already right in the middle of a slot: no fade, no waiting, nothing touched.
    fresh(container=want['playlist'], playing=True)
    for p in ROOMS.values():
        STATE['speakers'][p] = 0
    for room, level in want['speakers'].items():
        STATE['speakers'][ROOMS[room]] = level
    STATE['levels'] = []
    run.check_store(cfg, home, mon_eve, True)
    check(not STATE['slept'] and not STATE['levels'],
          'when the music is already right there is no fade and nothing is set')

    # 4. Dry run: it says what it would do and waits for nothing.
    fresh()
    lines, trouble, pending, acted = run.check_store(cfg, home, sat, False)
    check(not STATE['played'] and not STATE['slept'] and not STATE['levels'],
          'a dry run starts nothing, sets nothing and waits for nothing')
    check(pending and 'fading in over 600 seconds' in '\n'.join(lines),
          'and it says the change is outstanding and how long the fade would take')

    # 5. Andrew, 2026-09-14: every playlist change at every location fades the old
    # music out, then fades the new one in. This reverses the 2026-09-12 rule that the
    # shops start at once.
    shop = store_called(cfg, 'west-harlem')
    lunch = datetime.datetime(2026, 9, 14, 13, 0)
    want = schedule.decide(cfg, lunch, shop)
    fresh(container='Cocktail Jazz', playing=True)
    STATE['speakers'].update({'P-dining': 28, 'P-dining-2': 36})
    lines, trouble, pending, acted = run.check_store(cfg, shop, lunch, True)
    new = levels_of('P-dining-2')
    before = STATE['levels'][:STATE['played_at'][0]] if STATE['played_at'] else []
    down = [v for p, v in before if p == 'P-dining-2']
    check(bool(STATE['played']), 'a shop playing the wrong playlist is changed')
    check(len(down) > 2 and down == sorted(down, reverse=True) and down[-1] == 0,
          'the old music fades down to nothing before the new playlist starts')
    up = new[len(down):]
    check(len(up) > 2 and up == sorted(up) and up[-1] == 36,
          'then the new playlist fades up to its level')
    check(levels_of('P-dining')[-1] == 28, 'the other speaker comes back to its own level')
    check(abs(sum(STATE['slept']) - (run.CHANGE_FADE_OUT_SECONDS
                                     + run.CHANGE_FADE_IN_SECONDS)) < 1,
          'taking the short change fade, not a long one')
    check('faded down' in '\n'.join(lines) and 'faded up' in '\n'.join(lines),
          'and the report says both')

    # 5b. A shop starting from silence at opening has nothing to fade out, but still
    # fades in.
    fresh(container='Brunch Jazz', playing=False)
    run.check_store(cfg, shop, lunch, True)
    new = levels_of('P-dining-2')
    check(new[0] == 0 and new[-1] == 36 and new == sorted(new),
          'a shop starting from silence fades in from nothing')
    check(abs(sum(STATE['slept']) - run.CHANGE_FADE_IN_SECONDS) < 1,
          'with no fade out, because nothing was playing')

    # 5c. A store without its own per speaker levels keeps the balance set by hand in
    # the room: each speaker fades back to where it was, not to one shared number.
    # Every multi speaker store has its own levels today, so this is Hell's Kitchen
    # with them taken away, which is how it ran before 2026-09-10.
    hk = dict(store_called(cfg, 'hells-kitchen'))
    hk.pop('speaker_volumes', None)
    lunch_hk = datetime.datetime(2026, 9, 14, 13, 0)
    want = schedule.decide(cfg, lunch_hk, hk)
    check(not want.get('speakers'), '(Hell\'s Kitchen sets the group, not each speaker, at lunch)')
    fresh(container='Cocktail Jazz', playing=True)
    STATE['speakers'].update({'P-left': 34, 'P-right': 30})
    run.check_store(cfg, hk, lunch_hk, True)
    check(bool(STATE['played']) and 0 in levels_of('P-left'),
          'the pair fades down before the change')
    check(levels_of('P-left')[-1] == 34 and levels_of('P-right')[-1] == 30,
          'and each speaker fades back to its own level, keeping the balance')

    # 5d. A one speaker store rises straight to the slot's level. Seen at Central Harlem's
    # first real fade, 16:00 on 2026-09-14: it rose to its old 30 and then jumped to 34.
    ch = store_called(cfg, 'central-harlem')
    evening = datetime.datetime(2026, 9, 14, 16, 30)
    want = schedule.decide(cfg, evening, ch)
    fresh(container='Instrumental Jazz Standards', playing=True)
    run.check_store(cfg, ch, evening, True)
    one = levels_of('P-ch')
    at_play = STATE['played_at'][0] if STATE['played_at'] else 0
    down = [v for p, v in STATE['levels'][:at_play] if p == 'P-ch']
    up = one[len(down):]
    check(up and up == sorted(up) and up[-1] == want['volume'] and want['volume'] != 30,
          'a one speaker store fades up to the new slot level, not its old one')
    check(one.count(want['volume']) == 1 and not [v for p, v in STATE['levels'] if p == 'group'],
          'and nothing jumps it there afterwards')

    # 6. Step sizes: long fades take bigger steps rather than making hundreds of calls,
    # and short fades still take enough steps to sound like a fade.
    check(run.fade_in_steps(600) == 20, 'ten minutes is twenty steps of thirty seconds')
    check(run.fade_in_steps(120) == 12, 'two minutes is twelve steps of ten seconds')
    check(run.fade_in_steps(20) == 10, 'twenty seconds is ten steps of two seconds')
    check(run.fade_in_steps(1) == 1, 'anything tiny is a single step')

    print()
    if fails:
        print('%d CHECK%s FAILED.' % (len(fails), '' if len(fails) == 1 else 'S'))
        return 1
    print('All checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
