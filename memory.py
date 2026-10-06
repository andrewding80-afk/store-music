"""The job's memory between runs, kept as one small file on the 'status' branch.

Added 2026-10-05 for hand changes at home (hand.py). The job runs on GitHub's machines,
which keep nothing between runs, so the memory lives beside status.json and is read and
written through GitHub's contents API with the run's own token.

It must never break the music. Every failure is swallowed: a memory that cannot be read
comes back as None, and run.py then behaves exactly as it did before memory existed.
"""
import base64
import json
import os
import urllib.error
import urllib.request

REPO = os.environ.get('GITHUB_REPOSITORY', 'andrewding80-afk/store-music')
BRANCH = 'status'
PATH = 'home-memory.json'
API = 'https://api.github.com/repos/%s/contents/%s' % (REPO, PATH)


def _request(url, token, method='GET', body=None):
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body else None)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Accept', 'application/vnd.github+json')
    if body:
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read() or b'{}')


def load():
    """Returns (memory for every store, sha, a note). Memory is None when it cannot be read."""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        return None, None, 'no token here, so no memory: hand changes are not tracked this run'
    try:
        got = _request('%s?ref=%s' % (API, BRANCH), token)
        return json.loads(base64.b64decode(got.get('content', '')).decode()), got.get('sha'), None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}, None, None            # first run: an empty memory is a real answer
        return None, None, 'memory could not be read (%s)' % e.code
    except Exception as e:
        return None, None, 'memory could not be read (%s)' % str(e)[:80]


def save(data, sha):
    """Write the memory. Returns a note when it fails, None when it worked."""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        return None
    body = {'message': 'memory: hand changes at home',
            'content': base64.b64encode((json.dumps(data, indent=2, sort_keys=True) + '\n').encode()).decode(),
            'branch': BRANCH}
    if sha:
        body['sha'] = sha
    try:
        _request(API, token, method='PUT', body=body)
        return None
    except Exception as e:
        return 'memory could not be saved (%s); the next run falls back to the old behaviour' % str(e)[:80]
