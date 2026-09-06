"""List the individual speakers on a system, and what each one's volume is right now.

  python speakers.py home

Reads only. Changes nothing. The names printed here are what you would use to set a
speaker's own level, separately from the volume of the group as a whole.
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
        data = sonos.groups(store_id, h['id'])

        print('Groups on this system:')
        for g in data.get('groups', []):
            print('    %-30s %d speaker(s)' % (g.get('name'), len(g.get('playerIds') or [])))
        print()

        players = data.get('players', [])
        print('Individual speakers, %d of them:' % len(players))
        print()
        for p in players:
            name = p.get('name')
            pid = p.get('id')
            try:
                v = sonos.player_volume(store_id, pid)
                level = v.get('volume')
                muted = ' MUTED' if v.get('muted') else ''
                print('    %-28s volume %s%s' % (name, level, muted))
            except sonos.SonosError as e:
                print('    %-28s could not read its volume: %s' % (name, e))
    print()
    print('If a volume is shown for each speaker above, setting them separately will work.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
