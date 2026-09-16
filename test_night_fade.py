"""The Bedroom's last hour at home, asked for by Andrew on 2026-09-15.

Eleven to midnight keeps its own level until 23:30. Then the Bedroom steps down to
12, at 23:45 to 10, and from there fades to nothing by midnight. Nothing here talks
to Sonos or waits: it answers in place of Sonos and records every sleep.
"""

import sys
import types
import datetime

STATE = {'levels': [], 'slept': [], 'speakers': {}}
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
    m.players = lambda s, h: dict(ROOMS)
    m.player_volume = lambda s, p: {'volume': STATE['speakers'].get(p, 18)}
    m.set_player_volume = set_player_volume
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


def bedroom_at(cfg, home, hh, mm):
    when = datetime.datetime(2026, 9, 15, hh, mm)
    want = schedule.decide(cfg, when, home)
    return want, (want.get('speakers') or {}).get('Bedroom')


def main():
    cfg = schedule.load('config.json')
    home = [s for s in cfg['stores'] if s['id'] == 'home'][0]
    home['household'] = 'Sonos_pretend_household'
    home['group'] = 'RINCON_pretend_group:1'

    # The night level itself is whatever the dealt playlist asks for: 18 most nights,
    # 15 when Goodnight Mix is dealt. So the Bedroom is checked against the rest of the
    # house rather than against a fixed number.
    want, bed = bedroom_at(cfg, home, 23, 15)
    night_level = (want.get('speakers') or {}).get('Kitchen')
    check(bed == night_level,
          'before half past eleven the Bedroom sits at the same night level as the house')
    check(not want.get('ramp'), 'and nothing is fading yet')

    want, bed = bedroom_at(cfg, home, 23, 35)
    check(bed == 12, 'at half past eleven the Bedroom is turned down to 12')
    check(not want.get('ramp'), 'and still nothing is fading')
    check((want.get('speakers') or {}).get('Kitchen') == night_level,
          'the Kitchen is left at the night level, this is the Bedroom only')

    want, bed = bedroom_at(cfg, home, 23, 45)
    check(bed == 10, 'at a quarter to midnight it is turned down to 10')
    check(want.get('ramp') and want['ramp']['speaker'] == 'Bedroom'
          and want['ramp']['to'] == 0,
          'and from there the Bedroom is fading to nothing')

    want, bed = bedroom_at(cfg, home, 23, 52)
    check(bed is not None and 4 <= bed <= 6,
          'halfway through that last quarter hour it is about half way down')
    want, bed = bedroom_at(cfg, home, 23, 59)
    check(bed <= 1, 'and by a minute to midnight it is as good as silent')

    # The fade itself: a run that lands in the last quarter hour takes the Bedroom
    # down to nothing across whatever time is left, rather than in one step.
    STATE.update(levels=[], slept=[], speakers=dict((p, 18) for p in ROOMS.values()))
    STATE['speakers']['P-bed'] = 10
    when = datetime.datetime(2026, 9, 15, 23, 47)
    want = schedule.decide(cfg, when, home)
    lines, acted = [], []
    run.night_ramp(home, want, when, lines, acted)
    bed = [v for p, v in STATE['levels'] if p == 'P-bed']
    others = [v for p, v in STATE['levels'] if p != 'P-bed']
    check(len(bed) > 3 and bed == sorted(bed, reverse=True) and bed[-1] == 0,
          'the Bedroom steps down to nothing, never up')
    check(not others, 'and no other room is touched')
    check(abs(sum(STATE['slept']) - 13 * 60) < 60,
          'taking the time that is left until midnight')
    check(bool(acted), 'and the run says it did it')

    print()
    if fails:
        print('%d CHECK%s FAILED.' % (len(fails), '' if len(fails) == 1 else 'S'))
        return 1
    print('All checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
