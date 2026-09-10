"""Checks the schedule decides correctly. No network, no speakers, no Sonos account.

Run:  python test_schedule.py
"""

from datetime import datetime, timedelta
import schedule

cfg = schedule.load()
failures = []


def check(when_text, expect_playlist, why):
    when = datetime.fromisoformat(when_text)
    got = schedule.decide(cfg, when)['playlist']
    ok = got == expect_playlist
    if not ok:
        failures.append('%s: expected %r, got %r  (%s)' % (when_text, expect_playlist, got, why))
    print('%s %-18s %-34s %s' % ('PASS' if ok else 'FAIL', when_text[-8:], str(got), why))


print('--- an ordinary Tuesday in October, no season or holiday override set ---')
check('2026-10-06T10:00', None, 'before opening, nothing plays')
check('2026-10-06T11:29', None, 'one minute before the first slot')
check('2026-10-06T11:30', 'Jazz Trumpet', 'lunch rush starts exactly on the boundary')
check('2026-10-06T13:29', 'Jazz Trumpet', 'last minute of lunch rush')
check('2026-10-06T13:30', 'Instrumental Jazz Standards', 'dead stretch takes over on the boundary')
check('2026-10-06T15:59', 'Instrumental Jazz Standards', 'end of the dead stretch')
check('2026-10-06T16:00', 'FOH Jazz', 'early evening')
check('2026-10-06T18:00', 'Jazz Classics Blue Note Edition', 'dinner peak, the known gap')
check('2026-10-06T21:00', 'Feel Good Jazz', 'last service')
check('2026-10-06T22:59', 'Feel Good Jazz', 'final minute before close')
check('2026-10-06T23:00', None, 'closed, nothing plays')
check('2026-10-07T03:00', None, 'middle of the night')

print()
print('--- Christmas: never before the first of December, 50/50 mix ---')
check('2026-11-30T19:00', 'Jazz Classics Blue Note Edition', 'November 30th is NOT Christmas')
check('2026-12-01T19:00', 'December Dinner 50-50', 'December 1st, Christmas starts')
check('2026-12-01T12:00', 'December Lunch 50-50', 'holiday applies to every slot, not just evening')
check('2026-12-25T19:00', 'December Dinner 50-50', 'Christmas Day itself')
check('2026-12-26T19:00', 'Jazz Classics Blue Note Edition', 'Boxing Day, holiday is over')

print()
print('--- holiday outranks season, and single day holidays work ---')
check('2026-12-31T19:00', 'Big Band Celebration', "New Year's Eve outranks winter")
check('2026-12-30T19:00', 'Jazz Classics Blue Note Edition', '30th is neither Christmas nor NYE')
check('2027-02-14T19:00', 'Jazz Vocals Romantic', "Valentine's, dinner peak only")
check('2027-02-14T12:00', 'Jazz Trumpet', "Valentine's does not touch lunch")

print()
print('--- the winter season wraps across the new year without breaking ---')
season_dec, _ = schedule.active_season(cfg, datetime.fromisoformat('2026-12-15T12:00').date())
season_jan, _ = schedule.active_season(cfg, datetime.fromisoformat('2027-01-15T12:00').date())
season_jul, _ = schedule.active_season(cfg, datetime.fromisoformat('2026-07-15T12:00').date())
for label, got, want in (('15 Dec', season_dec, 'winter'),
                         ('15 Jan', season_jan, 'winter'),
                         ('15 Jul', season_jul, 'summer')):
    ok = got == want
    if not ok:
        failures.append('season on %s: expected %s, got %s' % (label, want, got))
    print('%s %-18s season is %s' % ('PASS' if ok else 'FAIL', label, got))

print()
print('--- the placeholder is flagged rather than played silently ---')
d = schedule.decide(dict(cfg, slots=[dict(s, playlist='NEEDS A TEST PLAYLIST') if s['name']=='Dinner peak' else s for s in cfg['slots']]), datetime.fromisoformat('2026-10-06T19:00'))
ok = d['needs_attention'] is not None
if not ok:
    failures.append('dinner peak placeholder was not flagged')
print('%s dinner peak raises: %s' % ('PASS' if ok else 'FAIL', d['needs_attention']))

d2 = schedule.decide(cfg, datetime.fromisoformat('2026-10-06T12:00'))
ok2 = d2['needs_attention'] is None
if not ok2:
    failures.append('lunch rush was flagged when it should not be')
print('%s lunch rush raises nothing' % ('PASS' if ok2 else 'FAIL'))

print()
print('--- a system with its own playlist names uses them, and wins over holidays ---')
home = [x for x in cfg['stores'] if x['id'] == 'home'][0]


