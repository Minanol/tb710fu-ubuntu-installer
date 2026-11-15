#!/usr/bin/python3
"""Handle the TB710FU cover for the active local graphical session."""
import subprocess
import sys
import time
from datetime import timedelta
import gpiod
from gpiod.line import Direction, Edge, Value
sys.path.insert(0, '/usr/local/lib')
from tb710fu_session import active_user, user_command

CHIP = '/dev/gpiochip0'
LINE = 66


def run_as(user, command):
    return subprocess.run(user_command(user, command), timeout=5, check=True,
                          text=True, capture_output=True)


def cover_event(closed):
    user = active_user()
    if user is None:
        print('no active graphical user; cover event skipped', flush=True)
        return
    try:
        if closed:
            state = run_as(user, ['busctl', '--user', 'call', 'org.gnome.ScreenSaver',
                '/org/gnome/ScreenSaver', 'org.gnome.ScreenSaver', 'GetActive']).stdout.strip()
            if state != 'b true':
                run_as(user, ['busctl', '--user', 'call', 'org.gnome.ScreenSaver',
                    '/org/gnome/ScreenSaver', 'org.gnome.ScreenSaver', 'Lock'])
        mode = '3' if closed else '0'
        run_as(user, ['busctl', '--user', 'set-property', 'org.gnome.Mutter.DisplayConfig',
            '/org/gnome/Mutter/DisplayConfig', 'org.gnome.Mutter.DisplayConfig',
            'PowerSaveMode', 'i', mode])
        run_as(user, ['/usr/local/bin/tb-backlight-power', 'off' if closed else 'on'])
        print('cover closed' if closed else 'cover opened', flush=True)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'cover action failed: {exc}', flush=True)


def main():
    settings = gpiod.LineSettings(direction=Direction.INPUT, edge_detection=Edge.BOTH)
    with gpiod.request_lines(CHIP, consumer='tb710fu-cover-hall', config={LINE: settings}) as req:
        print('monitoring GPIO 66; low=closed, high=open', flush=True)
        while True:
            if not req.wait_edge_events(timedelta(seconds=30)):
                continue
            req.read_edge_events()
            time.sleep(.15)
            while req.wait_edge_events(timedelta(seconds=0)):
                req.read_edge_events()
            cover_event(req.get_value(LINE) == Value.INACTIVE)


if __name__ == '__main__':
    main()
