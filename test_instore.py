"""Checks for the in-shop setup kit, run without talking to Sonos at all.

The part worth guarding is which playlist names a shop is told it must have.
Get that wrong and somebody stands in a shop adding the wrong things, or leaves
thinking it is finished when it is not.
"""

import io
import sys
import types

FAVS = []


def fake_sonos():
    m = types.ModuleType('sonos')
    m.SonosError = Exception
    m.households = lambda s: [{'id': 'HH1'}]
    m.groups = lambda s, h: {'groups': [{'name': 'Dining Room', 'id': 'G1'}]}
    m.players = lambda s, h: {'players': [{'name': 'Dining Room', 'id': 'P1'}]}
    m.favourites = lambda s, h: FAVS
    m.find_favourite = lambda s, h, n: next((f for f in FAVS if f['name'] == n), None)
    return m


sys.modules['sonos'] = fake_sonos()

import instore      # noqa: E402
import schedule     # noqa: E402

fails = []


def check(ok, what):
    print('%s %s' % ('PASS' if ok else 'FAIL', what))
    if not ok:
        fails.append(what)


def run_check_mode(store_id):
    sys.argv = ['instore.py', store_id, '--check']
    buf = io.StringIO()
    real = sys.stdout
    sys.stdout = buf
    try:
        code = instore.main()
    finally:
        sys.stdout = real
    return code, buf.getvalue()


def main():
    cfg = schedule.load('config.json')
    shop = [s for s in cfg['stores'] if s['id'] == 'west-harlem'][0]
    home = [s for s in cfg['stores'] if s['id'] == 'home'][0]

    today = instore.wanted_playlists(cfg, shop)
    everything = instore.wanted_playlists(cfg, shop, everything=True)

    check('Jazz Trumpet' in today,
          'a shop is asked for the playlist its lunch slot actually plays')
    check(not any(n.startswith('NEEDS ') for n in everything),
          'a slot with no playlist chosen yet is never asked for')
    check(all('December' not in n for n in today),
          'Christmas playlists do not hold up a visit in September')
    check(any('December' in n for n in everything),
          'Christmas playlists are still listed as due later')

    home_today = instore.wanted_playlists(cfg, home)
    check('BACH' in home_today, 'home is asked for the stations its own day uses')
    check(all('Jazz Trumpet' not in n for n in home_today),
          'home is never asked for the shop playlists')
    # From 2026-09-10 home has its OWN December, because Andrew asked for home to follow
    # the same 50/50 rule as the shops. What must still never happen is a SHOP's playlist
    # turning up on home's list, which is what this always guarded.
    shop_xmas = set()
    for block in cfg.get('holidays', []):
        for value in (block.get('overrides') or {}).values():
            shop_xmas.update(value if isinstance(value, list) else [value])
    home_everything = instore.wanted_playlists(cfg, home, everything=True)
    check(not (set(home_everything) & shop_xmas),
          'a shop playlist never follows home around')
    check(any('December' in n for n in home_everything),
          "home's own December playlist is listed as due later")

    FAVS[:] = []
    code, out = run_check_mode('west-harlem')
    check(code == 2 and 'STILL MISSING' in out,
          'an empty shop is reported as not ready')

    FAVS[:] = [{'name': n, 'id': str(i)} for i, n in enumerate(today)]
    code, out = run_check_mode('west-harlem')
    check(code == 0 and 'NOTHING MISSING' in out,
          'a shop holding every everyday playlist is reported as ready')

    print()
    if fails:
        print('%d CHECK%s FAILED.' % (len(fails), '' if len(fails) == 1 else 'S'))
        return 1
    print('All checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