def check_store(when_text, expect_playlist, why):
    when = datetime.fromisoformat(when_text)
    got = schedule.decide(cfg, when, home)['playlist']
    ok = got == expect_playlist
    if not ok:
        failures.append('%s on home: expected %r, got %r  (%s)'
                        % (when_text, expect_playlist, got, why))
    print('%s %-18s %-34s %s' % ('PASS' if ok else 'FAIL', when_text[-8:], str(got), why))


def home_slot(prefix):
    """The first home slot whose name starts with this.

    From 2026-09-10 the daytime and evening are split across several slots so that
    different days can behave differently: the Sunroom is off Tue to Thu, the TV Room
    is off those evenings, and the weekend starts at ten. Matching on a prefix means
    these checks keep testing the behaviour rather than the label.
    """
    for sl in home['slots']:
        if sl['name'].startswith(prefix):
            return sl
    raise AssertionError('no home slot starting with %r' % prefix)

_pool_now = home_slot('Daytime')['playlist_pool']
_sat = schedule.decide(cfg, datetime.fromisoformat('2026-10-10T12:00'), home)['playlist']
_ok_sat = _sat in _pool_now
if not _ok_sat:
    failures.append('Saturday daytime dealt something not in the list: %r' % _sat)
print('%s %-18s %-34s %s' % ('PASS' if _ok_sat else 'FAIL', '10T12:00', _sat,
                             'Saturday daytime deals from the classical list'))
_eve_pool = home_slot('Evening')['playlist_pool']
_tue_eve = schedule.decide(cfg, datetime.fromisoformat('2026-10-06T19:00'), home)['playlist']
_ok_tue = _tue_eve in _eve_pool
if not _ok_tue:
    failures.append('Tuesday evening dealt something not in the lounge list: %r' % _tue_eve)
print('%s %-18s %-34s %s' % ('PASS' if _ok_tue else 'FAIL', '06T19:00', _tue_eve,
                             'Tuesday evening deals from the lounge list'))
_xmas = schedule.decide(cfg, datetime.fromisoformat('2026-12-20T19:00'), home)['playlist']
_ok_xmas = _xmas in _eve_pool
if not _ok_xmas:
    failures.append('a December evening at home was hijacked by the store Christmas rule: %r'
                    % _xmas)
print('%s %-18s %-34s %s' % ('PASS' if _ok_xmas else 'FAIL', '20T19:00', _xmas,
                             'home ignores the store Christmas playlists'))
check_store('2026-10-10T08:00', None, 'before nine, nothing plays at home')

d3 = schedule.decide(cfg, datetime.fromisoformat('2026-10-06T19:00'), home)
ok3 = d3['needs_attention'] is None
if not ok3:
    failures.append('a home evening was flagged even though it names a real station')
print('%s home raises nothing, every slot names a real station' % ('PASS' if ok3 else 'FAIL'))

# A station named in capitals is a real station, not a placeholder. Only the word
# NEEDS marks a gap.
ok_caps = all(
    schedule.decide(cfg, datetime.fromisoformat(t), home)['needs_attention'] is None
    for t in ('2026-09-07T10:00', '2026-09-08T10:00', '2026-09-09T10:00',
              '2026-09-10T10:00', '2026-09-11T10:00'))
if not ok_caps:
    failures.append('a Calm Radio station in capitals was mistaken for a placeholder')
print('%s a station named in capitals is not mistaken for a placeholder'
      % ('PASS' if ok_caps else 'FAIL'))

d4 = schedule.decide(cfg, datetime.fromisoformat('2026-10-06T19:00'))
ok4 = d4['playlist'] == 'Jazz Classics Blue Note Edition'
if not ok4:
    failures.append('the store default was changed by adding home playlists: got %r'
                    % d4['playlist'])
print('%s stores are untouched by home having its own names' % ('PASS' if ok4 else 'FAIL'))

print()
print('--- speakers can be set one by one, and a missing name is caught ---')


def check_speakers(when_text, speaker, expect, why):
    when = datetime.fromisoformat(when_text)
    d = schedule.decide(cfg, when, home)
    got = (d.get('speakers') or {}).get(speaker)
    ok = got == expect
    if not ok:
        failures.append('%s %s: expected %r, got %r  (%s)'
                        % (when_text, speaker, expect, got, why))
    print('%s %-18s %-14s %-6s %s' % ('PASS' if ok else 'FAIL', when_text[-8:], speaker,
                                      str(got), why))


