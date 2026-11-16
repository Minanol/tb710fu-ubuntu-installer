#!/usr/bin/python3
"""Bind an unclaimed clean-install Droidloom configuration to its first desktop user."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, '/usr/local/lib')
from tb710fu_session import active_user

MARKER = Path('/etc/tb710fu/release-owner-unclaimed')
CONFIG = Path('/etc/droidloom/cell.json')


def configure(document, uid):
    if not isinstance(uid, int) or uid < 1000 or uid >= 60000:
        raise ValueError('unsupported desktop UID')
    result = dict(document)
    result['host_uid'] = uid
    result['data_dir'] = f'/var/lib/droidloom/users/{uid}/data'
    result['runtime_dir'] = f'/run/droidloom/cells/u{uid}'
    result['denial_socket'] = f'/run/user/{uid}/droidloom/native-bridge.sock'
    return result


def main():
    while MARKER.exists():
        account = active_user()
        if not account:
            time.sleep(2)
            continue
        if MARKER.is_symlink() or CONFIG.is_symlink() or not CONFIG.is_file():
            raise RuntimeError('unsafe first-user configuration')
        config = configure(json.loads(CONFIG.read_text(encoding='utf-8')), account[0])
        fd, name = tempfile.mkstemp(prefix='.cell-', dir=CONFIG.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(config, stream, indent=2, ensure_ascii=False)
                stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.chmod(name, 0o644)
            os.replace(name, CONFIG)
            MARKER.unlink()
        finally:
            if os.path.exists(name):
                os.unlink(name)
        print('Initial desktop owner configured.', flush=True)
        # On a clean install the daemon is held until this owner is known.
        subprocess.run(['systemctl', 'start', 'droidloomd.service'], check=False, timeout=30)


if __name__ == '__main__':
    main()
