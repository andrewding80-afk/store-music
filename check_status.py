"""Read what the music job last said, and decide whether it is worth troubling Andrew.

Written 2026-09-10. Runs on the Mac mini, not on GitHub. The job publishes every real
change to the 'status' branch; this decides what is worth saying out loud.

The damping is here on purpose, and the reason is in in-store-music.md: a speaker at
home left and rejoined its group three times in four minutes, one missing speaker must
never raise an alarm, and an alarm that is usually wrong is worse than no alarm. So a
single bad run says nothing. A fault has to persist.

Three things it can conclude:

  OK        the last verdict is good, and it was written recently enough
  STALE     nothing has been written for over a day, so the job has stopped running
  FAULT     the same fault has persisted across several published verdicts

Exit code 0 means nothing to say. 1 means say it.
"""
import json
import subprocess
import sys
import time

REPO = '/Users/andrewding/Documents/store-music'
BRANCH = 'status'
STALE_AFTER = 30 * 3600          # the job writes at least daily, so a day and a bit
NEEDS_TO_PERSIST = 3             # published verdicts in a row before it counts


def git(*args):
    return subprocess.run(['git', '-C', REPO] + list(args),
                          capture_output=True, text=True, timeout=60).stdout


def latest_status():
    git('fetch', '--quiet', 'origin', BRANCH)
    raw = git('show', 'origin/%s:status.json' % BRANCH)
    try:
        return json.loads(raw)
    except Exception:
        return None


def published_verdicts(limit=12):
    """The recent published states, newest first, from the branch's own history."""
    out = git('log', '--format=%H', '-n', str(limit), 'origin/%s' % BRANCH)
    verdicts = []
    for sha in out.split():
        raw = git('show', '%s:status.json' % sha)
        try:
            verdicts.append(json.loads(raw))
        except Exception:
            continue
    return verdicts


def decide():
    now = int(time.time())
    status = latest_status()
    if status is None:
        return 'FAULT', 'The status file could not be read at all.'
    if status.get('written_at') is None:
        return 'OK', 'Waiting for the first real run to publish. Nothing wrong yet.'

    age = now - (status.get('written_at_epoch') or 0)
    if age > STALE_AFTER:
        return 'STALE', (
            'The music job has not reported for %d hours. It writes at least once a '
            'day, so this means it has stopped running, not that nothing changed. '
            'Last thing it said: %s' % (age // 3600, status.get('result')))

    if status.get('ok'):
        return 'OK', status.get('result', '')

    recent = published_verdicts()
    bad_in_a_row = 0
    for v in recent:
        if v.get('ok') is False:
            bad_in_a_row += 1
        else:
            break
    if bad_in_a_row < NEEDS_TO_PERSIST:
        return 'OK', (
            'One bad run, not yet enough to mean anything. %d of the last %d published '
            'verdicts were bad. Staying quiet.' % (bad_in_a_row, NEEDS_TO_PERSIST))

    unreachable = status.get('stores_switched_on_but_unreachable') or []
    detail = status.get('result', '')
    if unreachable:
        detail += '. Switched on but unreachable: ' + ', '.join(unreachable)
    return 'FAULT', (
        'The music job has reported the same fault %d times running, so this is not a '
        'speaker flapping. %s' % (bad_in_a_row, detail))


def main():
    state, message = decide()
    print('%s: %s' % (state, message))
    if state == 'OK':
        return 0
    status = latest_status() or {}
    tail = status.get('output_tail') or ''
    if tail:
        # What the run actually said. Added after run 326 on 2026-09-10 reported a
        # fault and carried no reason with it, which made the report true and useless.
        print()
        print('What the run itself said:')
        for line in tail.splitlines():
            print('  ' + line)
    print()
    print('The run it came from: %s' % status.get('run_url', ''))
    return 1


if __name__ == '__main__':
    sys.exit(main())