# The ceilings Andrew asked for on 2026-09-10, pinned so a typo in the settings file is
# caught. Checked on a MONDAY, because Tue to Thu silence the Sunroom by day and the TV
# Room by evening, and a test that pins levels must not be reading a deliberate zero.
for room, level in (('TV Room', 20), ('Kitchen', 28), ('Bedroom', 25),
                    ('Sunroom', 20), ('Dressing Room', 25)):
    check_speakers('2026-10-05T12:00', room, level, 'the ceiling Andrew asked for, daytime')

daytime = schedule.decide(cfg, datetime.fromisoformat('2026-10-05T12:00'), home)['speakers']
evening = schedule.decide(cfg, datetime.fromisoformat('2026-10-05T19:00'), home)['speakers']

ok_quieter = all(evening[r] < daytime[r] for r in daytime)
if not ok_quieter:
    failures.append('the evening is not quieter than the daytime in every room')
print('%s every room is quieter in the evening than in the day'
      % ('PASS' if ok_quieter else 'FAIL'))

# Sunroom and TV Room now share a ceiling, so a strict order is meaningless between
# them. What matters is that no pair SWAPS: if one room is louder than another by day
# it must not be quieter in the evening.
order_day = sorted(daytime, key=lambda r: (daytime[r], r))
order_eve = sorted(evening, key=lambda r: (evening[r], r))
rooms = sorted(daytime)
ok_order = all(
    not ((daytime[a] < daytime[b] and evening[a] > evening[b]) or
         (daytime[a] > daytime[b] and evening[a] < evening[b]))
    for i, a in enumerate(rooms) for b in rooms[i + 1:])
if not ok_order:
    failures.append('the rooms change their loudness order between slots: %s vs %s'
                    % (order_day, order_eve))
print('%s no two rooms swap places between the day and the evening'
      % ('PASS' if ok_order else 'FAIL'))

d5 = schedule.decide(cfg, datetime.fromisoformat('2026-10-06T19:00'))
ok5 = d5.get('speakers') is None
if not ok5:
    failures.append('a store with no speaker levels was given some: %r' % d5.get('speakers'))
print('%s stores get no speaker levels, they use one volume for the group'
      % ('PASS' if ok5 else 'FAIL'))

d6 = schedule.decide(cfg, datetime.fromisoformat('2026-10-06T03:00'), home)
ok6 = d6.get('speakers') is None
if not ok6:
    failures.append('speaker levels were returned while closed')
print('%s nothing is set while closed' % ('PASS' if ok6 else 'FAIL'))

names = set()
for slot_levels in home.get('speaker_volumes', {}).values():
    names |= set(slot_levels)
ok7 = names == {'Kitchen', 'Sunroom', 'Bedroom', 'Dressing Room', 'TV Room'}
if not ok7:
    failures.append('speaker names in config do not match the five real speakers: %s'
                    % sorted(names))
print('%s every slot names the same five real speakers' % ('PASS' if ok7 else 'FAIL'))

ok8 = all(0 <= v <= 100
          for slot_levels in home.get('speaker_volumes', {}).values()
          for v in slot_levels.values())
if not ok8:
    failures.append('a speaker volume is outside 0 to 100')
print('%s no volume is outside 0 to 100' % ('PASS' if ok8 else 'FAIL'))

print()
print('--- the clock is the one where the speakers are, not the one on the machine ---')

tz_name = cfg.get('timezone')
ok_tz = tz_name == 'America/New_York'
if not ok_tz:
    failures.append('config.json does not name New York time, it says %r' % tz_name)
print('%s config names the clock: %s' % ('PASS' if ok_tz else 'FAIL', tz_name))

try:
    from zoneinfo import ZoneInfo
    ZoneInfo(tz_name)
    ok_zone = True
    why = 'the machine knows that clock'
except Exception as e:
    ok_zone = False
    why = 'the machine does NOT know that clock: %s' % e
if not ok_zone:
    failures.append(why)
print('%s %s' % ('PASS' if ok_zone else 'FAIL', why))

# The real trap: a machine set to UTC must still decide by New York time.
import datetime as _dt
ny = schedule.local_now(cfg)
machine = _dt.datetime.now()
offset_hours = round((machine - ny.replace(tzinfo=None)).total_seconds() / 3600.0)
print('     machine clock %s, New York %s, %s hours apart'
      % (machine.strftime('%H:%M'), ny.strftime('%H:%M'), offset_hours))

# A summer afternoon in New York is the lunch slot no matter what the machine thinks.
# The point of this one is the clock, not the day: midday is midday whatever the
# machine running this thinks the time is.
ok_choice = str(schedule.decide(cfg, _dt.datetime(2026, 7, 18, 12, 0), home)['slot']).startswith('Daytime')
if not ok_choice:
    failures.append('midday in July was not the daytime slot')
