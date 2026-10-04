# SPDX-License-Identifier: GPL-3.0-or-later
"""Extend the published v1 bundle with the exact reboot-tested motion repair."""
import argparse
import gzip
import io
import json
from pathlib import Path
import tarfile
from build_motion import ORIGINAL, PATCHED, MODULE
from package import binary_patch, digest, require, tar_bytes

HERE = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-backboardd', type=Path, required=True)
    parser.add_argument('--patched-backboardd', type=Path, required=True)
    parser.add_argument('--module', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    before, after, module = (p.read_bytes() for p in [args.base_backboardd, args.patched_backboardd, args.module])
    for blob, sha in [(before, ORIGINAL), (after, PATCHED), (module, MODULE)]:
        require(blob, sha)
    # Always start from the immutable v1 archive, even when v2 artifacts exist.
    with tarfile.open(HERE / 'artifacts/touch4-ios7-11D257-v1.tar.gz') as archive:
        old = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
    manifest = json.loads(old['manifest.json'])
    for name, record in manifest['files'].items():
        require(old[name], record['sha256'])
    overlay = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(old['rootfs.tar'])) as source, tarfile.open(fileobj=overlay, mode='w', format=tarfile.USTAR_FORMAT) as target:
        for member in source:
            target.addfile(member, source.extractfile(member) if member.isfile() else None)
        info = tarfile.TarInfo('usr/lib')
        info.type, info.mode = tarfile.DIRTYPE, 0o755
        target.addfile(info)
        info = tarfile.TarInfo('usr/lib/libtouch4motion.dylib')
        info.size, info.mode = len(module), 0o755
        target.addfile(info, io.BytesIO(module))
    files = {'kernel.patch': old['kernel.patch'], 'BTServer.patch': old['BTServer.patch'],
             'backboardd.patch': binary_patch(before, after), 'rootfs.tar': overlay.getvalue()}
    manifest['version'] = 'cs59-motion-v2'
    manifest['inputs']['backboardd'] = digest(before)
    manifest['outputs']['backboardd'] = digest(after)
    manifest['outputs']['libtouch4motion.dylib'] = digest(module)
    manifest['files'] = {name: digest(data) for name, data in files.items()}
    manifest['limitations'] = ['System sound effects unresolved', 'Settings wallpaper gallery unresolved',
                               'App-specific CoreMotion is not repaired by the backboardd-only module',
                               'Fresh full restore with the v2 bundle pending']
    manifest['motion'] = {'install_name': '/usr/lib/libtouch4motion.dylib', 'scope': 'backboardd process only',
        'coremotion_uuid': 'f541183564873c8489cce9deca3e9bd5', 'model': 11,
        'shared_cache_modified': False, 'additional_kernel_changes': False,
        'launch_configuration_modified': False,
        'hardware_validation': {'device': '8 GB iPod4,1 / N81AP', 'full_reboot': 'passed',
            'safari_both_landscape_and_portrait': 'passed', 'rotation_lock': 'passed',
            'lock_unlock_then_rotation': 'passed', 'fresh_v2_full_restore': 'pending'}}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (args.output / name).write_bytes(data)
    (args.output / 'libtouch4motion.dylib').write_bytes(module)
    bundle = gzip.compress(tar_bytes(files), compresslevel=9, mtime=0)
    bundle = bundle[:9] + b'\xff' + bundle[10:]
    (args.output / 'touch4-ios7-11D257-v2.tar.gz').write_bytes(bundle)
    print(json.dumps({'bundle': digest(bundle), 'files': manifest['files'], 'outputs': manifest['outputs']}, indent=2))


if __name__ == '__main__':
    main()
