"""Checks the fade in Andrew asked for on 2026-09-12: at home the music comes on
from silence and rises to its level, ten minutes on weekend mornings and two minutes
for every other slot. The shops start at once, as before.

Nothing here talks to Sonos or waits. It answers in place of Sonos and records every
sleep instead of taking it, so a ten minute fade is checked in a blink.
"""

import sys
import types
import datetime

STATE = {'playing': False, 'container': None, 'played': [],
         'levels': [], 'slept': [], 'speakers': {}}

ROOMS = {'Bedroom': 'P-bed', 'Dressing Room': 'P-dress', 'Kitchen': 'P-kit',
         'Sunroom': 'P-sun', 'TV Room': 'P-tv'}


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
                                        STATE.update(playing=True))
    m.pause = lambda s, g: STATE.update(playing=False)
    m.set_volume = lambda s, g, v: STATE['levels'].append(('group', v))
    m.group_volume = lambda s, g: {'volume': 30}
    m.players = lambda s, h: dict(ROOMS) if s == 'home' else {}
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
    STATE.update(playing=playing, container=container, played=[], levels=[], slept=[],
                 speakers=dict((p, 30) for p in ROOMS.values()))


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
    check(bed and bed[0] == 0 and bed[-1] == want['speakers']['Bedroom'],
          'the evening also starts from silence and reaches its level')
    check(abs(sum(STATE['slept']) - 120) < 1, 'taking about two minutes')
    tv = levels_of('P-tv')
    check(tv == [0], 'a room meant to be silent this slot is set to 0 once and left there')

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

    # 5. A shop starts at once. Nothing about this may reach a shop.
    shop = store_called(cfg, 'west-harlem')
    noon = datetime.datetime(2026, 9, 14, 12, 0)
    want = schedule.decide(cfg, noon, shop)
    check(not want.get('fade_in_seconds'), 'no shop has a fade in')
    fresh()
    run.check_store(cfg, shop, noon, True)
    check(bool(STATE['played']) and not STATE['slept'], 'a shop starts its music at once')

    # 6. Step sizes: long fades take bigger steps rather than making hundreds of calls.
    check(run.fade_in_steps(600) == 20, 'ten minutes is twenty steps of thirty seconds')
    check(run.fade_in_steps(120) == 12, 'two minutes is twelve steps of ten seconds')
    check(run.fade_in_steps(5) == 1, 'anything tiny is a single step')

    print()
    if fails:
        print('%d CHECK%s FAILED.' % (len(fails), '' if len(fails) == 1 else 'S'))
        return 1
    print('All checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