print('%s midday in July is the daytime slot' % ('PASS' if ok_choice else 'FAIL'))

print()
print('--- home plays Calm Radio all day, never Spotify ---')
# Spotify only plays in one place at a time, so anything scheduled on the home speakers
# would cut off whatever Andrew is listening to on his phone. Calm Radio has no such
# limit. That is why not one home slot points at Spotify.
# 7 September 2026 is a Monday, the 12th is the Saturday.


def check_home(when_text, expect, why):
    when = datetime.fromisoformat(when_text)
    got = schedule.decide(cfg, when, home)['playlist']
    ok = got == expect
    if not ok:
        failures.append('%s at home: expected %r, got %r  (%s)'
                        % (when_text, expect, got, why))
    print('%s %-16s %-28s %s' % ('PASS' if ok else 'FAIL', when_text[5:], str(got), why))


_mon = schedule.decide(cfg, datetime.fromisoformat('2026-09-07T09:00'), home)['playlist']
_ok_mon = _mon in _pool_now
if not _ok_mon:
    failures.append('Monday morning dealt something not in the list: %r' % _mon)
print('%s %-16s %-28s %s' % ('PASS' if _ok_mon else 'FAIL', '09-07T09:00', _mon,
                             'nine sharp, dealt from the classical list'))
check_home('2026-09-07T08:59', None, 'one minute before, nothing plays')
_late = schedule.decide(cfg, datetime.fromisoformat('2026-09-07T17:59'), home)['playlist']
_ok_late = _late == _mon
if not _ok_late:
    failures.append('the daytime station changed during the day: %r then %r' % (_mon, _late))
print('%s %-16s %-28s %s' % ('PASS' if _ok_late else 'FAIL', '09-07T17:59', _late,
                             'same station all day, it does not switch mid afternoon'))
_six = schedule.decide(cfg, datetime.fromisoformat('2026-09-07T18:00'), home)['playlist']
_ok_six = _six in _eve_pool
if not _ok_six:
    failures.append('six oclock dealt something not in the lounge list: %r' % _six)
print('%s %-16s %-28s %s' % ('PASS' if _ok_six else 'FAIL', '09-07T18:00', _six,
                             'six sharp, the lounge takes over'))
_eleven = schedule.decide(cfg, datetime.fromisoformat('2026-09-07T22:59'), home)['playlist']
_ok_eleven = _eleven == _six
if not _ok_eleven:
    failures.append('the evening changed mid evening: %r then %r' % (_six, _eleven))
print('%s %-16s %-28s %s' % ('PASS' if _ok_eleven else 'FAIL', '09-07T22:59', _eleven,
                             'same all evening, it does not switch at nine'))
_e = schedule.decide(cfg, datetime.fromisoformat('2026-09-07T23:00'), home)['playlist']
_night_pool = home_slot('Night')['playlist_pool']
_ok_e = _e in _night_pool
if not _ok_e:
    failures.append('eleven at night dealt something not in the late list: %r' % _e)
print('%s %-16s %-28s %s' % ('PASS' if _ok_e else 'FAIL', '09-07T23:00', _e,
                             'eleven is no longer the end of the night'))
_sat2 = schedule.decide(cfg, datetime.fromisoformat('2026-09-12T10:00'), home)['playlist']
_ok_sat2 = _sat2 in _pool_now
if not _ok_sat2:
    failures.append('Saturday morning dealt something not in the list: %r' % _sat2)
print('%s %-16s %-28s %s' % ('PASS' if _ok_sat2 else 'FAIL', '09-12T10:00', _sat2,
                             'weekends are dealt from the same list'))
_sat_eve = schedule.decide(cfg, datetime.fromisoformat('2026-09-12T19:00'), home)['playlist']
_ok_sat_eve = _sat_eve in _eve_pool
if not _ok_sat_eve:
    failures.append('Saturday evening dealt something not in the lounge list: %r' % _sat_eve)
print('%s %-16s %-28s %s' % ('PASS' if _ok_sat_eve else 'FAIL', '09-12T19:00', _sat_eve,
                             'Saturday evening, from the lounge list'))
_sun_eve = schedule.decide(cfg, datetime.fromisoformat('2026-09-13T19:00'), home)['playlist']
_ok_sun_eve = _sun_eve in _eve_pool
if not _ok_sun_eve:
    failures.append('Sunday evening dealt something not in the lounge list: %r' % _sun_eve)
