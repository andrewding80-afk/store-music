"""Hand changes at home are kept until midnight; each morning everything resets.

Andrew, 2026-10-05, yes to all six:
  1. a room turned up or down by hand stays there until midnight
  2. music picked by hand stays until midnight
  3. a pause stays off until midnight
  4. at a new time block, untouched rooms move and touched rooms stay
  5. a Bedroom changed by hand skips its walk down to silence
  6. a speaker that changes level by itself counts as a hand change
"as long as it resets and regroups speakers for the next morning".

This tests the deciding, which talks to nothing. The run's use of it is tested by
test_hand_run.py.
"""
import hand

failures = []


def check(ok, why):
    if not ok:
        failures.append(why)
    print('%s %s' % ('PASS' if ok else 'FAIL', why))


WANT = {'Bedroom': 18, 'Dressing Room': 18, 'Kitchen': 20, 'Sunroom': 14, 'TV Room': 0}

print('--- a new day starts clean ---')
mem, reset = hand.start_day(None, '2026-10-06')
check(reset and mem['day'] == '2026-10-06' and mem['held'] == {} and not mem['morning_done'],
      'no memory at all is treated as a fresh day, with the morning reset still to do')
old = {'day': '2026-10-05', 'held': {'Kitchen': 9}, 'set': {'Kitchen': 9}, 'music': 'X',
       'playing': True, 'music_held': 'X', 'paused_held': True, 'morning_done': True}
mem, reset = hand.start_day(old, '2026-10-06')
check(reset and mem['held'] == {} and not mem['music_held'] and not mem['paused_held']
      and not mem['morning_done'],
      'after midnight every hand change is forgotten and the morning reset is due')
same, reset = hand.start_day(dict(old, day='2026-10-06'), '2026-10-06')
check(not reset and same['held'] == {'Kitchen': 9}, 'the same day keeps what it knew')

print('--- 1 and 6: a level the job did not set is a hand change ---')
mem = {'day': 'd', 'held': {}, 'set': dict(WANT), 'music': 'M', 'playing': True,
       'music_held': None, 'paused_held': False, 'morning_done': True}
actual = dict(WANT, Kitchen=9)
new = hand.find_hand_levels(mem, actual, WANT)
check(new == ['Kitchen'] and mem['held'] == {'Kitchen': 9}, 'the Kitchen turned down to 9 is held at 9')
actual = dict(WANT, Kitchen=0)
mem['held'] = {}
hand.find_hand_levels(mem, actual, WANT)
check(mem['held'] == {'Kitchen': 0}, 'a speaker that went to 0 by itself is held too (answer 6)')

print('--- not a hand change ---')
mem['held'] = {}
check(hand.find_hand_levels(mem, dict(WANT), WANT) == [] and mem['held'] == {},
      'levels exactly where the job left them are not held')
mem2 = dict(mem, set=dict(WANT, Kitchen=28), held={})
check(hand.find_hand_levels(mem2, dict(WANT, Kitchen=28), WANT) == [],
      'a new time block: the job has not moved the room yet, so it is not held')
mem3 = dict(mem, set=dict(WANT, Kitchen=28), held={})
check(hand.find_hand_levels(mem3, dict(WANT), WANT) == [],
      'a level that already matches the schedule is never held, even if the memory missed it')
mem4 = dict(mem, set={}, held={})
check(hand.find_hand_levels(mem4, dict(WANT, Kitchen=9), WANT) == [],
      'with nothing remembered for a room there is no evidence, so it is not held')

print('--- 4: at a new time block only the touched rooms stay ---')
mem = dict(mem, held={'Kitchen': 9})
EVENING = dict(WANT, Bedroom=22)
levels = hand.levels_to_set(mem, EVENING)
check('Kitchen' not in levels and levels.get('Bedroom') == 22,
      'the held Kitchen is left out; the Bedroom moves to the new level')

print('--- 2: music picked by hand ---')
mem = {'day': 'd', 'held': {}, 'set': {}, 'music': 'Classical Romance', 'playing': True,
       'music_held': None, 'paused_held': False, 'morning_done': True}
hand.find_hand_music(mem, 'Some Spotify Thing', True, 'Classical Romance')
check(mem['music_held'] == 'Some Spotify Thing', 'a playlist the job did not start is held')
mem['music_held'] = None
hand.find_hand_music(mem, 'Classical Romance', True, 'Julie London Radio')
check(mem['music_held'] is None,
      'the job\'s own playlist still on at a new time block is not a hand pick')
mem['music_held'] = None
mem['music'] = None
hand.find_hand_music(mem, 'Some Spotify Thing', True, 'Classical Romance')
check(mem['music_held'] is None, 'with no memory of the job\'s music there is no evidence')

print('--- 3: a pause ---')
mem = {'day': 'd', 'held': {}, 'set': {}, 'music': 'Classical Romance', 'playing': True,
       'music_held': None, 'paused_held': False, 'morning_done': True}
hand.find_hand_music(mem, 'Classical Romance', False, 'Classical Romance')
check(mem['paused_held'], 'music the job left playing, now paused, is held off')
mem = dict(mem, playing=False, paused_held=False)
hand.find_hand_music(mem, 'Classical Romance', False, 'Classical Romance')
check(not mem['paused_held'], 'music that was already stopped last time is not a new pause')

print('--- 5: the Bedroom walk down ---')
check(hand.skip_ramp({'held': {'Bedroom': 15}}, 'Bedroom'), 'a Bedroom held by hand skips the walk down')
check(not hand.skip_ramp({'held': {'Kitchen': 9}}, 'Bedroom'), 'otherwise the walk down happens')
check(not hand.skip_ramp(None, 'Bedroom'), 'with no memory the walk down happens as it always did')

print('--- remembering what the job left ---')
mem = {'day': 'd', 'held': {'Kitchen': 9}, 'set': {}, 'music': None, 'playing': False,
       'music_held': None, 'paused_held': False, 'morning_done': True}
hand.remember(mem, dict(WANT, Kitchen=9), 'Julie London Radio', True)
check(mem['set']['Kitchen'] == 9 and mem['set']['Bedroom'] == 18 and mem['music'] == 'Julie London Radio'
      and mem['playing'], 'the end of each run records the levels and music as they are')

print()
if failures:
    print('%d FAILURES' % len(failures))
    for f in failures:
        print('   ' + f)
    raise SystemExit(1)
print('All checks passed.')
