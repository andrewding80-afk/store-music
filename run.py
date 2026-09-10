"""Work out what should be playing at every store, and make it so.

DRY RUN IS THE DEFAULT. It tells you what it would do and changes nothing.
To actually act:   python run.py --live

Adding a store is one entry in config.json plus one run of connect.py. Nothing in this
file mentions a particular store.
"""

import argparse
import sys
import time
from datetime import datetime

import schedule
import sonos



# How gently the music stops at the end of the night. Sonos has no fade of its own, so
# this does it by hand: the level comes down in small steps and only then does the music
# stop. Andrew asked for this on 2026-09-06 because a sudden cut is jarring at midnight.
FADE_SECONDS = 30
FADE_STEPS = 10


def fade_out(store, lines):
    """Bring the volume down gently. Returns what each speaker was at, to put back after."""
    try:
        found = sonos.players(store['id'], store['household'])
    except sonos.SonosError:
        found = {}

    if not found:
        # A system with no speaker by speaker control. Fade the whole group instead.
        start = sonos.group_volume(store['id'], store['group']).get('volume') or 0
        if start <= 0:
            return {}
        for step in range(FADE_STEPS - 1, 0, -1):
            sonos.set_volume(store['id'], store['group'],
                             int(round(start * step / float(FADE_STEPS))))
            time.sleep(FADE_SECONDS / float(FADE_STEPS))
        sonos.set_volume(store['id'], store['group'], 0)
        lines.append('    faded down from %s to nothing over about %d seconds'
                     % (start, FADE_SECONDS))
        return {'the whole group': (None, start)}

    was = {}
    for name, player_id in found.items():
        level = sonos.player_volume(store['id'], player_id).get('volume') or 0
        if level > 0:
            was[name] = (player_id, level)
    if not was:
        return {}

    for step in range(FADE_STEPS - 1, 0, -1):
        for player_id, level in was.values():
            sonos.set_player_volume(store['id'], player_id,
                                    int(round(level * step / float(FADE_STEPS))))
        time.sleep(FADE_SECONDS / float(FADE_STEPS))
    for player_id, level in was.values():
        sonos.set_player_volume(store['id'], player_id, 0)

    lines.append('    faded down over about %d seconds: %s'
                 % (FADE_SECONDS,
                    ', '.join('%s from %s' % (n, l) for n, (_, l) in sorted(was.items()))))
    return was


def restore_levels(store, was, lines):
    """Put the volume back now the music has stopped.

    Left at nothing, anyone pressing play in the middle of the night would get silence
    and think something was broken.
    """
    if not was:
        return
    for name, (player_id, level) in was.items():
        if player_id is None:
            sonos.set_volume(store['id'], store['group'], level)
        else:
            sonos.set_player_volume(store['id'], player_id, level)
    lines.append('    volume put back where it was, ready for the morning')


def wanted_levels(store, want, found):
    """What every speaker on this system should be set to.

    Speakers named in config.json get their own number. Every other speaker gets the
    slot volume, so none is ever left sitting at last night's level.
    """
    named = want.get('speakers') or {}
    return dict((name, named.get(name, want['volume'])) for name in found)


def reconcile_volume(store, want, live, lines, acted):
    """Get the volume right, whatever the music is doing.

    This is deliberately separate from the playlist. An earlier version only set the
    volume as a side effect of changing the music, so when the right playlist was
    already playing the volume was never touched at all. A wrong volume with the right
    music is still wrong.

    Returns (trouble, pending).
    """
    trouble = False
    pending = False

    # One level per speaker.
    if want.get('speakers'):
        found = sonos.players(store['id'], store['household'])

        # Sonos sometimes answers with an incomplete list of speakers for a few seconds,
        # and a speaker that has simply gone quiet on the network reappears on its own.
        # Seen on the very first night of testing: the Bedroom vanished from one call and
        # was back in the next. So ask twice before saying anything is wrong. A job that
        # raises a false alarm now and then is a job that stops being read.
        missing = sorted(n for n in want['speakers'] if n not in found)
        if missing:
            time.sleep(3)
            found = sonos.players(store['id'], store['household'])
            still_missing = sorted(n for n in want['speakers'] if n not in found)
            if not still_missing:
                lines.append('    (%s did not answer the first time and answered the '
                             'second. Not treating that as a fault.)' % ', '.join(missing))
            missing = still_missing

        if missing:
            lines.append('    speakers Sonos returned this time: %s'
                         % (', '.join(sorted(found)) or 'none at all'))
        for name in missing:
            lines.append('    NOTE: no speaker named %r answered, so nothing was set for '
                         'it. Sonos loses track of a speaker now and then and it comes '
                         'back on its own. Worth looking at only if it says this every '
                         'time for days.' % name)

        should = wanted_levels(store, want, found)
        wrong = []
        for name, player_id in sorted(found.items()):
            now_at = sonos.player_volume(store['id'], player_id).get('volume')
            if now_at != should[name]:
                wrong.append((name, player_id, now_at, should[name]))

        if not wrong:
            lines.append('    volume: all %d speakers already correct' % len(found))
            return trouble, pending

        for name, player_id, now_at, target in wrong:
            if live:
                sonos.set_player_volume(store['id'], player_id, target)
                lines.append('    volume: %s %s -> %s' % (name, now_at, target))
                acted.append('%s volume %s to %s' % (name, now_at, target))
            else:
                lines.append('    volume: %s is %s, WOULD set %s   (dry run, nothing done)'
                             % (name, now_at, target))
                pending = True
        return trouble, pending

    # One level for the whole group.
    now_at = sonos.group_volume(store['id'], store['group']).get('volume')
    if now_at == want['volume']:
        lines.append('    volume: already %s' % now_at)
        return trouble, pending

    if live:
        sonos.set_volume(store['id'], store['group'], want['volume'])
        lines.append('    volume: %s -> %s' % (now_at, want['volume']))
        acted.append('volume %s to %s' % (now_at, want['volume']))
    else:
        lines.append('    volume: is %s, WOULD set %s   (dry run, nothing done)'
                     % (now_at, want['volume']))
        pending = True
    return trouble, pending


