"""A dead Sonos group at save time must never wipe the memory of hand changes.

22 Nov 2026: at 22:00 the home group id died mid-run (404), run.py dropped the home memory,
and the 22:15 run faded the house from a Spotify playlist Andrew had picked by hand over to
the schedule's playlist. Now remember_house() re-finds the group and retries once; if it
still fails, the hand holds are kept and only the baseline is cleared.
"""
import run, hand, sonos

def check(name, ok):
    print(('PASS ' if ok else 'FAIL ') + name)
    if not ok: raise SystemExit(1)

orig = (sonos.playback_status, sonos.now_playing, run.levels_now, run.point_at_the_live_group)
try:
    sonos.now_playing = lambda sid, g: {'container': {'name': None}}
    run.levels_now = lambda s: (True, {'Kitchen': 40})

    print('--- the group dies, is found again, the retry works ---')
    calls = {'n': 0}
    def status(sid, group):
        calls['n'] += 1
        if group == 'dead': raise RuntimeError('404 ERROR_RESOURCE_GONE')
        return {'playbackState': 'PLAYBACK_STATE_PLAYING'}
    sonos.playback_status = status
    def refind(s):
        s['group'] = 'alive'; return '    found it again'
    run.point_at_the_live_group = refind
    mem = hand.fresh('2026-11-22'); mem['music_held'] = 'music picked by hand'; mem['held'] = {'Kitchen': 40}
    store = {'id': 'home', 'group': 'dead', '_mem': mem}
    check('remember_house reports success', run.remember_house(store) is True)
    check('the retry used the re-found group', store['group'] == 'alive' and calls['n'] == 2)
    check('the hand-picked music is still remembered', mem['music_held'] == 'music picked by hand')

    print('--- the group stays dead ---')
    sonos.playback_status = lambda sid, g: (_ for _ in ()).throw(RuntimeError('404'))
    run.point_at_the_live_group = lambda s: None
    mem = hand.fresh('2026-11-22'); mem['music_held'] = 'music picked by hand'; mem['held'] = {'Kitchen': 40}
    mem['set'] = {'Kitchen': 15}; mem['music'] = 'Classical Romance'; mem['playing'] = True; mem['paused_held'] = True
    store = {'id': 'home', 'group': 'dead', '_mem': mem}
    check('remember_house reports failure', run.remember_house(store) is False)
    check('hand holds kept', mem['music_held'] == 'music picked by hand' and mem['held'] == {'Kitchen': 40} and mem['paused_held'] is True)
    check('baseline cleared', mem['set'] == {} and mem['music'] is None and mem['playing'] is False)
    check('no stray nameless flag', mem['nameless_pending'] is False)
    check('run.py no longer drops a memory', "mem_all.pop(s['id'], None)" not in open('run.py').read())
finally:
    sonos.playback_status, sonos.now_playing, run.levels_now, run.point_at_the_live_group = orig
print('All checks passed.')