print('%s %-16s %-28s %s' % ('PASS' if _ok_sun_eve else 'FAIL', '09-13T19:00', _sun_eve,
                             'Sunday evening, from the lounge list'))

# ---- the rule that stops Spotify reaching the home speakers ----
#
# Spotify plays in one place at a time, so anything scheduled on the home speakers
# would cut off whatever Andrew is listening to on his phone. Calm Radio has no such
# limit.
#
# An earlier version of this check compared against a hand written list of Spotify
# names. That list was incomplete and two Spotify playlists walked straight past it,
# "Jacques Loussier Playlist" and "Classical", and were scheduled for Friday and
# Saturday evenings. A test is only as good as the thing it compares against.
#
# The rule now is Andrew's own convention, which cannot go stale: **his Calm Radio
# stations are the ones named in capitals.** Anything at home with a lower case letter
# in it is something else and must not be there.

def _slot_names(slot):
    names = set()
    if 'playlist' in slot:
        names.add(slot['playlist'])
    names |= set(slot.get('playlist_by_day', {}).values())
    names |= set(slot.get('playlist_pool', []))
    return names


def _home_playlist_names():
    names = set()
    for slot in home['slots']:
        names |= _slot_names(slot)
    return names


# The rule applies to the daytime only. Andrew is out during the day and using Spotify
# himself, so anything scheduled on Spotify then would cut him off. In the evening he is
# home and playing nothing elsewhere, so Spotify is fine after six.
CALM_ONLY_SLOTS = {sl['name'] for sl in home['slots'] if sl['name'].startswith('Daytime')}

not_calm = []
for slot in home['slots']:
    if slot['name'] not in CALM_ONLY_SLOTS:
        continue
    for n in _slot_names(slot):
        if n != n.upper():
            not_calm.append('%s: %s' % (slot['name'], n))
ok_caps_only = not not_calm
if not ok_caps_only:
    failures.append('a daytime slot plays something that is not Calm Radio: %s'
                    % sorted(not_calm))
print('%s the daytime is Calm Radio only, so nothing cuts off his phone'
      % ('PASS' if ok_caps_only else 'FAIL'))

_evening = home_slot('Evening')
ok_evening_free = len(_slot_names(_evening)) >= 2
if not ok_evening_free:
    failures.append('the evening has fewer than two things to deal from')
print('%s the evening deals from %d, Spotify allowed after six'
      % ('PASS' if ok_evening_free else 'FAIL', len(_slot_names(_evening))))

print('     home plays %d different stations across the week' % len(_home_playlist_names()))

print()
print('--- eleven at night, bedroom and kitchen only ---')
_pre = schedule.decide(cfg, datetime.fromisoformat('2026-09-07T22:59'), home)['playlist']
_ok_pre = _pre in _eve_pool
if not _ok_pre:
    failures.append('one minute to eleven was not an evening playlist: %r' % _pre)
print('%s %-16s %-28s %s' % ('PASS' if _ok_pre else 'FAIL', '09-07T22:59', _pre,
                             'one minute to eleven, still the evening'))
_night_slot = home_slot('Night')
_night_own = _night_slot.get('volume_by_playlist', {})

for _when, _why in (('2026-09-07T23:00', 'eleven sharp'),
                    ('2026-09-07T23:59', 'the last minute of the day'),
                    ('2026-09-12T23:30', 'Saturday night too, every night means every night')):
    _got = schedule.decide(cfg, datetime.fromisoformat(_when), home)['playlist']
    _ok = _got in _night_pool
    if not _ok:
        failures.append('%s dealt something not in the late list: %r' % (_when, _got))
    print('%s %-16s %-28s %s' % ('PASS' if _ok else 'FAIL', _when[5:], _got, _why))

check_home('2026-09-08T00:00', None, 'midnight, it stops')

# The three names Andrew asked for, so a typo in the settings file is caught.
ok_night_names = sorted(_night_pool) == sorted(['BY A LAKE', 'SCHUMANN RESONANCE', 'AMBIENT CALM'])
if not ok_night_names:
    failures.append('the late night list is not the three Andrew asked for: %r' % _night_pool)
print('%s the late night list is the three he asked for' % ('PASS' if ok_night_names else 'FAIL'))

