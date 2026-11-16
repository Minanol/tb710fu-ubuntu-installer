"""Exercise the real installer rsync filter on disposable trees."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

class PreserveCopyTest(unittest.TestCase):
    def test_existing_home_accounts_and_settings_survive(self):
        script = Path(__file__).with_name('tb-install-single.sh').read_text()
        lines = [line.strip() for line in script.splitlines() if line.startswith('excludes=(') or line.strip().startswith('excludes+=(')]
        self.assertEqual(len(lines), 2)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td); src = base/'new'; dst = base/'old'
            files = {'home/alice/private.txt': ('release', 'precious'),
                     'home/alice/.config/user-setting': ('new', 'my-setting'),
                     'etc/passwd': ('new accounts', 'existing accounts'),
                     'etc/gdm3/custom.conf': ('new login', 'my login'),
                     'etc/NetworkManager/system-connections/wifi': ('new wifi', 'private wifi'),
                     'etc/droidloom/cell.json': ('new owner', 'old owner'),
                     'usr/share/example': ('new system', 'old system')}
            for name, (new, old) in files.items():
                for root, value in ((src,new),(dst,old)):
                    path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(value)
            self.assertIn('rsync -aHAXxc --numeric-ids', script)
            run = '\n'.join(lines) + '\nrsync -aHAXxc --numeric-ids "${excludes[@]}" "$1/" "$2/"\n'
            subprocess.run(['bash','-c',run,'preserve-test',str(src),str(dst)], check=True)
            for name, (new, old) in files.items():
                self.assertEqual((dst/name).read_text(), new if name.startswith('usr/') else old, name)

if __name__ == '__main__': unittest.main()
