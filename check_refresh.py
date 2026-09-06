"""Find out whether Sonos hands back a new permanent pass each time it refreshes.

  python check_refresh.py home

Why this matters: if the pass stays the same, this can run on GitHub's machines with the
pass stored once. If it changes every time, whatever runs it has to save the new one, and
somewhere that can keep a file is simpler.

It backs up the pass first, forces one refresh, and compares. It never prints either pass,
only whether they match.
"""

import hashlib
import json
import os
import shutil
import sys

import sonos


def fingerprint(text):
    """A short stand in for a secret, so two of them can be compared without showing either."""
    return hashlib.sha256((text or '').encode()).hexdigest()[:12]


def main():
    store_id = sys.argv[1] if len(sys.argv) > 1 else 'home'
    path = sonos._token_path(store_id)

    if not os.path.exists(path):
        print('That system has not been connected. Run connect.py first.')
        return 1

    backup = path + '.backup'
    shutil.copy(path, backup)
    print('Backed up to %s, so nothing here can lock you out.' % os.path.basename(backup))
    print()

    before = json.load(open(path, encoding='utf-8'))
    print('permanent pass before: %s' % fingerprint(before.get('refresh_token')))

    # Make the current access look expired so the next call has to refresh.
    before['obtained_at'] = 0
    json.dump(before, open(path, 'w', encoding='utf-8'), indent=2)

    try:
        sonos.access_token(store_id)
    except Exception as e:
        shutil.copy(backup, path)
        print('Refresh failed, and the backup has been put back: %s' % e)
        return 1

    after = json.load(open(path, encoding='utf-8'))
    print('permanent pass after:  %s' % fingerprint(after.get('refresh_token')))
    print()

    same = before.get('refresh_token') == after.get('refresh_token')
    if same:
        print('SAME. The pass does not change.')
        print('GitHub can run this. The pass is stored once and never has to be written back.')
    else:
        print('DIFFERENT. Sonos issues a new pass on every refresh.')
        print('Whatever runs this has to save the new pass each time, so a machine that can')
        print('keep a file is the simpler home for it.')

    # Prove the new state still works.
    try:
        sonos.households(store_id)
        print()
        print('Checked afterwards: the connection still works.')
    except Exception as e:
        shutil.copy(backup, path)
        print()
        print('The connection broke afterwards, backup restored: %s' % e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
