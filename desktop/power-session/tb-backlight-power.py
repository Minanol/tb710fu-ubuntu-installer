#!/usr/bin/python3
"""Remember screen brightness, blank physically, and restore on explicit wake."""
import fcntl
import json
import os
from pathlib import Path
import signal
import sys
import tempfile


class Backlight:
    def __init__(self, hardware=None, directory=None):
        self.hardware = Path(hardware or '/sys/class/backlight/sy7758-backlight')
        runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid())))
        self.directory = Path(directory or runtime / 'tb710fu-backlight')
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    def read(self, name):
        return int((self.hardware / name).read_text().strip())

    def write(self, name, value):
        (self.hardware / name).write_text(str(value))

    def apply(self, action):
        with (self.directory / 'lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.directory / 'state.json'
            try:
                data = json.loads(path.read_text())
            except (OSError, ValueError):
                data = {'blanked': False}
            maximum = self.read('max_brightness')
            current = self.read('brightness')
            if action == 'off':
                if not data.get('blanked'):
                    data['saved'] = max(1, current or int(data.get('saved', maximum * .3)))
                data['blanked'] = True
                self.save(path, data)
                self.write('bl_power', 4)
                self.write('brightness', 0)
            elif action == 'on':
                if data.get('blanked') or current == 0:
                    saved = max(1, min(maximum, int(data.get('saved', maximum * .3))))
                    self.write('bl_power', 0)
                    self.write('brightness', saved)
                    data.update(blanked=False, saved=saved)
                    self.save(path, data)
            elif action == 'enforce':
                # Compositor fade/wake updates must not relight a screen requested off.
                if data.get('blanked'):
                    if self.read('bl_power') != 4:
                        self.write('bl_power', 4)
                    if current != 0:
                        self.write('brightness', 0)
            elif action != 'status':
                raise ValueError('unknown action')
            return data

    @staticmethod
    def save(path, data):
        fd, name = tempfile.mkstemp(prefix='.state-', dir=path.parent)
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream)
        os.replace(name, path)


def watch():
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib
    controller = Backlight()
    loop = GLib.MainLoop()
    proxy = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE,
        None, 'org.gnome.ScreenSaver', '/org/gnome/ScreenSaver', 'org.gnome.ScreenSaver', None)
    def update(active):
        controller.apply('off' if active else 'on')
        print('locked: backlight zero' if active else 'unlocked: brightness restored', flush=True)
    def changed(proxy, sender, name, values):
        if name == 'ActiveChanged':
            try:
                update(values.unpack()[0])
            except Exception as exc:
                print('lock backlight error:', str(exc), flush=True)
    def enforce():
        try:
            controller.apply('enforce')
        except Exception as exc:
            print('backlight guard error:', str(exc), flush=True)
        return True
    proxy.connect('g-signal', changed)
    result = proxy.call_sync('GetActive', None, Gio.DBusCallFlags.NONE, 2000, None)
    update(result.unpack()[0])
    GLib.timeout_add(500, enforce)
    for number in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, number, lambda: (loop.quit(), False)[1])
    loop.run()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: tb-backlight-power off|on|status|--watch')
    if sys.argv[1] == '--watch':
        watch()
    else:
        print(json.dumps(Backlight().apply(sys.argv[1])))