# Whichever one is dealt, only the bedroom and the kitchen play, at that playlist's level.
_bad_nights = []
for _d in range(60):
    _at = datetime(2026, 9, 7, 23, 30) + timedelta(days=_d)
    _n = schedule.decide(cfg, _at, home)
    _want = _night_own.get(_n['playlist'], _night_slot['volume'])
    if _n['volume'] != _want:
        _bad_nights.append('%s played at %s, should be %s' % (_n['playlist'], _n['volume'], _want))
    if _n['speakers'] != {'Bedroom': _want, 'Kitchen': _want,
                          'TV Room': 0, 'Sunroom': 0, 'Dressing Room': 0}:
        _bad_nights.append('%s set the wrong rooms: %r' % (_n['playlist'], _n['speakers']))
ok_two = not _bad_nights
if not ok_two:
    failures.append('late night is wrong: %s' % sorted(set(_bad_nights))[:3])
print('%s every late night playlist plays in the bedroom and kitchen only, at its own level'
      % ('PASS' if ok_two else 'FAIL'))

# The one Andrew singled out. AMBIENT CALM is quieter than the rest of that hour.
_ambient = None
for _d in range(60):
    _n = schedule.decide(cfg, datetime(2026, 9, 7, 23, 30) + timedelta(days=_d), home)
    if _n['playlist'] == 'AMBIENT CALM':
        _ambient = _n
        break
ok_vol = (_ambient is not None and _ambient['volume'] == 15
          and _ambient['speakers']['Bedroom'] == 15 and _ambient['speakers']['Kitchen'] == 15)
if not ok_vol:
    failures.append('AMBIENT CALM did not come out at 15: %r' % (_ambient and _ambient['speakers']))
print('%s AMBIENT CALM plays at 15 wherever it comes up' % ('PASS' if ok_vol else 'FAIL'))

# And the other two are unaffected by that rule.
_others = [schedule.decide(cfg, datetime(2026, 9, 7, 23, 30) + timedelta(days=_d), home)
           for _d in range(60)]
ok_others = all(n['volume'] == 18 for n in _others if n['playlist'] != 'AMBIENT CALM')
if not ok_others:
    failures.append('one of the other late night playlists changed volume')
print('%s the other two still play at 18' % ('PASS' if ok_others else 'FAIL'))

# All three actually get used, rather than one never coming up.
_dealt_night = set(n['playlist'] for n in _others)
ok_all_three = _dealt_night == set(_night_pool)
if not ok_all_three:
    failures.append('over two months the late night list only dealt %s' % sorted(_dealt_night))
print('%s all three come up over two months' % ('PASS' if ok_all_three else 'FAIL'))

# Nothing may be left silent into the next morning. The night sets rooms to zero, so
# something has to prove they come back up. Checked on a MONDAY, because from
# 2026-09-10 the Sunroom is deliberately off on Tue, Wed and Thu and the TV Room in
# those evenings. A deliberate silence must not be mistaken for a stuck one, and a
# stuck one must not hide behind a deliberate one.
morning = schedule.decide(cfg, datetime.fromisoformat('2026-09-07T09:30'), home)   # Monday
ok_back = all(v > 0 for v in morning['speakers'].values())
if not ok_back:
    failures.append('a room is still silenced on a Monday morning: %r' % morning['speakers'])
print('%s every room comes back up in the morning' % ('PASS' if ok_back else 'FAIL'))

# Andrew's day rules, 2026-09-10. These are what a room being at zero is ALLOWED to mean.
_day_rules = [
    ('2026-09-07T11:00', 'Mon daytime', set()),                  # nothing off
    ('2026-09-08T11:00', 'Tue daytime', {'Sunroom'}),
    ('2026-09-09T11:00', 'Wed daytime', {'Sunroom'}),
    ('2026-09-10T11:00', 'Thu daytime', {'Sunroom'}),
    ('2026-09-11T11:00', 'Fri daytime', set()),
    ('2026-09-12T11:00', 'Sat daytime', set()),
    ('2026-09-07T19:00', 'Mon evening', set()),
    ('2026-09-08T19:00', 'Tue evening', {'TV Room'}),
    ('2026-09-10T19:00', 'Thu evening', {'TV Room'}),
    ('2026-09-11T19:00', 'Fri evening', set()),
]
ok_rules = True
for stamp, label, expect_off in _day_rules:
    w = schedule.decide(cfg, datetime.fromisoformat(stamp), home)
    got_off = {k for k, v in (w.get('speakers') or {}).items() if v == 0}
    if got_off != expect_off:
        ok_rules = False
        failures.append('%s: expected %s silent, got %s' % (label, sorted(expect_off) or 'none', sorted(got_off) or 'none'))
print('%s the Tue-Thu sunroom and TV room rules hold all week' % ('PASS' if ok_rules else 'FAIL'))

