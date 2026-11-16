#!/usr/bin/env python3
"""Prepare account databases for a preserve-data installation, without touching inputs."""
import argparse
from pathlib import Path


def records(path, fields):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'account database missing or unsafe: {path.name}')
    rows = []
    names = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        parts = line.split(':')
        if len(parts) != fields or not parts[0] or parts[0] in names:
            raise ValueError(f'invalid or duplicate account entry: {path.name}')
        names.add(parts[0]); rows.append(parts)
    return rows


def indexed(rows, column):
    out = {}
    for row in rows:
        ident = int(row[column])
        if ident in out and out[ident] != row[0]:
            raise ValueError('duplicate numeric account identifier')
        out[ident] = row[0]
    return out


def merge(existing, incoming):
    old_users, new_users = existing['passwd'], incoming['passwd']
    old_groups, new_groups = existing['group'], incoming['group']
    users_by_name = {x[0]: x for x in old_users}
    groups_by_name = {x[0]: x for x in old_groups}
    used_uids, used_gids = indexed(old_users, 2), indexed(old_groups, 2)
    added_users, added_groups = [], []
    for row in new_groups:
        name, gid = row[0], int(row[2])
        old = groups_by_name.get(name)
        if old:
            if int(old[2]) != gid:
                raise ValueError(f'incompatible system group ID: {name}')
        else:
            if gid in used_gids:
                raise ValueError(f'system group ID conflicts: {name}')
            old_groups.append(row[:]); added_groups.append(name); used_gids[gid] = name
    for row in new_users:
        name, uid, gid = row[0], int(row[2]), int(row[3])
        if 1000 <= uid < 60000:
            raise ValueError('release image unexpectedly contains a regular user')
        old = users_by_name.get(name)
        if old:
            if int(old[2]) != uid or int(old[3]) != gid:
                raise ValueError(f'incompatible system user ID: {name}')
        else:
            if uid in used_uids or gid not in used_gids:
                raise ValueError(f'system user ID or group conflicts: {name}')
            old_users.append(row[:]); added_users.append(name); used_uids[uid] = name
    for file, added in (('shadow', added_users), ('gshadow', added_groups)):
        target = existing[file]
        have = {x[0] for x in target}
        incoming_index = {x[0]: x for x in incoming[file]}
        for name in added:
            if name not in incoming_index:
                raise ValueError(f'new system account missing from {file}: {name}')
            target.append(incoming_index[name][:]); have.add(name)
    if {x[0] for x in old_users} - {x[0] for x in existing['shadow']}:
        raise ValueError('existing account is missing from shadow')
    if {x[0] for x in old_groups} - {x[0] for x in existing['gshadow']}:
        raise ValueError('existing group is missing from gshadow')
    return existing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--existing', required=True, type=Path)
    ap.add_argument('--release', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    formats = {'passwd': 7, 'shadow': 9, 'group': 4, 'gshadow': 4}
    existing = {n: records(args.existing / n, f) for n, f in formats.items()}
    incoming = {n: records(args.release / n, f) for n, f in formats.items()}
    merged = merge(existing, incoming)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, rows in merged.items():
        target = args.out / name
        target.write_text(''.join(':'.join(row) + '\n' for row in rows), encoding='utf-8')
        target.chmod(0o600)
    print('Account merge prepared; existing account IDs and password hashes preserved.')


if __name__ == '__main__':
    main()
