#!/usr/bin/env python3
"""Create a private, untested boot candidate with installer NBD precedence.

Only accepts the verified original TB710FU Ubuntu baseline. Does not access any
physical device or publish output. The result requires DTB installer flags and
full offline and hardware verification before it may be used.
"""
import argparse
import gzip
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE = '49e01404b2f7725a3e04d4161089f7bbc6b86078dad60c82f237dbd070e7f16a'
START = 4096 + 41943040 + 36690316
SIZE = 1357060
OLD = b'for want in arch archdata steamos; do try_partition $want && break; done'
NEW = b'grep -Eq "(^| )tb710fu[.]install=(single|dual)( |$)" /proc/cmdline || for want in arch archdata steamos; do try_partition $want && break; done'


def patch_init(archive):
    archive = bytearray(archive)
    pos = 0
    while archive[pos:pos+6] in (b'070701', b'070702'):
        values = [int(archive[pos+6+j*8:pos+14+j*8], 16) for j in range(13)]
        size, namesize = values[6], values[11]
        begin = pos + 110
        name = bytes(archive[begin:begin+namesize-1])
        data = (begin + namesize + 3) & ~3
        if name == b'init':
            init = bytes(archive[data:data+size])
            if init.count(OLD) != 1:
                raise ValueError('Unexpected init script')
            init = init.replace(OLD, NEW).rstrip(b'\n')
            if len(init) > size:
                raise ValueError('Patched init does not fit its cpio record')
            archive[data:data+size] = init + b'\n' * (size - len(init))
            return bytes(archive)
        pos = (data + size + 3) & ~3
    raise ValueError('No init file in initramfs')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--avbtool', type=Path, required=True)
    ap.add_argument('--test-key', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists() or args.output.resolve() == args.baseline.resolve():
        ap.error('Output must be a new file, distinct from baseline')
    src = args.baseline.read_bytes()
    if hashlib.sha256(src).hexdigest() != BASELINE:
        ap.error('Baseline hash does not match verified original Ubuntu image')
    import zopfli.gzip
    original = gzip.decompress(src[START:START+SIZE])
    patched = patch_init(original)
    compressed = zopfli.gzip.compress(patched, numiterations=30)
    if len(compressed) > SIZE or gzip.decompress(compressed) != patched:
        raise ValueError('Compressed initramfs does not fit or failed round-trip')
    info = subprocess.check_output([sys.executable, str(args.avbtool), 'info_image', '--image', str(args.baseline)], text=True)
    def field(pattern):
        m = re.search(pattern, info)
        if not m:
            raise ValueError('Missing AVB metadata')
        return m.group(1)
    orig_size = int(field(r'Original image size:\s+(\d+)'))
    salt = field(r'Salt:\s+([0-9a-f]+)')
    rollback = field(r'Rollback Index:\s+(\d+)')
    props = re.findall(r"Prop: (\S+) -> '([^']*)'", info)
    if not START + SIZE <= orig_size < len(src):
        raise ValueError('Unexpected AVB image layout')
    body = bytearray(src[:orig_size])
    body[START:START+SIZE] = compressed + bytes(SIZE-len(compressed))
    args.output.write_bytes(body)
    try:
        cmd = [sys.executable, str(args.avbtool), 'add_hash_footer', '--image', str(args.output), '--partition_name', 'boot', '--partition_size', str(len(src)), '--key', str(args.test_key), '--algorithm', 'SHA256_RSA4096', '--rollback_index', rollback, '--salt', salt]
        for k, v in dict(props).items():
            cmd.extend(['--prop', f'{k}:{v}'])
        subprocess.run(cmd, check=True)
        with tempfile.TemporaryDirectory(prefix='tb710fu-avb-') as td:
            alias = Path(td) / 'boot.img'
            alias.symlink_to(args.output.resolve())
            subprocess.run([sys.executable, str(args.avbtool), 'verify_image', '--image', str(alias), '--key', str(args.test_key)], check=True)
    except BaseException:
        args.output.unlink(missing_ok=True)
        raise
    print('Private untested candidate created; no device was modified.')

if __name__ == '__main__':
    main()
