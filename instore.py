"""The in-shop setup kit. Walks one shop from nothing to working, step by step.

  python instore.py west-harlem            do the setup, one step at a time
  python instore.py west-harlem --check    just say what is done and what is left

Written 2026-09-07 so that a shop visit takes ten minutes and never has to happen
twice. Everything that can be done from a desk has already been done by the time
you are standing there. What is left needs the phone app on the shop's wifi, and
this checks each one the moment you do it, so nothing is discovered later.

Reads and plays. It never deletes anything and never edits your settings file.
"""

import json
import sys

import schedule
import sonos

CONFIG = 'config.json'


def line(ch='-'):
    print(ch * 72)


def ask(prompt):
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        print('Stopped. Nothing was left half done, you can run this again any time.')
        sys.exit(1)


def wanted_playlists(cfg, store, everything=False):
    """The playlist names this shop has to have saved.

    By default only the ones it needs to work today. Pass everything=True to get
    the seasonal and Christmas ones as well, which are not needed until December
    and should never hold up a shop visit in September.
    """
    names = []

    def add(n):
        if n and n not in names:
            names.append(n)

    slots = schedule.slots_for(cfg, store)
    slot_names = [s.get('name') for s in slots]
    for slot in slots:
        add(slot.get('playlist'))
        for n in slot.get('playlist_pool', []) or []:
            add(n)

    # A season or a holiday swaps the playlist for a named slot. Only the ones that
    # name a slot this shop actually has apply here, which is what keeps the shop
    # Christmas playlists off the list for home and the other way round.
    def from_overrides(block):
        for slot_name, playlist in (block.get('overrides') or {}).items():
            if slot_name in slot_names:
                add(playlist)

    if everything:
        seasons = cfg.get('seasons', {})
        for block in (seasons.values() if isinstance(seasons, dict) else seasons):
            from_overrides(block)
        for block in cfg.get('holidays', []):
            from_overrides(block)

    return [n for n in names if n and not n.startswith('NEEDS ')]


def pick_system(store_id, households):
    if len(households) == 1:
        return households[0]['id']
    print('This sign-in reaches more than one system:')
    for i, h in enumerate(households, 1):
        try:
            gs = sonos.groups(store_id, h['id']).get('groups', [])
            where = ', '.join(g.get('name', '?') for g in gs)
        except Exception:
            where = 'could not read the speakers'
        print('  %d. %s   (%s)' % (i, h['id'], where))
    while True:
        answer = ask('Which one is this shop? Type its number: ')
        if answer.isdigit() and 1 <= int(answer) <= len(households):
            return households[int(answer) - 1]['id']
        print('Type one of the numbers above.')


def show_state(store_id, household, needed):
    """Print what is saved on the system now, and what is still missing."""
    have = [f.get('name') for f in sonos.favourites(store_id, household)]
    missing = [n for n in needed if n not in have]
    print('Playlists saved on this system right now: %d' % len(have))
    for n in have:
        print('    %s' % n)
    print()
    if missing:
        print('STILL MISSING, %d of them:' % len(missing))
        for n in missing:
            print('    %s' % n)
    else:
        print('NOTHING MISSING. Every playlist the schedule asks for is saved here.')
    return have, missing