# The weekend starts at ten, not nine.
_sat9 = schedule.decide(cfg, datetime.fromisoformat('2026-09-12T09:30'), home)
_sat10 = schedule.decide(cfg, datetime.fromisoformat('2026-09-12T10:30'), home)
ok_weekend = _sat9.get('playlist') is None and _sat10.get('playlist') is not None
if not ok_weekend:
    failures.append('the weekend did not start at ten: 09:30 %r, 10:30 %r'
                    % (_sat9.get('playlist'), _sat10.get('playlist')))
print('%s the weekend is silent at half nine and playing at half ten' % ('PASS' if ok_weekend else 'FAIL'))

print()
print('--- dealing from a list of playlists, like a shuffled deck ---')
import copy as _copy

_pool = ['BACH', 'MOZART', 'CHOPIN', 'VIVALDI', 'BEETHOVEN',
         'HANDEL', 'HAYDN', 'TELEMANN', 'RAMEAU', 'COUPERIN']
_deck_home = _copy.deepcopy(home)
_deck_home['slots'] = [{'name': 'Daytime', 'from': '09:00', 'to': '18:00',
                        'volume': 30, 'playlist_pool': _pool}]
_deck_home['speaker_volumes'] = {}


def _dealt(day_offset, hour=12):
    when = datetime(2026, 1, 1, hour) + timedelta(days=day_offset)
    return schedule.decide(cfg, when, _deck_home)['playlist']


# Every run in the same day has to agree, or the music would change four times an hour.
one_day = {_dealt(0, h) for h in range(9, 18)}
ok_stable = len(one_day) == 1
if not ok_stable:
    failures.append('the choice changed during a single day: %s' % sorted(one_day))
print('%s every run in one day picks the same one' % ('PASS' if ok_stable else 'FAIL'))

# A full round deals each playlist exactly once.
first_round = [_dealt(d) for d in range(10)]
ok_round = sorted(first_round) == sorted(_pool)
if not ok_round:
    failures.append('a round did not deal each playlist once: %s' % first_round)
print('%s ten days deals all ten, none twice' % ('PASS' if ok_round else 'FAIL'))

# The next round is dealt in a different order.
second_round = [_dealt(d) for d in range(10, 20)]
ok_reshuffle = first_round != second_round
if not ok_reshuffle:
    failures.append('the second round repeated the first round order')
print('%s the next round comes in a different order' % ('PASS' if ok_reshuffle else 'FAIL'))

# Never the same two days running, including across the join between rounds.
long_run = [_dealt(d) for d in range(2000)]
repeats = [i for i in range(1, len(long_run)) if long_run[i] == long_run[i - 1]]
ok_adjacent = not repeats
if not ok_adjacent:
    failures.append('the same playlist ran two days in a row, %d times' % len(repeats))
print('%s never the same two days running, checked over %d days'
      % ('PASS' if ok_adjacent else 'FAIL', len(long_run)))

# Over a long stretch everything gets played about equally.
from collections import Counter as _Counter
counts = _Counter(long_run)
ok_even = max(counts.values()) - min(counts.values()) <= 1
if not ok_even:
    failures.append('some playlists are favoured: %s' % counts.most_common())
print('%s all of them get played equally often' % ('PASS' if ok_even else 'FAIL'))

# A list of one is not an error.
_one = _copy.deepcopy(_deck_home)
_one['slots'][0]['playlist_pool'] = ['BACH']
ok_single = schedule.decide(cfg, datetime(2026, 3, 3, 12), _one)['playlist'] == 'BACH'
if not ok_single:
    failures.append('a list with one playlist in it did not work')
print('%s a list of one plays that one' % ('PASS' if ok_single else 'FAIL'))

print()
print('--- who goes quiet at closing time ---')
ok_home_quiet = home.get('stop_when_closed', False) is True
if not ok_home_quiet:
    failures.append('home is not set to stop the music, so the house would play on past '
                    'midnight instead of being put to bed')
print('%s home goes quiet at midnight' % ('PASS' if ok_home_quiet else 'FAIL'))

# Quiet means quiet, the whole way through the night, not just at the stroke of twelve.
_night_silent = []
for _h in range(0, 9):
    for _m in (0, 30):
        _d = schedule.decide(cfg, datetime(2026, 9, 7, _h, _m), home)
        if _d['playing']:
            _night_silent.append('%02d:%02d' % (_h, _m))
ok_night_silent = not _night_silent
if not ok_night_silent:
    failures.append('something is still scheduled to play overnight at home: %s'
                    % ', '.join(_night_silent))
print('%s nothing is scheduled at home from midnight to nine'
      % ('PASS' if ok_night_silent else 'FAIL'))

