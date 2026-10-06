"""Work out what should be playing at every store, and make it so.

DRY RUN IS THE DEFAULT. It tells you what it would do and changes nothing.
To actually act:   python run.py --live

Adding a store is one entry in config.json plus one run of connect.py. Nothing in this
file mentions a particular store.
"""

import argparse
import json
import sys
import time
from datetime import datetime

import hand
import memory
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


# How gently the music comes on. Also by hand, for the same reason. Andrew asked on
# 2026-09-12: at home the music should rise from silence to its level rather than
# come on all at once, ten minutes on weekend mornings and two minutes otherwise. The
# number of seconds lives in config.json, on the slot or on the system. No number, no
# fade, which is what the shops get. A step is at least ten seconds and there are at
# most twenty, so a long fade means bigger gaps rather than a flood of calls.
FADE_IN_MAX_STEPS = 20
FADE_IN_MIN_STEP_SECONDS = 10

# Every playlist change at every location, Andrew 2026-09-14: the old music fades out,
# the new playlist starts, and it fades in. This replaced the 2026-09-12 rule that the
# shops start at once. A system or slot with its own fade_in_seconds, which is home,
# keeps its own longer fade in. Short fades take steps of about two seconds, because
# the ten second steps that suit a ten minute fade would sound like two jumps.
CHANGE_FADE_OUT_SECONDS = 10
CHANGE_FADE_IN_SECONDS = 20
SHORT_FADE_STEPS = 10


