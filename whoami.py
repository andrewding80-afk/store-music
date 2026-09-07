"""What can this saved sign-in actually see?

  python whoami.py west-harlem

Prints every Sonos system that sign-in reaches, its speakers and its favourites.
Written 2026-09-07 because a sign-in was saved without it being clear whose it was.
"""

import sys
import sonos


def main():
    if len(sys.argv) < 2:
        print('Which one? For example:  python whoami.py west-harlem')
        return 1
    store_id = sys.argv[1]

    # Ask the raw question and show the raw answer. An earlier version only showed the
    # tidied list, so "no systems" and "an answer we did not understand" looked
    # identical, and they are not the same thing at all.
    try:
        raw = sonos._request('%s/households' % sonos.API,
                             headers=sonos._auth_headers(store_id))
    except Exception as e:
        print('COULD NOT ASK SONOS: %s' % e)
        print('The saved sign-in for %r may be missing or expired. Run connect.py again.'
              % store_id)
        return 1

    import json as _json
    print('Sonos answered, word for word:')
    print(_json.dumps(raw, indent=2)[:1500])
    print()

    found = raw.get('households', [])

    if not found:
        print('THIS SIGN-IN HAS NO SONOS SYSTEMS ON IT AT ALL.')
        print('It worked, but the account you signed in as owns no speakers.')
        print('That means it is the wrong account. Run connect.py again and sign in as a')
        print('different one. Signing out of Sonos in that browser window first is the')
        print('only way to be asked who you are.')
        return 1

    print('This sign-in reaches %d system%s.'
          % (len(found), '' if len(found) == 1 else 's'))
    print()
    for hh in found:
        print('SYSTEM  %s' % hh['id'])
        try:
            groups = sonos.groups(store_id, hh['id']).get('groups', [])
        except Exception as e:
            print('  could not list the speakers: %s' % e)
            groups = []
        for g in groups:
            print('  group   %-30s  %s' % (g.get('name'), g.get('id')))
        print()
        print('  playlists and stations already saved on this system:')
        try:
            favs = sonos.favourites(store_id, hh['id'])
        except Exception as e:
            print('    could not list them: %s' % e)
            favs = []
        if not favs:
            print('    none at all')
        for f in favs:
            print('    %s' % f.get('name'))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