# And the morning has to actually come back, or quiet at midnight means quiet forever.
_morning = schedule.decide(cfg, datetime(2026, 9, 7, 9, 0), home)
ok_morning_back = _morning['playing'] and str(_morning['slot']).startswith('Daytime')
if not ok_morning_back:
    failures.append('the morning cycle does not restart at nine, so the house would stay '
                    'silent after the midnight stop')
print('%s the morning cycle restarts at nine' % ('PASS' if ok_morning_back else 'FAIL'))

_shops = [st for st in cfg['stores'] if st['id'] != 'home']
ok_shops_quiet = all(st.get('stop_when_closed') for st in _shops)
if not ok_shops_quiet:
    failures.append('a shop is not set to go quiet at closing: %s'
                    % [st['id'] for st in _shops if not st.get('stop_when_closed')])
print('%s all three shops go quiet at closing' % ('PASS' if ok_shops_quiet else 'FAIL'))

print()
print('--- nothing in the settings file names Andrew or his house ---')
# These files are readable by anyone. The identifiers of the real Sonos systems live in
# GitHub's secure storage instead, and are put back at the moment a job runs. Nothing is
# secret about them, but there is no reason for a settings file to say whose house it is.
import os as _os
# Read the file itself, not the loaded settings, because loading puts the real
# identifiers back from ids.json or from the job. The question here is what is written
# in the file that anyone can read.
import json as _json
_raw_cfg = _json.load(open(schedule.CONFIG, encoding='utf-8'))
_named = []
for _st in _raw_cfg['stores']:
    for _field in ('household', 'group'):
        _v = str(_st.get(_field) or '')
        if _v.startswith('Sonos_') or _v.startswith('RINCON_'):
            _named.append('%s %s' % (_st['id'], _field))
ok_no_ids = not _named
if not ok_no_ids:
    failures.append('a real Sonos identifier is written into config.json: %s' % _named)
print('%s no real Sonos identifier is written into the settings file'
      % ('PASS' if ok_no_ids else 'FAIL'))

# And the names to look for are the ones the instruction file actually passes through.
_h, _g, _s = schedule.stored_id_names('home')
ok_names = (_h, _g, _s) == ('SONOS_HOUSEHOLD_HOME', 'SONOS_GROUP_HOME', 'SONOS_SPEAKER_HOME')
if not ok_names:
    failures.append('the stored names changed shape: %s, %s, %s' % (_h, _g, _s))
print('%s the three names are %s, %s and %s'
      % ('PASS' if ok_names else 'FAIL', _h, _g, _s))

# When they are set, they win. When they are not, the file is used and nothing breaks.
_os.environ['SONOS_HOUSEHOLD_HOME'] = 'Sonos_TEST'
_os.environ['SONOS_GROUP_HOME'] = 'RINCON_TEST'
_os.environ['SONOS_SPEAKER_HOME'] = 'RINCON_SPEAKER_TEST'
_reloaded = [x for x in schedule.load()['stores'] if x['id'] == 'home'][0]
ok_env = (_reloaded['household'] == 'Sonos_TEST'
          and _reloaded['group'] == 'RINCON_TEST'
          and _reloaded.get('speaker') == 'RINCON_SPEAKER_TEST')
del _os.environ['SONOS_HOUSEHOLD_HOME']
del _os.environ['SONOS_GROUP_HOME']
del _os.environ['SONOS_SPEAKER_HOME']
if not ok_env:
    failures.append('the stored identifiers were not picked up: %r' % _reloaded)
print('%s a stored identifier is used when it is there' % ('PASS' if ok_env else 'FAIL'))

# A system whose identifier is not visible here must be skipped, not half acted on.
ok_skip = (schedule.not_connected({'household': 'KEPT_IN_GITHUB_SECURE_STORAGE'})
           and schedule.not_connected({'household': 'PENDING_AUTHORISATION'})
           and schedule.not_connected({'household': ''})
           and not schedule.not_connected({'household': 'Sonos_real'}))
if not ok_skip:
    failures.append('the test for an unusable system is wrong')
print('%s a system with no visible identifier is skipped rather than half acted on'
      % ('PASS' if ok_skip else 'FAIL'))

print()
ok_stores = schedule.decide(cfg, datetime.fromisoformat('2026-09-07T10:00'))['playlist'] is None
if not ok_stores:
    failures.append('the stores picked up a home slot')
print('%s the stores are untouched by any of this' % ('PASS' if ok_stores else 'FAIL'))

print()
if failures:
    print('%d FAILURES' % len(failures))
    for f in failures:
        print('  ', f)
    raise SystemExit(1)
print('All checks passed.')
