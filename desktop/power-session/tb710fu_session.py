#!/usr/bin/python3
"""Find the active local graphical user without assuming an account name or UID."""
import pwd
import subprocess


def active_user():
    try:
        session = subprocess.check_output(
            ['loginctl', 'show-seat', 'seat0', '-p', 'ActiveSession', '--value'],
            text=True, timeout=3, stderr=subprocess.DEVNULL).strip()
        if not session:
            return None
        output = subprocess.check_output(
            ['loginctl', 'show-session', session, '-p', 'User', '-p', 'Seat',
             '-p', 'Type', '-p', 'Class', '-p', 'Active'],
            text=True, timeout=3, stderr=subprocess.DEVNULL)
        props = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
        if (props.get('Seat') != 'seat0' or props.get('Active') != 'yes' or
                props.get('Class') != 'user' or props.get('Type') not in ('wayland', 'x11')):
            return None
        uid = int(props['User'])
        account = pwd.getpwuid(uid)
        return uid, account.pw_name
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return None


def user_command(user, command):
    uid, name = user
    runtime = f'/run/user/{uid}'
    return ['runuser', '-u', name, '--', 'env', f'XDG_RUNTIME_DIR={runtime}',
            f'DBUS_SESSION_BUS_ADDRESS=unix:path={runtime}/bus', *command]
