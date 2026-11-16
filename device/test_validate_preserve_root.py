import tempfile
import unittest
from pathlib import Path
import validate_preserve_root as v


class RootValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for d in ('usr/lib', 'var/lib/dpkg', 'etc', 'home/alice'):
            (self.root / d).mkdir(parents=True)
        (self.root / 'usr/lib/os-release').write_text('ID=ubuntu\n')
        (self.root / 'var/lib/dpkg/status').write_text('')
        (self.root / 'etc/passwd').write_text('root:x:0:0:root:/root:/bin/bash\nalice:x:1234:1234::/home/alice:/bin/bash\n')
        (self.root / 'etc/fstab').write_text('UUID=example / ext4 defaults 0 1\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_supported_ubuntu(self):
        self.assertEqual(v.validate(self.root), 1)

    def test_rejects_non_ubuntu(self):
        (self.root / 'usr/lib/os-release').write_text('ID=arch\n')
        with self.assertRaisesRegex(ValueError, 'not an Ubuntu'):
            v.validate(self.root)

    def test_rejects_separate_home(self):
        (self.root / 'etc/fstab').write_text('UUID=example /home ext4 defaults 0 2\n')
        with self.assertRaisesRegex(ValueError, 'separate or remote'):
            v.validate(self.root)

    def test_rejects_external_home_symlink(self):
        (self.root / 'home/alice').rmdir()
        (self.root / 'home/alice').symlink_to('/tmp')
        with self.assertRaises(ValueError):
            v.validate(self.root)


if __name__ == '__main__':
    unittest.main()
