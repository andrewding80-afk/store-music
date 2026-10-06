"""The real run, at home, against a pretend house: hand changes kept, mornings and nights reset.

Written 2026-10-05 with hand.py. Nothing here talks to Sonos or waits.
"""
from datetime import datetime

import hand
import run
import schedule

failures = []


def check(ok, why):
    if not ok:
        failures.append(why)
    print('%s %s' % ('PASS' if ok else 'FAIL', why))


ROOMS = {'Bedroom': 'P-bed', 'Dressing Room': 'P-dress', 'Kitchen': 'P-kit',
         'Sunroom': 'P-sun', 'TV Room': 'P-tv'}
NAME = dict((v, k) for k, v in ROOMS.items())
H = {}


def house(levels, members=None, muted=(), playing=True, container='X'):
    H.update(levels=dict((ROOMS[n], v) for n, v in levels.items()),
             members=set(ROOMS[n] for n in (members or ROOMS)), muted=set(ROOMS[n] for n in muted),
             playing=playing, container=container, calls=[])


def groups(s, h):
    others = [p for p in ROOMS.values() if p not in H['members']]
    gs = [{'id': 'G', 'name': 'main', 'playerIds': sorted(H['members'])}]
    gs += [{'id': 'G-' + p, 'name': NAME[p], 'playerIds': [p]} for p in others]
    return {'groups': gs, 'players': [{'id': p, 'name': n} for n, p in ROOMS.items()]}


def set_player_volume(s, p, v):
    H['levels'][p] = v
    H['calls'].append(('volume', NAME[p], v))


def play_favourite(s, g, fid):
    H['container'], H['playing'] = fid, True
    H['calls'].append(('play', fid))


def add_to_group(s, g, ids):
    H['members'].update(ids)
    H['calls'].append(('regroup', sorted(NAME[i] for i in ids)))


def set_player_mute(s, p, m):
    if not m:
        H['muted'].discard(p)
    H['calls'].append(('unmute', NAME[p]))


S = run.sonos
S.groups = groups
S.players = lambda s, h: dict(ROOMS)
S.player_volume = lambda s, p: {'volume': H['levels'].get(p, 0), 'muted': p in H['muted']}
S.set_player_volume = set_player_volume
S.set_player_mute = set_player_mute
S.add_to_group = add_to_group
S.now_playing = lambda s, g: {'container': {'name': H['container']}}
S.playback_status = lambda s, g: {'playbackState': 'PLAYBACK_STATE_PLAYING' if H['playing'] else 'PLAYBACK_STATE_PAUSED'}
S.find_favourite = lambda s, h, name: {'id': name, 'resource': {'type': 'PLAYLIST'}}
S.play_favourite = play_favourite
S.pause = lambda s, g: H.update(playing=False)
S.group_volume = lambda s, g: {'volume': 20}
S.set_volume = lambda s, g, v: None
run.time.sleep = lambda x: None

cfg = schedule.load()
home = dict([s for s in cfg['stores'] if s['id'] == 'home'][0], household='H', group='G')
check(bool(home.get('keep_hand_changes_until_midnight')), 'home keeps hand changes')
check(not any(s.get('keep_hand_changes_until_midnight') for s in cfg['stores'] if s['id'] != 'home'),
      'no shop does: a shop always goes back to the schedule')


def run_at(when, mem):
    store = dict(home, _mem=mem)
    lines, trouble, pending, acted = run.check_store(cfg, store, when, True)
    run.night_ramp(store, schedule.decide(cfg, when, store), when, lines, acted)
    _f, actual = run.levels_now(store)
    hand.remember(mem, actual, H['container'], H['playing'])
    return lines, store


def want_at(when):
    return schedule.decide(cfg, when, home)


# A Monday: daytime 09:00 to 18:00, then the evening.
MORN = datetime(2026, 10, 5, 9, 2)
d = want_at(MORN)
print('--- the morning: split and muted rooms come back, the music starts ---')
house(dict((n, 0) for n in ROOMS), members=['TV Room', 'Bedroom', 'Sunroom'], muted=['Sunroom'],
      playing=False, container='BY A LAKE')
mem, _ = hand.start_day({'day': '2026-10-04', 'held': {'Kitchen': 9}, 'set': {}, 'music': 'BY A LAKE',
                         'playing': False, 'music_held': None, 'paused_held': True,
                         'morning_done': True}, '2026-10-05')
