#!/usr/bin/env python3
"""Fail closed unless a mounted root is a supported existing Ubuntu installation."""
import argparse
from pathlib import Path


def within(root, value):
    path = root / value.lstrip('/')
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError('existing path escapes the target filesystem')
    return resolved


def validate(root):
    root = root.resolve(strict=True)
    release = root / 'usr/lib/os-release'
    if release.is_symlink() or not release.is_file():
        raise ValueError('Ubuntu release metadata is unavailable')
    fields = dict(line.split('=', 1) for line in release.read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
    if fields.get('ID', '').strip('"\'') != 'ubuntu':
        raise ValueError('target is not an Ubuntu installation')
    if not (root / 'var/lib/dpkg/status').is_file():
        raise ValueError('Ubuntu package database is missing')
    home = root / 'home'
    if home.is_symlink() or not home.is_dir():
        raise ValueError('unsupported home directory layout')
    passwd = root / 'etc/passwd'
    if passwd.is_symlink() or not passwd.is_file():
        raise ValueError('existing account database is unsafe')
    users = 0
    for line in passwd.read_text(encoding='utf-8').splitlines():
        row = line.split(':')
        if len(row) != 7:
            raise ValueError('invalid existing account database')
        uid = int(row[2])
        if 1000 <= uid < 60000:
            users += 1
            if not row[5].startswith('/home/') or not within(root, row[5]).is_relative_to(home.resolve()):
                raise ValueError('a user home is outside the supported /home layout')
            if not within(root, row[5]).is_dir():
                raise ValueError('user home directory is missing')
    if not users:
        raise ValueError('no existing regular account was found')
    fstab = root / 'etc/fstab'
    if fstab.is_symlink() or not fstab.is_file():
        raise ValueError('existing fstab is unavailable')
    for line in fstab.read_text(errors='strict').splitlines():
        parts = line.split()
        if len(parts) >= 2 and not line.lstrip().startswith('#'):
            mountpoint = parts[1].replace('\\040', ' ')
            if mountpoint == '/home' or mountpoint.startswith('/home/'):
                raise ValueError('separate or remote home mounts require manual migration')
    return users


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    count = validate(args.root)
    print(f'Existing Ubuntu validated; {count} regular account(s) have supported home directories.')
