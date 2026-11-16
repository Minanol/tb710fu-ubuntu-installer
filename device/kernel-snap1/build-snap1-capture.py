#!/usr/bin/env python3
"""Build only: correct snap1 capture SoundWire DAI and verify AVB; never flash."""
from pathlib import Path
import hashlib,subprocess
out=Path('/output');src=out/'tb710fu-wcd-capture-UNTESTED.dtb';dst=out/'tb710fu-wcd-sdw-pin1-UNTESTED.dtb'
assert hashlib.sha256(src.read_bytes()).hexdigest()=='d03d40daa54e0ed6ebbb97cca425712ef16e10e5a7ea6658e26463bb35ea602d'
b=subprocess.check_output(['fdtget','-tx',str(src),'/sound/wcd-capture-dai-link/codec','sound-dai'],text=True).split();assert len(b)==6 and b[3]=='0'
b[3]='1';dst.write_bytes(src.read_bytes());subprocess.run(['fdtput','-tx',str(dst),'/sound/wcd-capture-dai-link/codec','sound-dai']+b,check=True)
h=hashlib.sha256(dst.read_bytes()).hexdigest();print('DTB',h)
s=(out/'build-boot.py').read_text().replace('tb710fu-wcd-capture-UNTESTED.dtb','tb710fu-wcd-sdw-pin1-UNTESTED.dtb').replace('boot-snap1-microphone-UNTESTED.img','boot-snap1-mic-sdw-pin1-UNTESTED.img').replace('d03d40daa54e0ed6ebbb97cca425712ef16e10e5a7ea6658e26463bb35ea602d',h)
p=out/'build-sdw-pin1-boot.py';p.write_text(s);subprocess.run(['python3',str(p)],check=True)
