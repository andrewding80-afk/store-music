"""One store failing must never take the music off in the others.

Written 2026-09-10. A bad household id used to crash the whole run inside
find_favourite, so a single mistyped identifier would have silenced all four shops and
the run would have ended with a stack trace instead of a report.

The obvious test, feeding a bad household to a real run, does not reach the crash: the
favourite is only looked up when the music needs changing, so a store already playing
the right thing sails past it. This forces the failure instead, which is the only way
to keep proving it.
"""
import io
import sys
import contextlib

import run

failures = []

print('--- one store failing must not stop the others ---')

real_check = run.check_store
calls = []


def explode_on_one(cfg, store, now, live):
    calls.append(store['id'])
    if store['id'] == 'west-harlem':
        raise RuntimeError('pretend the household id is wrong')
    return (['  %s' % store['name'], '    fine'], False, False, [])


run.check_store = explode_on_one
buf = io.StringIO()
code = None
_argv = sys.argv
sys.argv = ['run.py']          # a dry run: main reads sys.argv, and takes no arguments
try:
    with contextlib.redirect_stdout(buf):
        code = run.main()
except SystemExit as e:
    code = e.code
except Exception as exc:
    failures.append('the run died instead of containing the failure: %r' % exc)
finally:
    run.check_store = real_check
    sys.argv = _argv

out = buf.getvalue()

ok_survived = not failures
print('%s the run finished instead of crashing' % ('PASS' if ok_survived else 'FAIL'))

ok_all_seen = len(calls) >= 4
if not ok_all_seen:
    failures.append('only %d stores were checked, the loop stopped early: %s' % (len(calls), calls))
print('%s every store was still checked (%d)' % ('PASS' if ok_all_seen else 'FAIL', len(calls)))

ok_named = 'THIS STORE COULD NOT BE CHECKED AT ALL' in out
if not ok_named:
    failures.append('the broken store was not named in the output')
print('%s the broken store is named rather than silently skipped' % ('PASS' if ok_named else 'FAIL'))

ok_others = out.count('    fine') >= 3
if not ok_others:
    failures.append('the other stores were not reported: %r' % out[:300])
print('%s the other three were checked normally' % ('PASS' if ok_others else 'FAIL'))

ok_trouble = code == 1
if not ok_trouble:
    failures.append('a store that could not be checked did not count as trouble (exit %r)' % code)
print('%s it counts as trouble, so the heartbeat reports it' % ('PASS' if ok_trouble else 'FAIL'))

print()
if failures:
    for f in failures:
        print('FAILURE: %s' % f)
    sys.exit(1)
print('all good')
