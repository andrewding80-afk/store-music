"""Print the Sonos favourites on a system, exactly as Sonos spells them.

  python favourites.py home

The names printed here are what config.json has to say, character for character.
Reads only. Changes nothing.
"""

import sys
import sonos


def main():
    store_id = sys.argv[1] if len(sys.argv) > 1 else 'home'
    try:
        households = sonos.households(store_id)
    except sonos.SonosError as e:
        print('Could not reach Sonos: %s' % e)
        return 1

    for h in households:
        favs = sonos.favourites(store_id, h['id'])
        if not favs:
            print('No favourites on this system yet.')
            continue
        print('Favourites on %s, %d of them:' % (store_id, len(favs)))
        print()
        for f in favs:
            print('    %s' % f.get('name'))
    print()
    print('Copy these names into config.json exactly as they appear above.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
