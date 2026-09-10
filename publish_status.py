"""Publish what the last run found, so it can be read without opening GitHub.

Written 2026-09-10. run.py already detects the failures that matter, including a store
that is switched on but unreachable, which it deliberately treats as a fault rather than
a shrug. The problem was never detection. It was that the report went to the Actions
summary page, which Andrew does not see, so a job could fail quietly for days.

This writes the verdict to status.json on the 'status' branch, which is machine-written
and separate so main keeps only Andrew's work.

It commits only when the verdict CHANGES, or when the last write is over 20 hours old.
The daily write is what makes silence meaningful: a status file older than a day means
the job has stopped running, which no amount of change-detection alone would show.

⚠️ This must never break the music. Every failure here is swallowed and the exit code is
always 0. A heartbeat that can stop the thing it watches is worse than no heartbeat.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

REPO = os.environ.get('GITHUB_REPOSITORY', 'andrewding80-afk/store-music')
BRANCH = 'status'
PATH = 'status.json'
API = 'https://api.github.com/repos/%s/contents/%s' % (REPO, PATH)
STALE_AFTER = 20 * 3600          # write at least this often, so silence means stopped
UNREACHABLE = re.compile(r'^\s*(.*?)\s*$')


def read_run_output(path='run-output.txt'):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''


def verdict_from(text):
    """The Result: line run.py prints last, and any store it could not reach."""
    result = ''
    for line in text.splitlines():
        if line.startswith('Result: '):
            result = line[len('Result: '):].strip()
    unreachable = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if 'SWITCHED ON BUT NOT REACHABLE' in line:
            # the store's name is the nearest preceding line that is not indented
            for j in range(i - 1, -1, -1):
                if lines[j].strip() and not lines[j].startswith('    '):
                    unreachable.append(lines[j].strip())
                    break
    return result, unreachable


def build(text, exit_code):
    result, unreachable = verdict_from(text)
    # No Result: line means the run did not reach its own ending. Treating that as
    # healthy is the exact failure this file exists to catch: silence that looks fine.
    # Caught by its own test on 2026-09-10, before it ever ran.
    return {
        'ok': bool(result) and exit_code == 0 and 'NEEDS ATTENTION' not in result,
        'result': result or 'the run said nothing, which is itself wrong',
        'stores_switched_on_but_unreachable': unreachable,
        'run': os.environ.get('GITHUB_RUN_NUMBER', ''),
        'run_url': '%s/%s/actions/runs/%s' % (
            'https://github.com', REPO, os.environ.get('GITHUB_RUN_ID', '')),
    }


def meaningful(status):
    """Everything except the parts that change on every run regardless of health."""
    return {k: v for k, v in status.items() if k not in ('written_at', 'run', 'run_url')}


def _request(url, token, method='GET', body=None):
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body else None)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Accept', 'application/vnd.github+json')
    if body:
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read() or b'{}')


def main():
    token = os.environ.get('GITHUB_TOKEN', '')
    if not token:
        print('status: no token, nothing published')
        return
    text = read_run_output()
    try:
        exit_code = int(os.environ.get('RUN_EXIT_CODE', '0'))
    except ValueError:
        exit_code = 0
    status = build(text, exit_code)

    existing, sha = None, None
    try:
        current = _request('%s?ref=%s' % (API, BRANCH), token)
        sha = current.get('sha')
        import base64
        existing = json.loads(base64.b64decode(current.get('content', '')).decode())
    except Exception:
        pass

    now = int(time.time())
    if existing:
        unchanged = meaningful(existing) == meaningful(status)
        last = existing.get('written_at_epoch') or 0
        if unchanged and (now - last) < STALE_AFTER:
            print('status: unchanged and written recently, nothing to publish')
            return

    status['written_at'] = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(now))
    status['written_at_epoch'] = now
    import base64
    body = {
        'message': 'status: %s' % status['result'][:60],
        'content': base64.b64encode(
            (json.dumps(status, indent=2) + '\n').encode()).decode(),
        'branch': BRANCH,
    }
    if sha:
        body['sha'] = sha
    _request(API, token, method='PUT', body=body)
    print('status: published -> %s' % status['result'])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:                      # never break the music
        print('status: could not publish (%s). The run itself is unaffected.' % exc)
    sys.exit(0)
