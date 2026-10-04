# SPDX-License-Identifier: GPL-3.0-or-later
"""Maintainer-only ARMv7 module/backboardd build; no device or shared-cache access."""
import argparse
import hashlib
from pathlib import Path
import plistlib
import subprocess
from macho import sections
from motion_dependency import add_dependency

HERE = Path(__file__).resolve().parent
INSTALL_NAME = '/usr/lib/libtouch4motion.dylib'
ORIGINAL = 'dbbdeb114ef589bab6a28c553245726a3c5d694c16091012f3a92c4b769dddee'
MODULE = '37672509e886f3ab4523939d79a63d3f16f3550bf6655b97858c4e53406bea3c'
PATCHED = '9b0e0e717cc810a5e79ee61810253ff07fb919db44c1423182d8a4f710771568'


def require(blob, expected):
    actual = hashlib.sha256(blob).hexdigest()
    if actual != expected:
        raise ValueError('Unexpected binary SHA256: ' + actual + '; expected ' + expected)


def text(blob):
    section = next(s for s in sections(blob) if s['name'] == '__text')
    return blob[section['offset']:section['offset'] + section['size']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backboardd', type=Path, required=True, help='Unmodified public iPhone3,3 11D257 daemon')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ldid', default='ldid')
    args = parser.parse_args()
    original = args.backboardd.read_bytes()
    require(original, ORIGINAL)
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    stub = out / 'libSystem.tbd'
    stub.write_text('''--- !tapi-tbd-v3
archs: [ armv7 ]
platform: ios
install-name: /usr/lib/libSystem.B.dylib
exports:
  - archs: [ armv7 ]
    symbols: [ _dlopen, _dlsym, _printf, _sleep, _strcmp, _memset, _memcpy, _memcmp, dyld_stub_binder ]
...
''')
    obj = out / 'n81_motion.o'
    # Keep signing identifiers identical to the real-device tested build.
    module = out / 'n81_motion_persistent'
    subprocess.run(['xcrun', 'clang', '-target', 'armv7-apple-ios7.0', '-O2', '-fno-stack-protector',
                    '-c', str(HERE / 'n81_motion.c'), '-o', str(obj)], check=True)
    subprocess.run(['xcrun', 'ld', '-arch', 'armv7', '-ios_version_min', '7.0', '-dylib',
                    '-install_name', INSTALL_NAME, '-compatibility_version', '1.0.0',
                    '-current_version', '1.0.0', '-o', str(module), str(obj), str(stub)], check=True)
    subprocess.run([args.ldid, '-S', str(module)], check=True)
    require(module.read_bytes(), MODULE)
    entitlements = subprocess.check_output([args.ldid, '-e', str(args.backboardd)])
    ent_file = out / 'backboardd-entitlements.plist'
    ent_file.write_bytes(entitlements)
    candidate = out / 'backboardd-persistent'
    candidate.write_bytes(add_dependency(original, INSTALL_NAME))
    subprocess.run([args.ldid, '-S' + str(ent_file), str(candidate)], check=True)
    assert text(candidate.read_bytes()) == text(original), 'Executable __text changed'
    assert plistlib.loads(subprocess.check_output([args.ldid, '-e', str(candidate)])) == plistlib.loads(entitlements)
    require(candidate.read_bytes(), PATCHED)
    module.rename(out / 'libtouch4motion.dylib')
    candidate.rename(out / 'backboardd')
    print('Built module and signed daemon exactly match the full-reboot-tested outputs.')


if __name__ == '__main__':
    main()
