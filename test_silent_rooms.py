"""A speaker that is not making the music is reported, not called correct.

Written 2026-10-05. The home Sunroom sat muted (18 September) and the home Kitchen and
Dressing Room sat in groups of their own for two days (30 September to 2 October), and every
run said "correct". This answers in place of Sonos, so nothing here touches a speaker.
"""
import json

import run
import schedule

failures = []


def check(ok, why):
    if not ok:
        failures.append(why)
    print('%s %s' % ('PASS' if ok else 'FAIL', why))


PLAYERS = [{'id': 'P-left', 'name': 'Dining Room Left Speaker'},
           {'id': 'P-right', 'name': 'Dining Room Right Speaker'}]
STATE = {}


def fake(groups, muted=()):
    STATE['groups'] = groups
    STATE['muted'] = set(muted)


run.sonos.groups = lambda s, h: {'groups': STATE['groups'], 'players': PLAYERS}
run.sonos.player_volume = lambda s, p: {'volume': 30, 'muted': p in STATE['muted']}

store = {'id': 'hells-kitchen', 'household': 'H', 'group': 'G-main'}

print('--- the pair, both in the group and unmuted ---')
fake([{'id': 'G-main', 'playerIds': ['P-left', 'P-right']}])
check(run.rooms_not_in_the_music(store) == [], 'nothing reported when both rooms are in the music')

print('--- one speaker split off into a group of its own ---')
fake([{'id': 'G-main', 'playerIds': ['P-left']}, {'id': 'G-alone', 'playerIds': ['P-right']}])
q = run.rooms_not_in_the_music(store)
check([r for r, _ in q] == ['Dining Room Right Speaker'] and 'left the main group' in q[0][1],
      'a speaker outside the main group is named, and why')

print('--- one speaker muted inside the group ---')
fake([{'id': 'G-main', 'playerIds': ['P-left', 'P-right']}], muted=['P-left'])
q = run.rooms_not_in_the_music(store)
check([r for r, _ in q] == ['Dining Room Left Speaker'] and 'muted' in q[0][1],
      'a muted speaker is named, and why')

print('--- the main group cannot be found ---')
fake([{'id': 'G-other', 'playerIds': ['P-left', 'P-right']}])
check(run.rooms_not_in_the_music(store) == [],
      'no false alarm when the group itself is missing; other checks report that')

print('--- only the shops have it switched on ---')
cfg = schedule.load()
on = dict((s['id'], bool(s.get('report_silent_rooms'))) for s in cfg['stores'])
check(on.get('west-harlem') and on.get('central-harlem') and on.get('hells-kitchen'),
      'all three shops report a silent room')
check(not on.get('home'),
      'home does not, until Andrew rules on leaving hand changes alone')

print()
if failures:
    print('%d FAILURES' % len(failures))
    for f in failures:
        print('   ' + f)
    raise SystemExit(1)
print('All checks passed.')
