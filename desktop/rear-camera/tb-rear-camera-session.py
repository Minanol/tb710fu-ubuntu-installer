#!/usr/bin/python3
"""Recover rear-camera enumeration if session startup beat device access."""
import subprocess
import time

CAMERA_PATH = '/base/soc@0/cci@ac15000/i2c-bus@1/camera@36'


def camera_present():
    try:
        output = subprocess.check_output(['pw-cli', 'ls', 'Node'], text=True,
                                         stderr=subprocess.DEVNULL, timeout=5)
        return 'libcamera:' + CAMERA_PATH in output
    except (OSError, subprocess.SubprocessError):
        return False


def wait_for_camera(seconds):
    for _ in range(seconds):
        if camera_present():
            return True
        time.sleep(1)
    return False


def main():
    if wait_for_camera(12):
        return
    print('Rear camera not yet enumerated; restarting the session media manager.', flush=True)
    subprocess.run(['systemctl', '--user', 'try-restart', 'wireplumber.service'],
                   timeout=20, check=True)
    if not wait_for_camera(25):
        raise RuntimeError('Rear camera is still unavailable after media-manager restart')


if __name__ == '__main__':
    main()
