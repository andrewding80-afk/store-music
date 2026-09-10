"""Talking to Sonos.

⚠️ READ THIS BEFORE TRUSTING IT.

Every address below comes from Sonos's published developer documentation. **None of it has
been run against a real system yet.** The whole point of testing on the home system first is
to find out which parts of this are right.

Sonos's own community support says the consumer app cannot control speakers from outside the
network. The developer interface is a separate thing and is documented as cloud based, but
that is a claim from a document, not a result. Treat everything here as a proposal until the
home test passes.

No outside libraries. Standard library only, matching the rest of Andrew's code.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

AUTH_URL = 'https://api.sonos.com/login/v3/oauth'
TOKEN_URL = 'https://api.sonos.com/login/v3/oauth/access'
API = 'https://api.ws.sonos.com/control/api/v1'

HERE = os.path.dirname(__file__)
TOKEN_DIR = os.path.join(HERE, 'tokens')
SECRETS = os.path.join(HERE, 'secrets.json')


class SonosError(Exception):
    pass


# ---------------------------------------------------------------- plumbing

def _request(url, method='GET', body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')[:400]
        raise SonosError('%s %s -> %s %s' % (method, url, e.code, detail))
    except urllib.error.URLError as e:
        raise SonosError('could not reach %s: %s' % (url, e.reason))


def _secrets():
    """The Key and Secret.

    On Andrew's laptop these live in secrets.json. On GitHub's machines there are no
    files of his, so they arrive as settings on the job instead. Same values, two homes,
    and nothing in the rest of this file has to know which.
    """
    env_id = os.environ.get('SONOS_CLIENT_ID')
    env_secret = os.environ.get('SONOS_CLIENT_SECRET')
    if env_id and env_secret:
        return {'client_id': env_id, 'client_secret': env_secret}

    if not os.path.exists(SECRETS):
        raise SonosError(
            'secrets.json is missing, and SONOS_CLIENT_ID and SONOS_CLIENT_SECRET are not '
            'set either. One or the other has to be there. See SETUP.md.')
    with open(SECRETS, encoding='utf-8') as f:
        return json.load(f)


def _env_token_name(store_id):
    """home -> SONOS_TOKEN_HOME,  west-harlem -> SONOS_TOKEN_WEST_HARLEM"""
    return 'SONOS_TOKEN_' + store_id.upper().replace('-', '_')


def _load_token(store_id):
    """Returns the saved pass, and whether it came from a setting rather than a file.

    Checked 2026-09-05 on the real account: Sonos hands back the same permanent pass
    every time it refreshes. So when it arrives as a setting there is nothing to write
    back, which is the whole reason this can run on GitHub's machines.
    """
    raw = os.environ.get(_env_token_name(store_id))
    if raw:
        return json.loads(raw), True

    path = _token_path(store_id)
    if not os.path.exists(path):
        raise SonosError(
            'System %r has not been connected. Run connect.py for it, or set %s. '
            'See SETUP.md.' % (store_id, _env_token_name(store_id)))
    with open(path, encoding='utf-8') as f:
        return json.load(f), False


def _save_token(store_id, tok, from_setting):
    if from_setting:
        return          # nothing to write, and nothing has changed that would need writing
    os.makedirs(TOKEN_DIR, exist_ok=True)
    with open(_token_path(store_id), 'w', encoding='utf-8') as f:
        json.dump(tok, f, indent=2)


# ---------------------------------------------------------------- tokens

def _token_path(store_id):
    return os.path.join(TOKEN_DIR, '%s.json' % store_id)


def authorise_url(redirect_uri):
    """Step one of connecting a store. Andrew opens this, signs in, approves."""
    s = _secrets()
    q = urllib.parse.urlencode({
        'client_id': s['client_id'],
        'response_type': 'code',
        'state': 'store-music',
        'scope': 'playback-control-all',
        'redirect_uri': redirect_uri,
    })
    return '%s?%s' % (AUTH_URL, q)


def exchange_code(store_id, code, redirect_uri):
    """Step two. Turns the one-time code from the browser into a lasting token."""
    s = _secrets()
    basic = urllib.parse.quote(s['client_id']) + ':' + urllib.parse.quote(s['client_secret'])
    import base64
    auth = base64.b64encode(basic.encode()).decode()
    body = urllib.parse.urlencode({
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method='POST')
    req.add_header('Authorization', 'Basic ' + auth)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urllib.request.urlopen(req, timeout=20) as resp:
        tok = json.loads(resp.read())
    tok['obtained_at'] = int(time.time())
    os.makedirs(TOKEN_DIR, exist_ok=True)
    with open(_token_path(store_id), 'w', encoding='utf-8') as f:
        json.dump(tok, f, indent=2)
    return tok


def access_token(store_id):
    """A usable token, refreshed if it has expired. One token file per store, so
    connecting a new store never disturbs one that already works."""
    tok, from_setting = _load_token(store_id)

    age = time.time() - tok.get('obtained_at', 0)
    if age < tok.get('expires_in', 3600) - 120:
        return tok['access_token']

    s = _secrets()
    import base64
    basic = urllib.parse.quote(s['client_id']) + ':' + urllib.parse.quote(s['client_secret'])
    auth = base64.b64encode(basic.encode()).decode()
    body = urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'refresh_token': tok['refresh_token'],
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method='POST')
    req.add_header('Authorization', 'Basic ' + auth)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urllib.request.urlopen(req, timeout=20) as resp:
        new = json.loads(resp.read())
    new['obtained_at'] = int(time.time())
    new.setdefault('refresh_token', tok['refresh_token'])
    _save_token(store_id, new, from_setting)
    return new['access_token']


def _auth_headers(store_id):
    return {'Authorization': 'Bearer ' + access_token(store_id)}


# ---------------------------------------------------------------- reading

def households(store_id):
    return _request('%s/households' % API, headers=_auth_headers(store_id)).get('households', [])


def groups(store_id, household):
    url = '%s/households/%s/groups' % (API, household)
    return _request(url, headers=_auth_headers(store_id))


def group_for_speaker(store_id, household, speaker_id):
    """The group that speaker is in RIGHT NOW, or None if it is not there.

    Written 2026-09-10, the morning two stores lost their music. A group id is a
    speaker's serial plus a number that is regenerated every time the speakers
    re-form a group, so it dies on any wifi drop, power cut, or somebody tapping
    group in the app. A speaker's serial is the hardware and survives all of it.

    Matches on playerIds rather than the coordinator, because home's failure that
    morning was the coordinator itself moving to a different speaker when the
    Bedroom one dropped off.
    """
    data = groups(store_id, household)
    for g in data.get('groups', []):
        if speaker_id in (g.get('playerIds') or []):
            return g.get('id')
    return None


def favourites(store_id, household):
    url = '%s/households/%s/favorites' % (API, household)
    return _request(url, headers=_auth_headers(store_id)).get('items', [])


def now_playing(store_id, group_id):
    """What is playing right now. Used to avoid restarting something already correct,
    and to notice a store that has gone silent."""
    url = '%s/groups/%s/playbackMetadata' % (API, group_id)
    return _request(url, headers=_auth_headers(store_id))


def playback_status(store_id, group_id):
    url = '%s/groups/%s/playback' % (API, group_id)
    return _request(url, headers=_auth_headers(store_id))


# ---------------------------------------------------------------- acting

def find_favourite(store_id, household, name):
    """Match a favourite by its name, because names are the interface between
    config.json and Sonos. Exact match first, then a forgiving one."""
    items = favourites(store_id, household)
    for it in items:
        if it.get('name', '').strip() == name.strip():
            return it
    lowered = name.strip().lower()
    for it in items:
        if it.get('name', '').strip().lower() == lowered:
            return it
    return None


# Andrew's standing rule, 2026-09-10: every playlist at every location shuffles,
# repeats and crossfades. Repeat is not a preference, it is what stops the music
# running out mid-slot and the leave-it-off rule then assuming he wanted silence.
# Crossfade is his taste call, decided the same day after hearing both.
WANTED_PLAY_MODES = {'shuffle': True, 'repeat': True, 'crossfade': True}


def token_age_days(store_id):
    """How old the saved pass is, in days, or None if it cannot be read.

    Never returns any part of the pass itself, only its age.

    Written 2026-09-10 because a token died and nobody could say why. The code says
    Sonos hands back the same permanent pass on every refresh, checked on 2026-09-05,
    and yet Central Harlem's came back 401 Invalid Token. Both cannot be true.

    Re-authorising was the obvious suspect and is ruled out: West Harlem was
    re-authorised on this machine the same morning and its GitHub copy kept working.

    So the question is open, and this is what will answer it. If tokens die at a
    certain age, a few months of this recorded beside each failure will show it. A
    question you cannot answer today becomes one that answers itself, which beats
    guessing now.
    """
    try:
        tok, _from_setting = _load_token(store_id)
        got = tok.get('obtained_at')
        if not got:
            return None
        return round((time.time() - got) / 86400.0, 1)
    except Exception:
        return None


def is_a_track_list(favourite):
    """True for a Spotify playlist, False for a radio stream.

    Shuffle, repeat and crossfade are properties of a list of tracks. A radio stream
    has no list to shuffle and no gaps to fade between. Andrew's home runs Calm Radio
    stations through the day and Spotify playlists in the evening, so the rule has to
    follow the content rather than the store.

    Read off the data, not a list of service names: Sonos reports resource.type as
    PLAYLIST or STREAM. Naming the services I happen to know about is the mistake that
    has cost us all day.
    """
    return ((favourite or {}).get('resource') or {}).get('type') == 'PLAYLIST'


def playing_a_track_list(store_id, group_id):
    """True when what is playing RIGHT NOW is a list of tracks rather than a stream.

    Written 2026-09-10 after Andrew asked whether shuffle and crossfade were on
    everywhere and home came back with all three off. The hold only looked at the
    playlist the schedule wanted, and home's daytime slot is a Calm Radio stream, so
    a track list Andrew started by hand sat there unshuffled with nothing watching.

    Andrew's rule is about playlists, not about slots. The same reading, taken from
    what is on rather than what was planned.
    """
    container = now_playing(store_id, group_id).get('container') or {}
    return str(container.get('type', '')).upper() == 'PLAYLIST'


def play_modes(store_id, group_id):
    return playback_status(store_id, group_id).get('playModes') or {}


def set_play_modes(store_id, group_id, modes):
    url = '%s/groups/%s/playback/playMode' % (API, group_id)
    return _request(url, method='POST', body={'playModes': modes},
                    headers=_auth_headers(store_id))


def wrong_play_modes(store_id, group_id):
    """Which of the wanted modes are not set. Empty means all is well."""
    now = play_modes(store_id, group_id)
    return {k: v for k, v in WANTED_PLAY_MODES.items() if now.get(k) is not v}


def play_favourite(store_id, group_id, favourite_id):
    url = '%s/groups/%s/favorites' % (API, group_id)
    return _request(url, method='POST', body={
        'favoriteId': favourite_id,
        'playOnCompletion': True,
        'playModes': WANTED_PLAY_MODES,
    }, headers=_auth_headers(store_id))


def set_volume(store_id, group_id, volume):
    url = '%s/groups/%s/groupVolume' % (API, group_id)
    return _request(url, method='POST', body={'volume': int(volume)},
                    headers=_auth_headers(store_id))


def pause(store_id, group_id):
    url = '%s/groups/%s/playback/pause' % (API, group_id)
    return _request(url, method='POST', body={}, headers=_auth_headers(store_id))

def player_volume(store_id, player_id):
    """One speaker's own volume, separate from the volume of its group."""
    url = '%s/players/%s/playerVolume' % (API, player_id)
    return _request(url, headers=_auth_headers(store_id))


def set_player_volume(store_id, player_id, volume):
    """Set one speaker's own volume. Unproven until speakers.py reports levels."""
    url = '%s/players/%s/playerVolume' % (API, player_id)
    return _request(url, method='POST', body={'volume': int(volume)},
                    headers=_auth_headers(store_id))


def players(store_id, household):
    """Every individual speaker on a system, as {name: id}."""
    data = groups(store_id, household)
    return dict((p.get('name'), p.get('id')) for p in data.get('players', []))


def group_volume(store_id, group_id):
    """The volume of a whole group, as it is right now."""
    url = '%s/groups/%s/groupVolume' % (API, group_id)
    return _request(url, headers=_auth_headers(store_id))