lines, _s = run_at(MORN, mem)
check(('regroup', ['Dressing Room', 'Kitchen']) in H['calls'], 'the Kitchen and Dressing Room rejoin the group')
check(('unmute', 'Sunroom') in H['calls'], 'the muted Sunroom is unmuted for the new day')
check(H['playing'] and H['container'] == d['playlist'], 'yesterday\'s pause is forgotten and the day starts')
check(all(H['levels'][ROOMS[n]] == v for n, v in d['speakers'].items()),
      'every room is at the morning\'s levels, yesterday\'s hand change gone')

print('--- 1: a room turned down by hand stays down ---')
house(dict(d['speakers'], Kitchen=9), container=d['playlist'])
lines, _s = run_at(datetime(2026, 10, 5, 11, 2), mem)
check(H['levels']['P-kit'] == 9 and mem['held'] == {'Kitchen': 9}, 'the Kitchen at 9 is left at 9')
check(not any(c[0] == 'volume' for c in H['calls']), 'nothing else is touched')
check(any('stays there until midnight' in l for l in lines), 'and the run says so')

print('--- 4: at six the untouched rooms move, the Kitchen stays ---')
e = want_at(datetime(2026, 10, 5, 18, 2))
H['calls'] = []
lines, _s = run_at(datetime(2026, 10, 5, 18, 2), mem)
check(H['container'] == e['playlist'], 'the evening music starts')
check(H['levels']['P-kit'] == 9, 'the Kitchen is still 9')
check(all(H['levels'][ROOMS[n]] == v for n, v in e['speakers'].items() if n != 'Kitchen'),
      'every other room is at the evening level')

print('--- 2: music put on by hand stays ---')
H['container'] = 'Something Andrew Chose'
H['calls'] = []
lines, _s = run_at(datetime(2026, 10, 5, 19, 2), mem)
check(H['container'] == 'Something Andrew Chose' and not any(c[0] == 'play' for c in H['calls']),
      'the hand-picked music is not replaced')
lines, _s = run_at(datetime(2026, 10, 5, 20, 17), mem)
check(H['container'] == 'Something Andrew Chose', 'and is still on later in the evening')

print('--- 3: a pause stays off until midnight ---')
mem2, _ = hand.start_day(None, '2026-10-06')
house(dict((n, 0) for n in ROOMS), playing=False, container='BY A LAKE')
run_at(datetime(2026, 10, 6, 9, 2), mem2)
H['playing'] = False
H['calls'] = []
lines, _s = run_at(datetime(2026, 10, 6, 14, 2), mem2)
check(not H['playing'] and mem2['paused_held'], 'paused at two, still off')
lines, _s = run_at(datetime(2026, 10, 6, 18, 2), mem2)
check(not H['playing'], 'still off at six, though the time block changed')

print('--- 5: a Bedroom set by hand skips the walk down ---')
mem3, _ = hand.start_day(None, '2026-10-07')
n = want_at(datetime(2026, 10, 7, 23, 10))
house(dict(n['speakers']), container=n['playlist'])
mem3.update(morning_done=True, set=dict(n['speakers']), music=n['playlist'], playing=True)
H['levels']['P-bed'] = 15
run_at(datetime(2026, 10, 7, 23, 10), mem3)
H['calls'] = []
run_at(datetime(2026, 10, 7, 23, 50), mem3)
check(H['levels']['P-bed'] == 15 and not any(c[:2] == ('volume', 'Bedroom') for c in H['calls']),
      'the Bedroom stays at 15; no walk down')

print('--- the night: every speaker back in the group ---')
house(dict((n, 10) for n in ROOMS), members=['TV Room', 'Bedroom', 'Sunroom'], playing=False)
store = dict(home, _mem=mem3)
lines, *_ = run.check_store(cfg, store, datetime(2026, 10, 8, 0, 17), True)
check(('regroup', ['Dressing Room', 'Kitchen']) in H['calls'], 'a closed run puts split rooms back')
H['calls'] = []
lines, *_ = run.check_store(cfg, store, datetime(2026, 10, 8, 4, 32), True)
check(not any(c[0] == 'regroup' for c in H['calls']), 'and does nothing when the house is already whole')

print('--- a dry run, or no memory, behaves exactly as before ---')
house(dict(d['speakers'], Kitchen=9), container=d['playlist'])
store = dict(home, _mem=None)
lines, *_ = run.check_store(cfg, store, datetime(2026, 10, 5, 11, 2), True)
check(H['levels']['P-kit'] == d['speakers']['Kitchen'], 'with no memory the Kitchen is put back, as it always was')

print()
if failures:
    print('%d FAILURES' % len(failures))
    for f in failures:
        print('   ' + f)
    raise SystemExit(1)
print('All checks passed.')