def check_store(cfg, store, now, live):
    """Returns the lines to report, whether anything needs attention, and whether a
    change is outstanding.

    Those last two are different things. A store playing the wrong playlist is not a
    fault, it is simply something still to do. A store that is silent during service is
    a fault. The summary line must not blur them.

    The music and the volume are checked separately and either can be wrong on its own.
    """
    lines = []
    acted = []          # what was actually changed, so a silent run cannot look like a busy one
    trouble = False
    pending = False
    label = store['name']

    want = schedule.decide(cfg, now, store)

    if want['needs_attention']:
        lines.append('  ATTENTION  %s' % want['needs_attention'])
        return lines, True, pending, acted

    if not want['playing']:
        lines.append('  %s: closed, nothing should be playing' % label)

        # Whether to actually stop it is a per system choice, and the default is to
        # leave it alone. The shops go quiet at closing. Home does too, from midnight
        # until the nine in the morning start, because Andrew asked for the house to be
        # put to bed. The cost of that choice: music he starts himself after midnight
        # gets stopped at the next check, within fifteen minutes.
        if not store.get('stop_when_closed'):
            return lines, trouble, pending, acted
        if schedule.not_connected(store):
            return lines, trouble, pending, acted

        try:
            state = sonos.playback_status(store['id'], store['group'])
        except sonos.SonosError as e:
            lines.append('    COULD NOT REACH SONOS: %s' % e)
            return lines, True, pending, acted

        if state.get('playbackState') != 'PLAYBACK_STATE_PLAYING':
            lines.append('    already quiet')
            return lines, trouble, pending, acted

        if not live:
            lines.append('    WOULD fade it down over %d seconds and stop it   (dry run, nothing done)' % FADE_SECONDS)
            return lines, trouble, True, acted

        try:
            was = fade_out(store, lines)
            sonos.pause(store['id'], store['group'])
            lines.append('    stopped it')
            acted.append('stopped the music, outside hours')
            restore_levels(store, was, lines)
        except sonos.SonosError as e:
            lines.append('    FAILED to stop it: %s' % e)
            trouble = True
        return lines, trouble, pending, acted

    lines.append('  %s' % label)
    lines.append('    should be: %s  at volume %s   (%s)'
                 % (want['playlist'], want['volume'], want['reason']))
    if want.get('speakers'):
        lines.append('    each speaker: %s'
                     % ', '.join('%s %s' % (n, v)
                                 for n, v in sorted(want['speakers'].items())))

    if schedule.not_connected(store):
        # Switched on, but its identifiers are not visible here. That is a fault, not a
        # shrug: it means the job cannot touch these speakers and nobody would know.
        # This silence is exactly what hid a missing setting on 2026-09-06.
        lines.append('    SWITCHED ON BUT NOT REACHABLE. Its household and speaker group '
                     'are not set here. Either it has not been connected yet, or the two '
                     'values are in GitHub and are not being passed to the job.')
        return lines, True, pending, acted

    try:
        playing = sonos.now_playing(store['id'], store['group'])
        state = sonos.playback_status(store['id'], store['group'])
    except sonos.SonosError as e:
        lines.append('    COULD NOT REACH SONOS: %s' % e)
        return lines, True, pending, acted

    container = (playing.get('container') or {}).get('name')
    is_playing = state.get('playbackState') == 'PLAYBACK_STATE_PLAYING'
    lines.append('    actually: %s  (%s)' % (container or 'nothing',
                                             'playing' if is_playing else 'not playing'))

    # ---- did he turn it off himself? ----
    #
    # Asked for by Andrew 2026-09-07: if he stops the music, it should stay stopped.
    # Until now the next check started it again within fifteen minutes.
    #
    # There is no memory between runs and none is needed. This job never leaves a
    # system paused in the middle of a slot, it only stops things at closing time. So
    # paused, with music belonging to this slot still loaded, can only have been a
    # person. And when the slot changes, the loaded playlist belongs to the old slot
    # rather than the new one, so the music starts again on its own. Off means off
    # until the next change of slot, and nothing has to be remembered or cleared.
    # That recovery relies on no two home slots sharing a playlist, which is true and
    # is cheap to keep true.
    #
    # Belonging means any member of the slot's list, not only the one dealt for this
    # moment. The first version compared with the single dealt pick, and on the
    # evening of 2026-09-08 a pause at home was overridden within the minute because
    # the deal named a different member of the same evening list. Run #152 has it in
    # writing. Widened the same night.
    #
    # Only for systems that ask for it. A silent shop during service is a fault and
    # must stay one.
    slot_music = set(name.strip()
                     for name in (want.get('slot_playlists') or [want['playlist']]))
    stopped_by_hand = bool(not is_playing and container
                           and container.strip() in slot_music)
    if stopped_by_hand and store.get('leave_off_if_stopped_by_hand'):
        lines.append('    turned off by hand during this slot, so leaving it off')
        lines.append('    it starts again by itself at the next change of slot')
        return lines, trouble, pending, acted

    # ---- the music ----
    music_right = bool(is_playing and container
                       and container.strip() == want['playlist'].strip())

    if not is_playing:
        lines.append('    SILENT during service hours')
        trouble = True

    if music_right:
        lines.append('    music: already correct')
    else:
        fav = sonos.find_favourite(store['id'], store['household'], want['playlist'])
        if fav is None:
            lines.append('    NO SONOS FAVOURITE NAMED %r. Add it once on this system, '
                         'and point it at your own copy rather than the Spotify original.'
                         % want['playlist'])
            trouble = True
        elif live:
            try:
                sonos.play_favourite(store['id'], store['group'], fav['id'])
                lines.append('    music: changed to %r' % want['playlist'])
                acted.append('music to %r' % want['playlist'])
            except sonos.SonosError as e:
                lines.append('    FAILED to change the music: %s' % e)
                trouble = True
        else:
            lines.append('    music: WOULD change to %r   (dry run, nothing done)'
                         % want['playlist'])
            pending = True

    # ---- the volume, checked whatever the music did ----
    try:
        v_trouble, v_pending = reconcile_volume(store, want, live, lines, acted)
        trouble = trouble or v_trouble
        pending = pending or v_pending
    except sonos.SonosError as e:
        lines.append('    FAILED on the volume: %s' % e)
        trouble = True

    return lines, trouble, pending, acted


