"""Starting a playlist must REPLACE what is queued, never add to it.

Found 2026-09-14 at West Harlem. Sonos's loadFavorite adds to the end of the queue
when it is not told otherwise. The job never told it, so every playlist it put on
since the queue was last cleared piled up together, and with shuffle on, each new
song came from a different one of them. It looked like someone changing the music
every few minutes. Sonos documents the default as append.

Nothing here talks to Sonos. It catches the request instead of sending it.
"""

import sys

import sonos

sent = []
sonos._request = lambda url, method='GET', body=None, headers=None: sent.append(body) or {}
sonos._auth_headers = lambda store_id: {}

sonos.play_favourite('west-harlem', 'RINCON_pretend_group:1', 'fav-1')

body = sent[0] if sent else {}
if body.get('action') == 'REPLACE':
    print('PASS starting a playlist replaces the queue')
    sys.exit(0)
print('FAIL starting a playlist replaces the queue: the request carried action=%r'
      % body.get('action'))
sys.exit(1)
