#!/usr/bin/env python3
"""Generate an offline WCD939x capture-link DTB; never flash it automatically."""
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

base = Path('/output')
src = Path('/project/artifacts/snap-support-20261116/original.dtb')
dts = base / 'original.dts'
out = base / 'tb710fu-wcd-capture-UNTESTED.dtb'
assert hashlib.sha256(src.read_bytes()).hexdigest() == '639f1930047b4487396943b420960623487cb1829f343c6e0236d039ab8a560f'
shutil.copyfile(src, out)
used = {int(x,16) for x in re.findall(r'\bphandle = <0x([0-9a-f]+)>;', dts.read_text())}
next_phandle = max(used) + 1

def run(*args, check=True):
    return subprocess.run(args, capture_output=True, text=True, check=check)

def put(node, prop, vals=(), kind='x'):
    run('fdtput', '-t', kind, str(out), node, prop, *map(str, vals))

def mkdir(node):
    if run('fdtget', '-l', str(out), node, check=False).returncode:
        run('fdtput', '-c', str(out), node)

def phandle(node):
    global next_phandle
    result = run('fdtget', '-t', 'x', str(out), node, 'phandle', check=False)
    if not result.returncode:
        return int(result.stdout.strip(), 16)
    n = next_phandle
    next_phandle += 1
    put(node, 'phandle', [f'{n:x}'])
    return n

codec = phandle('/audio-codec')
swr = phandle('/soc@0/soundwire@6d30000')
txmacro = phandle('/soc@0/codec@6ae0000')
# These are copied from the current AW playback link, whose CPU and platform
# point at q6apmbedai and q6apm respectively.
link = '/sound/wcd-capture-dai-link'
mkdir(link)
put(link, 'link-name', ['WCD Capture'], 's')
for child in ('cpu','codec','platform'):
    mkdir(link + '/' + child)
put(link + '/cpu', 'sound-dai', ['156', '78']) # TX_CODEC_DMA_TX_3 = 120
put(link + '/codec', 'sound-dai', [f'{codec:x}', '1', f'{swr:x}', '0', f'{txmacro:x}', '0'])
put(link + '/platform', 'sound-dai', ['15b'])
put('/sound', 'audio-routing', ['AMIC1','MIC BIAS1','AMIC2','MIC BIAS2','AMIC3','MIC BIAS3','AMIC4','MIC BIAS3','AMIC5','MIC BIAS4','TX SWR_INPUT0','ADC1_OUTPUT','TX SWR_INPUT1','ADC2_OUTPUT','TX SWR_INPUT2','ADC3_OUTPUT','TX SWR_INPUT3','ADC4_OUTPUT'], 's')
run('dtc','-I','dtb','-O','dts','-o',str(out.with_suffix('.dts')),str(out))
print('OFFLINE ONLY:', out)
print('SHA256:', hashlib.sha256(out.read_bytes()).hexdigest())
print('UNVERIFIED: topology graph, mic routing and runtime compatibility; do not flash')
