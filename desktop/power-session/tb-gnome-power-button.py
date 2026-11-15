#!/usr/bin/python3
"""Power short press locks; long press requests shutdown; lid closure locks."""
import glob
import os
import select
import struct
import subprocess
import time
from pathlib import Path

EVENT = struct.Struct('@llHHi')
POWER = 116
LONG_SECONDS = 1.0

def call(*args):
    try:
        result = subprocess.run(('busctl', '--user', 'call', *args), timeout=5,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                check=False)
        if result.returncode:
            print('desktop action failed:', result.stderr.decode(errors='replace').strip(), flush=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print('desktop action error:', exc, flush=True)

def lock():
    call('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver', 'org.gnome.ScreenSaver', 'Lock')

def backlight_power(action):
    subprocess.run(('/usr/local/bin/tb-backlight-power', action),
                   timeout=3, check=True, stdout=subprocess.DEVNULL)

def short_press():
    """Lock and blank physically; next press restores the saved brightness."""
    try:
        locked = subprocess.run(
            ('busctl', '--user', 'call', 'org.gnome.ScreenSaver',
             '/org/gnome/ScreenSaver', 'org.gnome.ScreenSaver', 'GetActive'),
            timeout=2, capture_output=True, text=True, check=True).stdout.strip()
        base = Path('/sys/class/backlight/sy7758-backlight')
        if locked != 'b true':
            lock()
            backlight_power('off')
        elif (base / 'brightness').read_text().strip() == '0' or (base / 'bl_power').read_text().strip() == '4':
            subprocess.run(('busctl', '--user', 'set-property',
                'org.gnome.Mutter.DisplayConfig', '/org/gnome/Mutter/DisplayConfig',
                'org.gnome.Mutter.DisplayConfig', 'PowerSaveMode', 'i', '0'),
                timeout=3, check=True, capture_output=True, text=True)
            backlight_power('on')
        else:
            backlight_power('off')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('power button action failed:', exc, flush=True)

def shutdown_dialog():
    backlight_power('on')
    # The local menu requires an explicit selection; it has no shutdown timer.
    call('org.tb.PowerMenu', '/org/tb/PowerMenu', 'org.tb.PowerMenu', 'Open')

def main():
    override = os.environ.get('TB_POWER_KEY_DEVICE')
    keys = [override] if override else sorted(glob.glob('/dev/input/by-path/*:pwrkey-event'))
    if not keys:
        raise RuntimeError('power key not found')
    fds = {os.open(keys[0], os.O_RDONLY | os.O_NONBLOCK): 'power'}
    lid_override = os.environ.get('TB_LID_DEVICE')
    if lid_override:
        fds[os.open(lid_override, os.O_RDONLY | os.O_NONBLOCK)] = 'lid'
    for name in ([] if lid_override or os.environ.get('TB_DISABLE_LID') else glob.glob('/sys/class/input/event*/device/name')):
        try:
            path = Path(name)
            if path.read_text().strip() == 'gpio-keys' and int((path.parent / 'capabilities/sw').read_text().strip(), 16) & 1:
                event = path.parts[-3]
                fds[os.open('/dev/input/' + event, os.O_RDONLY | os.O_NONBLOCK)] = 'lid'
                break
        except (OSError, ValueError):
            continue
    pressed = None
    long_done = False
    while True:
        timeout = max(0, LONG_SECONDS - (time.monotonic() - pressed)) if pressed is not None and not long_done else None
        ready, _, _ = select.select(list(fds), [], [], timeout)
        if not ready and pressed is not None and not long_done:
            long_done = True
            shutdown_dialog()
            continue
        for fd in ready:
            try:
                data = os.read(fd, EVENT.size * 16)
            except BlockingIOError:
                continue
            if not data:
                raise OSError('input disconnected')
            for offset in range(0, len(data) - EVENT.size + 1, EVENT.size):
                _, _, event_type, code, value = EVENT.unpack_from(data, offset)
                if fds[fd] == 'power' and event_type == 1 and code == POWER:
                    if value == 1 and pressed is None:
                        pressed, long_done = time.monotonic(), False
                    elif value == 0 and pressed is not None:
                        if not long_done:
                            short_press()
                        pressed, long_done = None, False
                elif fds[fd] == 'lid' and (event_type, code, value) == (5, 0, 1):
                    lock()

if __name__ == '__main__':
    main()
