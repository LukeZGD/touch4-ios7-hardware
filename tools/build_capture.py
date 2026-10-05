# SPDX-License-Identifier: GPL-3.0-or-later
"""Maintainer-only build of the exact device-tested N81 VirtualAudio repair."""
import argparse
from pathlib import Path
import subprocess
from build_motion import require, text
from motion_dependency import add_dependency

HERE = Path(__file__).resolve().parent
INSTALL_NAME = '/usr/lib/libtouch4audioroute.dylib'
ORIGINAL = 'e6e200c1cd0be1241e3e5c055c9bbdf065abf36491895e8c32b029a13d33da84'
PATCHED = 'f2bb6a5fffc870c318701b83c7be3d5939a1bfbe58be8ecde2010d33d9c8393c'
MODULE = '3126434a585635c23c30bc82ca644b3f29d106d022d4e9e00cca88b3b7a8e738'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--virtualaudio', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ldid', default='ldid')
    args = parser.parse_args()
    original = args.virtualaudio.read_bytes()
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
    symbols: [ _dlopen, _dlsym, _printf, _sleep, _write, dyld_stub_binder ]
...
''')
    obj = out / 'n81_audio_route.o'
    module = out / 'libtouch4audioroute.dylib'
    subprocess.run(['xcrun', 'clang', '-target', 'armv7-apple-ios7.0', '-O2',
                    '-fno-stack-protector', '-c', str(HERE / 'n81_audio_route.c'),
                    '-o', str(obj)], check=True)
    subprocess.run(['xcrun', 'ld', '-arch', 'armv7', '-ios_version_min', '7.0', '-dylib',
                    '-install_name', INSTALL_NAME, '-compatibility_version', '1.0.0',
                    '-current_version', '1.0.0', '-o', str(module), str(obj), str(stub)], check=True)
    subprocess.run([args.ldid, '-S', str(module)], check=True)
    require(module.read_bytes(), MODULE)
    candidate = out / 'VirtualAudio.guarded-candidate'
    candidate.write_bytes(add_dependency(original, INSTALL_NAME))
    # Both the original plugin and the tested candidate have no entitlements.
    assert subprocess.check_output([args.ldid, '-e', str(args.virtualaudio)]) == b''
    subprocess.run([args.ldid, '-S', str(candidate)], check=True)
    assert subprocess.check_output([args.ldid, '-e', str(candidate)]) == b''
    assert text(candidate.read_bytes()) == text(original), 'Executable __text changed'
    require(candidate.read_bytes(), PATCHED)
    print('Signed module and VirtualAudio exactly match the device-tested outputs.')


if __name__ == '__main__':
    main()
