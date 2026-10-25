"""Sunday evenings at home are five points quieter (Andrew, 2026-10-25). No network.

Run:  python test_sunday_home.py
"""

from datetime import datetime
import schedule

cfg = schedule.load()
home = next(s for s in cfg['stores'] if s['id'] == 'home')
failures = []


def check(when, slot, speakers, why):
    d = schedule.decide(cfg, datetime.fromisoformat(when), home)
    got = (d['slot'], {r: d['speakers'][r] for r in speakers})
    ok = got == (slot, speakers)
    if not ok:
        failures.append('%s: expected %r, got %r (%s)' % (when, (slot, speakers), got, why))
    print('PASS' if ok else 'FAIL', when, why)
    return d


sun = check('2026-10-25T19:05', 'Sunday evening', {'Kitchen': 15, 'Bedroom': 13, 'Sunroom': 9, 'TV Room': 0}, 'Sunday evening five below')
check('2026-10-24T19:05', 'Evening', {'Kitchen': 20, 'Bedroom': 18}, 'Saturday evening unchanged')
check('2026-10-26T19:05', 'Evening', {'Kitchen': 20, 'Bedroom': 18}, 'Monday evening unchanged')
check('2026-10-25T23:10', 'Sunday night', {'Bedroom': 7, 'Kitchen': 7}, 'Sunday night five below (tonight is Goodnight Mix: its 12 less 5)')
check('2026-10-25T23:35', 'Sunday night', {'Bedroom': 5}, 'Sunday Bedroom step five below')
check('2026-10-24T23:35', 'Night', {'Bedroom': 10}, 'Saturday Bedroom step unchanged')

# Same deck as Evening, so the night-by-night playlist rotation does not jump.
ev = dict(next(s for s in home['slots'] if s['name'] == 'Sunday evening'))
ev.pop('deck')
ev['name'] = 'Evening'
plain = schedule.deal_from_pool(ev, datetime.fromisoformat('2026-10-25T19:05'))[0]
if plain is not None:
    ok = plain == sun['playlist']
    print('PASS' if ok else 'FAIL', 'Sunday deals the same playlist the Evening deck would')
    if not ok:
        failures.append('deck differs: %r vs %r' % (plain, sun['playlist']))

if failures:
    raise SystemExit('\n'.join(failures))
print('all passed')
