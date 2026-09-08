"""Checks the rule Andrew asked for on 2026-09-07: if he turns the music off
himself, it stays off until the next change of slot.

Nothing here talks to Sonos. It answers in place of Sonos, so every case can be
tried, including the ones that would be hard to arrange in a real room.
"""

import sys
import types
import datetime

STATE = {'playing': False, 'container': None, 'played': [], 'volumes': []}


def fake_sonos():
    m = types.ModuleType('sonos')

    class SonosError(Exception):
        pass

    m.SonosError = SonosError
    m.now_playing = lambda s, g: {'container': {'name': STATE['container']}}
    m.playback_status = lambda s, g: {
        'playbackState': 'PLAYBACK_STATE_PLAYING' if STATE['playing'] else 'PLAYBACK_STATE_PAUSED'}
    m.find_favourite = lambda s, h, n: {'id': 'fav-%s' % n, 'name': n}
    m.play_favourite = lambda s, g, f: STATE['played'].append(f)
    m.pause = lambda s, g: STATE.update(playing=False)
    m.set_volume = lambda s, g, v: STATE['volumes'].append(v)
    m.group_volume = lambda s, g: {'volume': 30}
    m.players = lambda s, h: {'players': []}
    m.player_volume = lambda s, p: {'volume': 30}
    m.set_player_volume = lambda s, p, v: STATE['volumes'].append(v)
    m.groups = lambda s, h: {'groups': []}
    return m


sys.modules['sonos'] = fake_sonos()

import run        # noqa: E402
import schedule   # noqa: E402

fails = []


def check(ok, what):
    print('%s %s' % ('PASS' if ok else 'FAIL', what))
    if not ok:
        fails.append(what)


def home_at(cfg, hour):
    """What home should be playing at a given hour today.

    The two identifiers are filled in here on purpose. On Andrew's own machines they
    come from a file that is deliberately not in the repository, and on GitHub they
    are only handed to the step that actually touches the speakers. A check that
    depended on either would pass on his laptop and fail on GitHub, which is exactly
    what happened the first time this was written.
    """
    when = datetime.datetime(2026, 9, 8, hour, 5)
    store = [s for s in cfg['stores'] if s['id'] == 'home'][0]
    store['household'] = 'Sonos_pretend_household'
    store['group'] = 'RINCON_pretend_group:1'
    return store, when, schedule.decide(cfg, when, store)


def main():
    cfg = schedule.load('config.json')
    store, when, want = home_at(cfg, 11)
    wanted = want['playlist']

    # 1. He stopped it during the slot. The right playlist is still loaded.
    STATE.update(playing=False, container=wanted, played=[], volumes=[])
    lines, trouble, pending, acted = run.check_store(cfg, store, when, True)
    text = '\n'.join(lines)
    check(not STATE['played'], 'it does not start the music again after he stops it')
    check(not trouble, 'and it does not call that a fault')
    check('leaving it off' in text, 'and it says plainly why it did nothing')
    check(not STATE['volumes'], 'and it leaves the volumes exactly where he put them')

    # 1b. He stopped it, and the deck has since dealt a different member of the same
    # slot. Happened for real on the evening of 2026-09-08: the pause was overridden
    # within the minute, because the loaded playlist was compared with the one dealt
    # rather than with the slot's whole list. Run #152 recorded it.
    others = [n for n in want.get('slot_playlists', []) if n != wanted]
    check(bool(others), 'the slot has more than one playlist, so this case can be tried')
    if others:
        STATE.update(playing=False, container=others[0], played=[], volumes=[])
        lines, trouble, pending, acted = run.check_store(cfg, store, when, True)
        text = '\n'.join(lines)
        check(not STATE['played'],
              'a pause holds even when the deal has moved to a different member of the slot')
        check(not STATE['volumes'], 'and the volumes are still left alone')
        check('leaving it off' in text, 'and it still says why')

    # 2. The slot has changed since he stopped it. Something else is loaded.
    STATE.update(playing=False, container='SOMETHING ELSE ENTIRELY', played=[])
    run.check_store(cfg, store, when, True)
    check(bool(STATE['played']), 'it does start again once the slot has moved on')

    # 3. Nothing loaded at all, which is a system that lost its place, not a choice.
    STATE.update(playing=False, container=None, played=[])
    run.check_store(cfg, store, when, True)
    check(bool(STATE['played']), 'it starts again when nothing is loaded at all')

    # 4. Playing the wrong thing is still corrected.
    STATE.update(playing=True, container='SOMETHING ELSE ENTIRELY', played=[])
    run.check_store(cfg, store, when, True)
    check(bool(STATE['played']), 'it still corrects music that is playing but wrong')

    # 5. A shop must never get this behaviour.
    shop = [s for s in cfg['stores'] if s['id'] == 'west-harlem'][0]
    check(not shop.get('leave_off_if_stopped_by_hand'),
          'no shop is set to leave itself off, a silent shop is a fault')

    print()
    if fails:
        print('%d CHECK%s FAILED.' % (len(fails), '' if len(fails) == 1 else 'S'))
        return 1
    print('All checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
</content>