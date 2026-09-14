"""Make Andrew's phone buzz with whatever check_status.py said. Runs on the Mac mini.

Written 2026-09-13. The music-job-health task used to report only inside the Claude app, which
does not buzz a phone. Now, when check_status.py exits 1, the task pipes its words into this:

    python3 check_status.py > /tmp/music-status.txt; code=$?
    if [ $code -eq 1 ]; then python3 push_alert.py < /tmp/music-status.txt; fi

It sends through the "Store music" Pushover application, at high priority so it gets past quiet
hours. The two key files sit beside this script and are on the ignore list. Reading and sending
only: nothing here touches a speaker or a setting.
"""
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
HIGH = 1


def read_key(name):
    with open(os.path.join(HERE, name)) as f:
        return f.read().strip()


def main():
    text = sys.stdin.read().strip() or 'check_status.py reported a problem but said nothing.'
    first_line = text.splitlines()[0]
    fields = {
        'token': read_key('pushover-app-token.txt'),
        'user': read_key('pushover-user-key.txt'),
        'title': 'Store music: ' + first_line.split(':')[0],
        'message': text[:1024],
        'priority': HIGH,
    }
    request = urllib.request.Request('https://api.pushover.net/1/messages.json',
                                     data=urllib.parse.urlencode(fields).encode(), method='POST')
    with urllib.request.urlopen(request, timeout=60) as response:
        response.read()
    print('Pushover accepted the alert.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
