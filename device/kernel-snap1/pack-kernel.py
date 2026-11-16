#!/usr/bin/env python3
"""Replace only Linux in the inspected boot bundle. Does not access a device."""
import argparse
import hashlib
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

LIVE_BOOT = '820d71fce5046b594a0c802623e9a658b3b6f6fa0f976f0090c6f76e9b8258c9'
LINUX = '219f7191d7751c724ccf8abe1fe9bef6c33996814e24177a0a3c1c1f8f1da955'
DTB = '639f1930047b4487396943b420960623487cb1829f343c6e0236d039ab8a560f'
SHIM = 'f83e6ccebe752005f16a8637352ee8c4dbe84f6449a12f3d4462357ef011d1cc'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'linux', 'output', 'avbtool', 'test-key'):
        ap.add_argument('--' + name, required=True, type=Path)
    a = ap.parse_args()
    assert not a.output.exists(), 'Output must be a new file'
    image = a.baseline.read_bytes()
    assert digest(image) == LIVE_BOOT, 'Current inspected boot required'
    assert image[:8] == b'ANDROID!' and len(image) == 100663296
    assert struct.unpack_from('<I', image, 12)[0] == 0, 'Unexpected ramdisk'
    size = struct.unpack_from('<I', image, 8)[0]
    kernel = image[4096:4096 + size]
    moff, msize = struct.unpack_from('<QQ', kernel, 32)
    assert kernel[56:60] == b'ARM\x64' and moff + msize == len(kernel)
    manifest = bytearray(kernel[moff:])
    assert struct.unpack_from('<IHHIII', manifest) == (0x464d504b, 0, 1, 4, 1, 1000)
    entries, pos = [], 60
    for _ in range(4):
        fields = struct.unpack_from('<QQIIQIIIQI', manifest, pos)
        name = bytes(manifest[pos+56:pos+56+fields[-1]]).decode()
        entries.append((pos, fields, name))
        pos = (pos + 56 + fields[-1] + 3) & ~3
    assert pos == len(manifest)
    lp, lf, _ = next(e for e in entries if e[2] == 'Ubuntu' and e[1][2] == 1)
    dp, df, _ = next(e for e in entries if e[1][2] == 5)
    _, sf, _ = next(e for e in entries if e[1][2] == 3)
    assert digest(kernel[lf[0]:lf[0]+lf[1]]) == LINUX
    dtb = kernel[df[0]:df[0]+df[1]]
    assert digest(dtb) == DTB
    assert digest(kernel[sf[0]:sf[0]+sf[1]]) == SHIM
    assert sf[0] + sf[1] <= lf[0] and lf[0] + lf[1] == df[0]
    linux = a.linux.read_bytes()
    assert linux[56:60] == b'ARM\x64'
    assert b'Linux version 7.2.6-tb710fu-snap1 ' in linux
    doff = (lf[0] + len(linux) + 7) & ~7
    new_moff = (doff + len(dtb) + 3) & ~3
    struct.pack_into('<Q', manifest, lp + 8, len(linux))
    struct.pack_into('<Q', manifest, dp, doff)
    packed = bytearray(kernel[:lf[0]]) + linux
    packed += bytes(doff-len(packed)) + dtb
    packed += bytes(new_moff-len(packed)) + manifest
    struct.pack_into('<Q', packed, 16, len(packed))
    struct.pack_into('<Q', packed, 32, new_moff)
    assert len(packed) < 86*1024*1024, 'ABL raw load limit exceeded'
    assert packed[lf[0]:lf[0]+len(linux)] == linux
    assert digest(packed[doff:doff+len(dtb)]) == DTB
    assert digest(packed[sf[0]:sf[0]+sf[1]]) == SHIM
    header = bytearray(image[:4096])
    struct.pack_into('<I', header, 8, len(packed))
    body = header + packed + bytes((-len(packed)) % 4096)
    info = subprocess.check_output([sys.executable, str(a.avbtool), 'info_image', '--image', str(a.baseline)], text=True)
    salt = re.search(r'Salt:\s+([0-9a-f]+)', info).group(1)
    rollback = re.search(r'Rollback Index:\s+(\d+)', info).group(1)
    a.output.write_bytes(body)
    cmd = [sys.executable, str(a.avbtool), 'add_hash_footer', '--image', str(a.output),
           '--partition_name', 'boot', '--partition_size', str(len(image)),
           '--key', str(a.test_key), '--algorithm', 'SHA256_RSA4096',
           '--rollback_index', rollback, '--salt', salt]
    for k, v in dict(re.findall(r"Prop: (\S+) -> '([^']*)'", info)).items():
        cmd += ['--prop', f'{k}:{v}']
    subprocess.run(cmd, check=True)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td)/'boot.img'
        path.symlink_to(a.output.resolve())
        subprocess.run([sys.executable, str(a.avbtool), 'verify_image', '--image', str(path), '--key', str(a.test_key)], check=True)
    print('OFFLINE candidate', digest(a.output.read_bytes()), 'packed bytes', len(packed))


if __name__ == '__main__':
    main()
