#!/usr/bin/env python3
"""Build an AVB-verified microphone boot candidate locally. Never flashes hardware."""
from pathlib import Path
import hashlib
import re
import struct
import subprocess
import sys
import tempfile

root = Path('/project')
source = root / 'artifacts/snap-support-20261116/boot-snap1-VERIFIED.img'
dtb_path = Path('/output/tb710fu-wcd-capture-UNTESTED.dtb')
out = Path('/output/boot-snap1-microphone-UNTESTED.img')
avb = root / 'sources/TB710FU-Archlinux/build/tools/avbtool.py'
key = root / 'sources/TB710FU-Archlinux/build/tools/testkey_rsa4096.pem'
assert hashlib.sha256(source.read_bytes()).hexdigest() == '6a588ec97a053d85afcf2b8dd8a62c479f50c7d6ec45552036c1a25e618fdf0e'
assert hashlib.sha256(dtb_path.read_bytes()).hexdigest() == 'd03d40daa54e0ed6ebbb97cca425712ef16e10e5a7ea6658e26463bb35ea602d'
b = source.read_bytes(); header = bytearray(b[:4096])
assert header[:8] == b'ANDROID!'
kernel_size = struct.unpack_from('<I', header, 8)[0]
kernel = bytearray(b[4096:4096 + kernel_size])
assert kernel[56:60] == b'ARM\x64'
assert struct.unpack_from('<Q', kernel, 0x10)[0] == len(kernel)
moff, msize = struct.unpack_from('<QQ', kernel, 0x20)
assert moff + msize == len(kernel)
manifest = bytearray(kernel[moff:moff+msize])
magic, major, minor, count, default, timeout = struct.unpack_from('<IHHIII', manifest)
assert (magic,major,minor,count,default) == (0x464d504b,0,1,4,1)
pos=60
entries=[]
for _ in range(count):
    fields=struct.unpack_from('<QQIIQIIIQI', manifest, pos)
    name=bytes(manifest[pos+56:pos+56+fields[-1]]).decode('utf-8')
    entries.append((pos,fields,name))
    pos=(pos+56+fields[-1]+3)&~3
assert pos == len(manifest)
dtb_entry=[e for e in entries if e[1][2]==5]
assert len(dtb_entry)==1
entry_pos, fields, name=dtb_entry[0]
dtb_offset, dtb_old_size = fields[0], fields[1]
assert dtb_offset % 8 == 0 and dtb_offset + dtb_old_size <= moff
old_dtb=bytes(kernel[dtb_offset:dtb_offset+dtb_old_size])
assert hashlib.sha256(old_dtb).hexdigest()=='639f1930047b4487396943b420960623487cb1829f343c6e0236d039ab8a560f'
assert all(x == 0 for x in kernel[dtb_offset+dtb_old_size:moff])
new_dtb=dtb_path.read_bytes()
assert new_dtb[:4] == bytes.fromhex('d00dfeed')
assert struct.unpack_from('>I',new_dtb,4)[0] == len(new_dtb)
struct.pack_into('<Q',manifest,entry_pos+8,len(new_dtb))
new_moff=(dtb_offset + len(new_dtb) + 3) & ~3
new_kernel=kernel[:dtb_offset] + new_dtb + bytes(new_moff-dtb_offset-len(new_dtb)) + manifest
struct.pack_into('<Q',new_kernel,0x10,len(new_kernel))
struct.pack_into('<Q',new_kernel,0x20,new_moff)
assert len(new_kernel) < 86*1024*1024
assert bytes(new_kernel[dtb_offset:dtb_offset+len(new_dtb)]) == new_dtb
assert bytes(new_kernel[new_moff:new_moff+4]) == b'KPMF'
assert struct.unpack_from('<Q',new_kernel,new_moff+entry_pos+8)[0] == len(new_dtb)
struct.pack_into('<I',header,8,len(new_kernel))
body=bytes(header)+bytes(new_kernel)+bytes((-len(new_kernel)) % 4096)
info=subprocess.check_output([sys.executable,str(avb),'info_image','--image',str(source)],text=True)
salt=re.search(r'Salt:\s+([0-9a-f]+)',info).group(1)
rollback=re.search(r'Rollback Index:\s+(\d+)',info).group(1)
props=re.findall(r"Prop: (\S+) -> '([^']*)'",info)
out.write_bytes(body)
args=[sys.executable,str(avb),'add_hash_footer','--image',str(out),'--partition_name','boot','--partition_size','100663296','--key',str(key),'--algorithm','SHA256_RSA4096','--rollback_index',rollback,'--salt',salt]
for prop,value in dict(props).items(): args += ['--prop', f'{prop}:{value}']
subprocess.run(args,check=True)
with tempfile.TemporaryDirectory(prefix='tb-microphone-verify-') as td:
    symlink=Path(td)/'boot.img'; symlink.symlink_to(out)
    subprocess.run([sys.executable,str(avb),'verify_image','--image',str(symlink),'--key',str(key)],check=True)
print('OFFLINE ONLY:',out)
print('SHA256:',hashlib.sha256(out.read_bytes()).hexdigest())
print('kernel bytes',len(new_kernel),'manifest offset',new_moff,'DTB bytes',len(new_dtb))
print('UNTESTED: microphone routing and startup have not been tested; do not flash automatically.')