def main():
    if len(sys.argv) < 2:
        print('Which shop? For example:  python instore.py west-harlem')
        return 1
    store_id = sys.argv[1]
    check_only = '--check' in sys.argv

    cfg = schedule.load(CONFIG)
    store = None
    for s in cfg['stores']:
        if s['id'] == store_id:
            store = s
    if store is None:
        print('There is no shop called %r in config.json. The ones there are:' % store_id)
        for s in cfg['stores']:
            print('    %s' % s['id'])
        return 1

    line('=')
    print('SETTING UP: %s' % store.get('name', store_id))
    line('=')
    print()

    # ---------------------------------------------------------------- step 1
    print('STEP 1 of 6.  Can we reach this shop from outside?')
    print()
    try:
        households = sonos.households(store_id)
    except Exception as e:
        print('COULD NOT REACH SONOS: %s' % e)
        print()
        print('There is no saved sign-in for this shop yet, or it has stopped working.')
        print('Fix it at your desk before you go, it does not need the shop wifi:')
        print('    python connect.py %s' % store_id)
        return 1

    if not households:
        print('That sign-in reaches no Sonos systems at all, so it is the wrong account.')
        print('Run  python connect.py %s  and sign in as the account that set the shop up.'
              % store_id)
        return 1

    household = pick_system(store_id, households)
    groups = sonos.groups(store_id, household).get('groups', [])
    players = sonos.players(store_id, household).get('players', [])
    print('Reached it. %d speaker%s, in %d group%s:'
          % (len(players), '' if len(players) == 1 else 's',
             len(groups), '' if len(groups) == 1 else 's'))
    for g in groups:
        print('    group    %s' % g.get('name'))
    for p in players:
        print('    speaker  %s' % p.get('name'))
    print()

    # ---------------------------------------------------------------- step 2
    print('STEP 2 of 6.  What is saved on it, and what is missing.')
    print()
    needed = wanted_playlists(cfg, store)
    have, missing = show_state(store_id, household, needed)
    later = [n for n in wanted_playlists(cfg, store, everything=True)
             if n not in needed and n not in have]
    if later:
        print()
        print('Not needed today, and not worth holding up this visit. These are the')
        print('Christmas and one-off day playlists, due before December:')
        for n in later:
            print('    %s' % n)
    print()

    if check_only:
        line()
        print('Check only, nothing was changed.')
        if missing:
            print('This shop is NOT ready. %d playlist%s still to add.'
                  % (len(missing), '' if len(missing) == 1 else 's'))
            return 2
        print('This shop is ready as far as playlists go.')
        return 0

    # ---------------------------------------------------------------- step 3
    print('STEP 3 of 6.  Adding the missing playlists. This is the part that needs')
    print('              you to be here, on the shop wifi, with the Sonos app open.')
    print()
    if not missing:
        print('Nothing to add. Skipping.')
        print()
    else:
        print('For each one: in the Sonos app, find that playlist in Spotify, open it,')
        print('and choose "Add to My Sonos". Then come back here and press Enter.')
        print('I check the system straight away, so you will know at once if it landed.')
        print()
        remaining = list(missing)
        while remaining:
            name = remaining[0]
            print('    ADD THIS ONE:   %s' % name)
            answer = ask('    Press Enter when it is added, or type skip: ')
            if answer == 'skip':
                print('    Skipped. It will show as missing at the end.')
                remaining.pop(0)
                print()
                continue
            try:
                found = sonos.find_favourite(store_id, household, name)
            except Exception as e:
                found = None
                print('    Could not check just now: %s' % e)
            if found:
                print('    CONFIRMED, it is on the system.')
                remaining.pop(0)
            else:
                print('    NOT THERE YET. Sonos still does not show a playlist by that')
                print('    name. Check the spelling matches character for character.')
            print()

    # ---------------------------------------------------------------- step 4
    print('STEP 4 of 6.  The old alarms.')
    print()
    print('In the Sonos app: Settings, then Alarms. Delete every alarm you find.')
    print('They are what used to start the music here and they now fight the schedule.')
    print('I cannot see or delete alarms myself, Sonos does not allow it from outside,')
    print('so this one is on your word.')
    ask('Press Enter once there are no alarms left: ')
    print()

    # ---------------------------------------------------------------- step 5
    print('STEP 5 of 6.  Play something, so you hear it with your own ears.')
    print()
    playable = [n for n in needed if any(f.get('name') == n
                for f in sonos.favourites(store_id, household))]
    if not playable and not groups:
        print('Nothing saved to play yet. Skipping.')
    else:
        answer = ask('Play a track through the shop speakers now? (yes/no): ')
        if answer.startswith('y') and playable and groups:
            group_id = groups[0]['id']
            name = playable[0]
            fav = sonos.find_favourite(store_id, household, name)
            try:
                sonos.set_volume(store_id, group_id, 15)
                sonos.play_favourite(store_id, group_id, fav['id'])
                print('    Playing %r at a low volume.' % name)
                heard = ask('    Can you hear it in the room? (yes/no): ')
                if heard.startswith('y'):
                    print('    Good. That is the whole chain working: this laptop, the')
                    print('    internet, Sonos, and the speakers in front of you.')
                else:
                    print('    Then the speakers playing are not the ones in this room,')
                    print('    or the group is wrong. Write down which group you picked.')
                sonos.pause(store_id, group_id)
                print('    Stopped it again.')
            except Exception as e:
                print('    Could not play: %s' % e)
        else:
            print('    Skipped.')
    print()

    # ---------------------------------------------------------------- step 6
    print('STEP 6 of 6.  The two identifiers I need to switch this shop on.')
    print()
    out = {
        'store': store_id,
        'household': household,
        'groups': [{'name': g.get('name'), 'id': g.get('id')} for g in groups],
        'speakers': [{'name': p.get('name'), 'id': p.get('id')} for p in players],
    }
    path = 'ids-%s.json' % store_id
    with open(path, 'w') as fh:
        json.dump(out, fh, indent=2)
    print('Written to %s, which never leaves this computer.' % path)
    print('Send me that file, or just say the word and I will read it, and I will put')
    print('these into GitHub for you and switch the shop on.')
    print()

    line('=')
    have, missing = show_state(store_id, household, needed)
    print()
    if missing:
        print('NOT FINISHED. Do not leave yet. %d playlist%s still missing above.'
              % (len(missing), '' if len(missing) == 1 else 's'))
        return 2
    print('DONE IN THE SHOP. Everything the schedule needs is on this system.')
    print('Nothing else here needs you. The rest I do from my end.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
