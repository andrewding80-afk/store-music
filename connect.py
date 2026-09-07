"""Connect one Sonos system. Run once per store, then never again for that store.

  python connect.py home

Opens a browser, you sign in and approve, and it saves a token for that store only.
Connecting a second store cannot disturb the first, because each has its own file.
"""

import http.server
import sys
import threading
import urllib.parse

import sonos

PORT = 8765
REDIRECT = 'http://localhost:%d/callback' % PORT

_code = {}


class Catcher(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parts = urllib.parse.urlparse(self.path)
        if parts.path != '/callback':
            self.send_response(404)
            self.end_headers()
            return
        q = urllib.parse.parse_qs(parts.query)
        _code['value'] = q.get('code', [None])[0]
        _code['error'] = q.get('error', [None])[0]
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        if _code['value']:
            self.wfile.write(b'<h2>Connected. You can close this tab and go back.</h2>')
        else:
            self.wfile.write(b'<h2>Something went wrong. Check the terminal.</h2>')

    def log_message(self, *a):
        pass  # keep the terminal readable


def main():
    if len(sys.argv) < 2:
        print('Which store? For example:  python connect.py home')
        print('The name must match an "id" in config.json.')
        return 1
    store_id = sys.argv[1]

    try:
        url = sonos.authorise_url(REDIRECT)
    except sonos.SonosError as e:
        print(e)
        return 1

    server = http.server.HTTPServer(('localhost', PORT), Catcher)
    threading.Thread(target=server.handle_request, daemon=True).start()

    # This used to open the browser by itself, and that was the bug. It opened the
    # ordinary browser, which was already signed in to Sonos, so that window approved
    # silently before Andrew had finished with the private one. Whichever tab arrived
    # first won, and it was never the one he was looking at. Now nothing opens on its
    # own and the only approval that can happen is the one he does deliberately.
    print()
    print('Copy the link below and paste it into the window you want to sign in from.')
    print('Nothing will open by itself.')
    print()
    print('  %s' % url)
    print()

    print('Waiting for you to approve...')
    for _ in range(300):
        if _code:
            break
        import time
        time.sleep(1)

    if not _code.get('value'):
        print('No approval came back. %s' % (_code.get('error') or 'Timed out after five minutes.'))
        return 1

    sonos.exchange_code(store_id, _code['value'], REDIRECT)
    print('Saved. Now finding the speakers on this system.')
    print()

    for hh in sonos.households(store_id):
        print('  household id: %s' % hh['id'])
        g = sonos.groups(store_id, hh['id'])
        for grp in g.get('groups', []):
            print('    group: %-28s id: %s' % (grp.get('name'), grp.get('id')))
        print()
        print('  favourites on this system:')
        for fav in sonos.favourites(store_id, hh['id']):
            print('    %s' % fav.get('name'))

    print()
    print('Copy the household id and the group id you want into config.json for %r.' % store_id)
    return 0


if __name__ == '__main__':
    sys.exit(main())
