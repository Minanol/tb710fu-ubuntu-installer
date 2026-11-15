#!/usr/bin/env python3
"""Create a boot-menu label candidate from the verified original Ubuntu boot."""
import hashlib
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
src = root / 'artifacts/ubuntu-kshim-main.img'
out = root / 'artifacts/ubuntu-release-dev/ubuntu-boot-menu-candidate.img'
tool = root / 'sources/TB710FU-Archlinux/build/tools/avbtool.py'
key = root / 'sources/TB710FU-Archlinux/build/tools/testkey_rsa4096.pem'
raw = src.read_bytes()
assert hashlib.sha256(raw).hexdigest() == '49e01404b2f7725a3e04d4161089f7bbc6b86078dad60c82f237dbd070e7f16a'
info = subprocess.check_output([sys.executable, str(tool), 'info_image', '--image', str(src)], text=True)
orig = int(re.search(r'Original image size:\s+(\d+)', info).group(1))
salt = re.search(r'Salt:\s+([0-9a-f]+)', info).group(1)
rollback = re.search(r'Rollback Index:\s+(\d+)', info).group(1)
props = list(dict(re.findall(r"Prop: (\S+) -> '([^']*)'", info)).items())
body = bytearray(raw[:orig])
page = 4096
kernel_size = struct.unpack_from('<I', body, 8)[0]
man_off, man_size = struct.unpack_from('<QQ', body, page + 0x20)
start = page + man_off
man = bytes(body[start:start + man_size])
assert man[:4] == b'KPMF' and man_size == 320
assert page + kernel_size == start + man_size
assert not any(body[start + man_size:start + man_size + 4])
count = struct.unpack_from('<I', man, 8)[0]
entries = []
pos = 60
for _ in range(count):
    n = struct.unpack_from('<I', man, pos + 52)[0]
    end = pos + 56 + ((n + 3) // 4) * 4
    entry = bytearray(man[pos:end])
    name = bytes(entry[56:56+n])
    if name == b'Arch':
        struct.pack_into('<I', entry, 52, 6)
        entry = entry[:56] + b'Ubuntu\0\0'
    entries.append((name, bytes(entry)))
    pos = end
assert pos == man_size and [x[0] for x in entries].count(b'Arch') == 1
new_man = man[:60] + b''.join(x[1] for x in entries)
assert len(new_man) == man_size + 4
body[start:start + len(new_man)] = new_man
struct.pack_into('<I', body, 8, kernel_size + 4)
runtime_size = struct.unpack_from('<Q', body, page + 0x10)[0]
struct.pack_into('<Q', body, page + 0x10, runtime_size + 4)
struct.pack_into('<Q', body, page + 0x28, len(new_man))
tmp = out.with_suffix('.body')
tmp.write_bytes(body)
args = [sys.executable, str(tool), 'add_hash_footer', '--image', str(tmp),
        '--partition_name', 'boot', '--partition_size', '100663296', '--key', str(key),
        '--algorithm', 'SHA256_RSA4096', '--rollback_index', rollback, '--salt', salt]
for name, value in props:
    args += ['--prop', f'{name}:{value}']
subprocess.run(args, check=True)
tmp.replace(out)
with tempfile.TemporaryDirectory(prefix='tb-boot-label-') as directory:
    named = Path(directory) / 'boot.img'
    named.symlink_to(out)
    subprocess.run([sys.executable, str(tool), 'verify_image', '--image', str(named), '--key', str(key)], check=True)
print('Built untested menu-label candidate:', out)
print('SHA256:', hashlib.sha256(out.read_bytes()).hexdigest())