def point_at_the_live_group(store):
    """Point this store at whichever group its speaker is in right now.

    Written 2026-09-10, the morning home and West Harlem both went silent. A group id
    is a speaker serial plus a number that is regenerated every time the speakers
    re-form a group, so an internet drop kills it and the music stops with a 410 that
    nobody sees. A speaker serial is the hardware and survives all of it.

    Never makes things worse than before it existed: any failure leaves the stored
    group in place and says so, so a store that worked yesterday still works today.
    A store with no speaker setting is untouched, which is what lets this be switched
    on one store at a time.
    """
    speaker = store.get('speaker')
    if not speaker or schedule.not_connected(store):
        return None
    try:
        found = sonos.group_for_speaker(store['id'], store['household'], speaker)
    except Exception as exc:
        return ('    could not ask Sonos which group the speaker is in (%s). '
                'Falling back to the stored group.' % str(exc)[:70])
    if not found:
        return ('    NOTE: speaker %s is not in any group right now, so the stored '
                'group is being used and may be stale.' % speaker)
    if found != store.get('group'):
        was = store.get('group')
        store['group'] = found
        return ('    the group had changed, found it again by its speaker: %s is now %s'
                % (was, found))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live', action='store_true',
                    help='actually change the music. Without this, nothing is touched.')
    ap.add_argument('--at', help='pretend it is this time, e.g. 2026-12-25T19:00')
    args = ap.parse_args()

    cfg = schedule.load()
    now = datetime.fromisoformat(args.at) if args.at else schedule.local_now(cfg)

    print('Store music check, %s' % now.strftime('%Y-%m-%d %H:%M'))
    print('Mode: %s' % ('LIVE, changes will be made' if args.live else 'dry run, nothing will change'))
    print()

    any_trouble = False
    any_pending = False
    changes = []
    enabled = [s for s in cfg['stores'] if s.get('enabled')]
    if not enabled:
        print('  No stores are enabled in config.json.')
        return 0

    for store in enabled:
        note = point_at_the_live_group(store)
        lines, trouble, pending, acted = check_store(cfg, store, now, args.live)
        if note:
            lines.insert(1, note)
        any_trouble = any_trouble or trouble
        any_pending = any_pending or pending
        changes.extend(acted)
        for line in lines:
            print(line)
        print()

    # A quiet success and a quiet failure must never look the same, and neither may be
    # confused with a change that has not been made yet.
    if any_trouble:
        result = 'SOMETHING NEEDS ATTENTION'
    elif changes:
        result = '%d change%s made' % (len(changes), '' if len(changes) == 1 else 's')
    elif any_pending:
        result = 'CHANGES OUTSTANDING. Nothing was done, this was a dry run. '\
                 'Add --live to actually make them.'
    else:
        result = 'all stores as expected, nothing to do'
    print('Result: %s' % result)
    return 1 if any_trouble else 0


if __name__ == '__main__':
    sys.exit(main())