def fade_in_steps(seconds):
    if seconds < 120:
        return max(1, min(SHORT_FADE_STEPS, int(seconds) // 2))
    return max(1, min(FADE_IN_MAX_STEPS, int(seconds) // FADE_IN_MIN_STEP_SECONDS))


def start_gently(store, want, fav, seconds, lines, acted, was_playing=False):
    """Fade out whatever is on, start the music, then bring the level up over `seconds`.

    Returns True if the music was started. Any failure after the music is playing is
    reported and left for reconcile_volume, which runs afterwards and sets the final
    levels regardless, so a fade that breaks halfway ends at the right volume rather
    than at nothing.
    """
    # Targets: one per speaker. A system with its own levels per speaker rises to
    # those. One without rises back to where each speaker already is, so a balance set
    # by hand in the room survives, and reconcile_volume then moves the group as a
    # whole. Only a system that reports no speakers at all is faded as one group.
    targets = []
    try:
        found = sonos.players(store['id'], store['household'])
    except sonos.SonosError:
        found = {}
    now_at = dict((name, sonos.player_volume(store['id'], pid).get('volume') or 0)
                  for name, pid in found.items())
    if want.get('speakers'):
        held = store.get('_held') or set()
        for name, level in wanted_levels(store, want, found).items():
            if name in held:
                continue                # a room set by hand keeps its level through the change
            targets.append((name, found[name], now_at[name], level))
    elif len(found) == 1:
        # One speaker is the whole group, so there is no balance to keep and it rises
        # straight to the slot's level. Central Harlem, 2026-09-14: rising to its old 30
        # and then jumping to 34 was audible.
        for name, pid in found.items():
            targets.append((name, pid, now_at[name], want['volume']))
    elif found:
        for name, pid in found.items():
            targets.append((name, pid, now_at[name], now_at[name]))
    else:
        level = sonos.group_volume(store['id'], store['group']).get('volume') or 0
        targets.append(('the whole group', None, level, want['volume']))

    def set_level(player_id, level):
        if player_id is None:
            sonos.set_volume(store['id'], store['group'], level)
        else:
            sonos.set_player_volume(store['id'], player_id, level)

    if was_playing and any(start > 0 for _n, _p, start, _l in targets):
        steps = fade_in_steps(CHANGE_FADE_OUT_SECONDS)
        for step in range(steps - 1, -1, -1):
            for _name, player_id, start, _level in targets:
                if start > 0:
                    set_level(player_id, int(round(start * step / float(steps))))
            if step:
                time.sleep(CHANGE_FADE_OUT_SECONDS / float(steps))
        time.sleep(CHANGE_FADE_OUT_SECONDS / float(steps))
        lines.append('    faded down over about %d seconds' % CHANGE_FADE_OUT_SECONDS)
    else:
        for _name, player_id, _start, _level in targets:
            set_level(player_id, 0)
    sonos.play_favourite(store['id'], store['group'], fav['id'])
    lines.append('    music: changed to %r, starting from silence' % want['playlist'])
    acted.append('music to %r' % want['playlist'])
    targets = [(name, player_id, level) for name, player_id, _start, level in targets]

    steps = fade_in_steps(seconds)
    try:
        for step in range(1, steps + 1):
            time.sleep(seconds / float(steps))
            for _name, player_id, level in targets:
                if level > 0:
                    set_level(player_id, int(round(level * step / float(steps))))
    except sonos.SonosError as e:
        lines.append('    the fade in stopped early: %s. The level is set outright below.' % e)
        return True
    lines.append('    faded up over about %d seconds to: %s'
                 % (seconds, ', '.join('%s %s' % (n, l) for n, _, l in sorted(targets))))
    acted.append('faded in over %ds' % seconds)
    return True


# Walking one speaker down to nothing across the rest of a slot. Andrew, 2026-09-15:
# the Bedroom fades to silence by midnight. A step of about a minute is small enough to
# go unnoticed in a quiet room and few enough calls to be cheap.
RAMP_MIN_STEP_SECONDS = 45
RAMP_MAX_STEPS = 20


def night_ramp(store, want, now, lines, acted):
    """Take one speaker down to its target over whatever time is left.

    Runs after every store has been checked, never in the middle of one, so a store
    waiting its turn is not held up by a fade at home.
    """
    ramp = want.get('ramp')
    if not ramp:
        return
    if keeps_hand_changes(store) and hand.skip_ramp(store.get('_mem'), ramp['speaker']):
        lines.append('    %s was set by hand today, so its walk down is skipped; the music '
                     'still stops at midnight' % ramp['speaker'])
        return
    try:
        found = sonos.players(store['id'], store['household'])
    except sonos.SonosError as e:
        lines.append('    could not reach the speakers to fade %s: %s' % (ramp['speaker'], e))
        return
    player_id = found.get(ramp['speaker'])
    if player_id is None:
        lines.append('    no speaker named %r answered, so nothing was faded'
                     % ramp['speaker'])
        return

    start = sonos.player_volume(store['id'], player_id).get('volume') or 0
    target = ramp['to']
    if start <= target:
        lines.append('    %s is already at %s, nothing to fade' % (ramp['speaker'], start))
        return

    left = schedule.seconds_until(now, ramp['by'])
    if left <= 0:
        sonos.set_player_volume(store['id'], player_id, target)
        acted.append('%s to %s' % (ramp['speaker'], target))
        return

    steps = max(1, min(RAMP_MAX_STEPS, int(left) // RAMP_MIN_STEP_SECONDS))
    try:
        for step in range(1, steps + 1):
            time.sleep(left / float(steps))
            sonos.set_player_volume(
                store['id'], player_id,
                int(round(start + (target - start) * step / float(steps))))
    except sonos.SonosError as e:
        lines.append('    the fade of %s stopped early: %s' % (ramp['speaker'], e))
        return
    lines.append('    %s faded from %s to %s over the %d minutes to %s'
                 % (ramp['speaker'], start, target, round(left / 60.0), ramp['by']))
    acted.append('%s faded %s to %s' % (ramp['speaker'], start, target))


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
        held = store.get('_held') or set()
        for name, player_id in sorted(found.items()):
            if name in held:
                continue                # set by hand at home today; left until midnight
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


def keeps_hand_changes(store):
    """Home only, Andrew 2026-10-05. A shop always goes back to the schedule."""
    return bool(store.get('keep_hand_changes_until_midnight'))


def regroup(store, lines, unmute=False):
    """Every speaker on the system back in the main group, and optionally unmuted.

    Andrew, 2026-10-05: "all speakers need to be regrouped at the end of each night", and
    the house resets "for the next morning". Done on every run while home is closed, which
    also catches the overnight restarts that left the Kitchen and Dressing Room on their
    own, and once more at the morning start, which also unmutes.
    """
    data = sonos.groups(store['id'], store['household'])
    main = [g for g in data.get('groups', []) if g.get('id') == store['group']]
    if not main:
        lines.append('    could not find the main group to put the speakers back into')
        return
    members = set(main[0].get('playerIds') or [])
    out = [p for p in data.get('players', []) if p.get('id') not in members]
    if out:
        sonos.add_to_group(store['id'], store['group'], [p['id'] for p in out])
        lines.append('    put back in the group: %s' % ', '.join(sorted(p['name'] for p in out)))
    if unmute:
        unmuted = []
        for p in data.get('players', []):
            if sonos.player_volume(store['id'], p['id']).get('muted'):
                sonos.set_player_mute(store['id'], p['id'], False)
                unmuted.append(p['name'])
        if unmuted:
            lines.append('    unmuted for the new day: %s' % ', '.join(sorted(unmuted)))


def levels_now(store):
    found = sonos.players(store['id'], store['household'])
    return found, dict((n, sonos.player_volume(store['id'], pid).get('volume') or 0)
                       for n, pid in found.items())


def rooms_not_in_the_music(store):
    """Every speaker on this system that is not making the music: left the main group, or muted.

    Added 2026-10-05. Three times a room went quiet while every run said "correct": the
    Sunroom muted at home (18 September), and the home Kitchen and Dressing Room split into
    groups of their own, the second time for two days (30 September to 2 October). The job
    reads one group and sets each speaker's level, so a muted speaker or one outside the group
    passes every other check. Hell's Kitchen's pair can fail the same way. This only reports;
    it changes nothing. A switch on the system turns it on, and only the shops have it.
    """
    data = sonos.groups(store['id'], store['household'])
    main = [g for g in data.get('groups', []) if g.get('id') == store['group']]
    if not main:
        return []      # the group could not be found at all; other checks already say so
    members = set(main[0].get('playerIds') or [])
    quiet = []
    for p in data.get('players', []):
        if p.get('id') not in members:
            quiet.append((p.get('name'), 'it has left the main group, so no music reaches it'))
        elif sonos.player_volume(store['id'], p['id']).get('muted'):
            quiet.append((p.get('name'), 'it is muted'))
    return quiet


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

        # Home: every speaker back in the group, every run through the night.
        if keeps_hand_changes(store) and live and not schedule.not_connected(store):
            try:
                regroup(store, lines)
            except sonos.SonosError as e:
                lines.append('    could not put the speakers back in the group: %s' % e)

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
    # Don't print a group volume for a store that sets each speaker separately: that
    # number is not used and someone would eventually "correct" the speakers to match
    # it. Hell's Kitchen started doing this on 2026-09-10.
    if want.get('speakers'):
        lines.append('    should be: %s  at its own level per speaker   (%s)'
                     % (want['playlist'], want['reason']))
    else:
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

    # ---- hand changes at home, kept until midnight (Andrew, 2026-10-05) ----
    mem = store.get('_mem') if keeps_hand_changes(store) else None
    if keeps_hand_changes(store) and store.get('_mem_note'):
        lines.append('    %s' % store['_mem_note'])
    if mem is not None and live:
        if not mem['morning_done']:
            regroup(store, lines, unmute=True)
            mem['morning_done'] = True
        found, actual = levels_now(store)
        for name in hand.find_hand_levels(mem, actual, wanted_levels(store, want, found)):
            lines.append('    %s was set to %s by hand, so it stays there until midnight'
                         % (name, mem['held'][name]))
        hand.find_hand_music(mem, container, is_playing, want['playlist'])
        if mem['held']:
            lines.append('    left as set by hand: %s' % ', '.join(
                '%s %s' % (n, v) for n, v in sorted(mem['held'].items())))
        store['_held'] = set(mem['held'])
        if mem['paused_held']:
            lines.append('    paused by hand today, so it stays off until midnight')
            return lines, trouble, pending, acted
        if mem['music_held']:
            lines.append('    %r was put on by hand, so it stays until midnight' % mem['music_held'])

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
    if mem is not None and live and mem['music_held'] and is_playing:
        music_right = True              # not the schedule's, but chosen by hand: leave it

    if not is_playing:
        lines.append('    SILENT during service hours')
        trouble = True

    if music_right:
        held_music = mem is not None and live and mem['music_held'] and is_playing
        lines.append('    music: left as chosen by hand' if held_music else '    music: already correct')
    else:
        fav = sonos.find_favourite(store['id'], store['household'], want['playlist'])
        if fav is None:
            # The advice to prefer your own copy was dropped 2026-10-05: Andrew ruled on
            # 2026-09-08 and again 2026-09-28 that Spotify's own playlists are fine.
            lines.append('    NO SONOS FAVOURITE NAMED %r. Save it once as a favourite on this '
                         'system, or change the name in config.json.' % want['playlist'])
            trouble = True
        elif live:
            try:
                fade = want.get('fade_in_seconds') or CHANGE_FADE_IN_SECONDS
                start_gently(store, want, fav, fade, lines, acted, was_playing=is_playing)
            except sonos.SonosError as e:
                lines.append('    FAILED to change the music: %s' % e)
                trouble = True
        else:
            fade = want.get('fade_in_seconds') or CHANGE_FADE_IN_SECONDS
            how = ', fading in over %d seconds' % fade
            if is_playing:
                how = ', fading out over %d seconds first%s' % (CHANGE_FADE_OUT_SECONDS, how)
            lines.append('    music: WOULD change to %r%s   (dry run, nothing done)'
                         % (want['playlist'], how))
            pending = True

    # ---- the volume, checked whatever the music did ----
    try:
        v_trouble, v_pending = reconcile_volume(store, want, live, lines, acted)
        trouble = trouble or v_trouble
        pending = pending or v_pending
    except sonos.SonosError as e:
        lines.append('    FAILED on the volume: %s' % e)
        trouble = True

    # ---- every room actually in the music, report only ----
    if store.get('report_silent_rooms'):
        try:
            quiet = rooms_not_in_the_music(store)
        except sonos.SonosError as e:
            quiet = []
            lines.append('    could not check the rooms: %s' % e)
        for room, why in quiet:
            lines.append('    ROOM NOT PLAYING: %s, %s' % (room, why))
        if quiet:
            trouble = True

    return lines, trouble, pending, acted


def hold_the_play_modes(store, wanted_playlist):
    """Keep shuffle, repeat and crossfade true, rather than setting them once and hoping.

    Andrew's standing rule, 2026-09-10: every playlist at every location shuffles,
    repeats and crossfades. Setting them only when a playlist starts means they drift
    the moment anyone touches the app, and nothing notices. Repeat especially: with it
    off the music runs out mid-slot and the leave-it-off rule then reads the silence as
    Andrew having stopped it, so a track list ending becomes an hour of quiet.

    Found the same day: all three shops had crossfade off and home had repeat off, none
    of it deliberate and none of it visible.

    Reads first and only writes when something is actually wrong, so a healthy store
    costs one call and changes nothing. Any failure leaves everything alone and says so.
    """
    if schedule.not_connected(store) or not store.get('group') or not wanted_playlist:
        return None
    try:
        fav = sonos.find_favourite(store['id'], store['household'], wanted_playlist)
        # Either the playlist this slot wants, or whatever is actually on. The second
        # half was added 2026-09-10: home's daytime slot is a stream, so a track list
        # started by hand had nothing holding its modes.
        track_list = (sonos.is_a_track_list(fav)
                      or sonos.playing_a_track_list(store['id'], store['group']))
        if not track_list:
            return None          # a radio stream: nothing to shuffle, nothing to fade
        wrong = sonos.wrong_play_modes(store['id'], store['group'])
        if not wrong:
            return None
        sonos.set_play_modes(store['id'], store['group'], wrong)
        return '    play modes put back: %s' % ', '.join(
            '%s should be %s' % (k, str(v).lower()) for k, v in sorted(wrong.items()))
    except Exception as exc:
        return '    could not check the play modes (%s). Nothing changed.' % str(exc)[:60]


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

    # Memory between runs, for systems that keep hand changes (home). Live runs only: a dry
    # run must not record anything, or it would teach the next live run the wrong levels.
    mem_all, mem_sha, mem_note, mem_before = None, None, None, None
    if args.live and any(keeps_hand_changes(s) for s in enabled):
        mem_all, mem_sha, mem_note = memory.load()
        mem_before = json.dumps(mem_all, sort_keys=True)
        for s in enabled:
            if not keeps_hand_changes(s):
                continue
            if mem_all is None:
                s['_mem_note'] = mem_note
                continue
            s['_mem'], _reset = hand.start_day(mem_all.get(s['id']), now.date().isoformat())
            mem_all[s['id']] = s['_mem']

    for store in enabled:
        # One store must never be able to take the music off in the others. A bad
        # household id used to crash the whole run inside find_favourite, so a single
        # mistyped identifier would have silenced all four shops and the run would end
        # with a stack trace instead of a report. Found 2026-09-10 while testing
        # something else.
        #
        # Deliberately catching everything rather than the one call that was seen to
        # fail. Protecting the failure you happened to notice is the same mistake as
        # listing the bad files in an ignore rule: it holds until the next one.
        try:
            note = point_at_the_live_group(store)
            want_now = schedule.decide(cfg, now, store)
            modes_note = (hold_the_play_modes(store, (want_now or {}).get('playlist'))
                          if args.live else None)
            lines, trouble, pending, acted = check_store(cfg, store, now, args.live)
            for extra in (modes_note, note):
                if extra:
                    lines.insert(1, extra)
        except Exception as exc:
            lines = ['  %s' % (store.get('name') or store['id']),
                     '    THIS STORE COULD NOT BE CHECKED AT ALL: %s' % str(exc)[:150],
                     '    The other stores were checked normally and are unaffected.']
            trouble, pending, acted = True, False, []
        any_trouble = any_trouble or trouble
        any_pending = any_pending or pending
        changes.extend(acted)
        for line in lines:
            print(line)
        print()

    # One speaker walking down to silence inside a slot, done last so that no store is
    # left waiting behind a fade at home. Andrew, 2026-09-15: the Bedroom fades to
    # nothing over the last quarter hour before midnight.
    for store in enabled:
        try:
            want_now = schedule.decide(cfg, now, store)
        except Exception:
            continue
        if not want_now.get('ramp') or schedule.not_connected(store):
            continue
        lines, acted = ['  %s' % (store.get('name') or store['id'])], []
        if not args.live:
            lines.append('    WOULD fade %s down to %s by %s   (dry run, nothing done)'
                         % (want_now['ramp']['speaker'], want_now['ramp']['to'],
                            want_now['ramp']['by']))
            any_pending = True
        else:
            try:
                night_ramp(store, want_now, now, lines, acted)
            except Exception as exc:
                lines.append('    the fade could not be done: %s' % str(exc)[:150])
                any_trouble = True
        changes.extend(acted)
        for line in lines:
            print(line)
        print()

    # Remember what the house was left at, so the next run can tell a person's change from
    # the job's own. Read back from the speakers rather than taken from what was asked for,
    # so a fade that stopped early is remembered where it really stopped.
    if mem_all is not None:
        for s in enabled:
            if not s.get('_mem') or schedule.not_connected(s):
                continue
            try:
                _found, actual = levels_now(s)
                st = sonos.playback_status(s['id'], s['group'])
                np = sonos.now_playing(s['id'], s['group'])
                hand.remember(s['_mem'], actual, (np.get('container') or {}).get('name'),
                              st.get('playbackState') == 'PLAYBACK_STATE_PLAYING')
            except Exception as exc:
                # Drop this system's memory rather than keep a half-true one: the guards in
                # hand.py turn an empty memory into the old behaviour, never a frozen house.
                mem_all.pop(s['id'], None)
                print('  memory for %s not updated: %s' % (s['id'], str(exc)[:120]))
        if json.dumps(mem_all, sort_keys=True) != mem_before:
            problem = memory.save(mem_all, mem_sha)
            if problem:
                print('  %s' % problem)

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
    # Say which stores are protected against a group id dying. Without this, a
    # mistyped or missing SONOS_SPEAKER_ setting looks exactly like a working one,
    # because the lookup is silent when the stored group happens to still be right.
    # Added 2026-09-10 so Andrew can see his own settings took effect.
    # How old each saved pass is. Never the pass itself, only its age. Recorded on
    # every run so that when one dies we can say how old it was, which is the one
    # thing nobody could answer when Central Harlem's died on 2026-09-10.
    ages = []
    for s in enabled:
        d = sonos.token_age_days(s['id'])
        ages.append('%s:%s' % (s['id'], 'unknown' if d is None else '%sd' % d))
    print('Saved pass ages: %s' % ', '.join(ages))

    protected = [s['id'] for s in enabled if s.get('speaker')]
    exposed = [s['id'] for s in enabled if not s.get('speaker')]
    print('Group found by speaker for: %s'
          % (', '.join(protected) if protected else 'no stores yet'))
    if exposed:
        # Name the gap rather than leaving it to be worked out from the list of the
        # ones that are fine. On 2026-09-10 that inference cost a round trip: three
        # stores were named and the missing one had to be spotted by its absence.
        print('NOT protected, a regrouping would take these off: %s' % ', '.join(exposed))
    print('Result: %s' % result)
    return 1 if any_trouble else 0


if __name__ == '__main__':
    sys.exit(main())
