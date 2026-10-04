# SPDX-License-Identifier: GPL-3.0-or-later
"""Package tested outputs into deterministic BSDIFF40 patches for Legacy iOS Kit."""
import argparse
import bz2
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile


def digest(data):
    return {'sha1': hashlib.sha1(data).hexdigest(), 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}


def integer(number):
    # BSDIFF40 uses little-endian sign/magnitude, including control triples.
    value = abs(number) | ((1 << 63) if number < 0 else 0)
    return value.to_bytes(8, 'little')


def binary_patch(before, after):
    shared = min(len(before), len(after))
    control = bz2.compress(integer(shared) + integer(len(after) - shared) + integer(0))
    delta = bz2.compress(bytes((after[i] - before[i]) & 255 for i in range(shared)))
    extra = bz2.compress(after[shared:])
    return b'BSDIFF40' + integer(len(control)) + integer(len(delta)) + integer(len(after)) + control + delta + extra


def tar_bytes(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(data), 0o644
            archive.addfile(entry, io.BytesIO(data))
    return stream.getvalue()


def require(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Input/output SHA256 mismatch: ' + hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base-kernel', 'patched-kernel', 'base-btserver', 'overlay', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    old_kernel, kernel = args.base_kernel.read_bytes(), args.patched_kernel.read_bytes()
    bt = args.base_btserver.read_bytes()
    require(old_kernel, '70cead59899008cc7cbd75020760b9a0da39498dc7d694cc61cc9ea4ad831489')
    require(kernel, 'c082f2b423e04aa60a71840c573557d9564d70542f45468de6c60fc2159ff0a8')
    require(bt, '2adcc0b16dc5f976c6ba80907bd6e1dba1ec395fbcc40c905dc4a543e4053c6e')
    rootfs_stream = io.BytesIO()
    with tarfile.open(args.overlay) as source, tarfile.open(fileobj=rootfs_stream, mode='w', format=tarfile.USTAR_FORMAT) as target:
        signed_bt = source.extractfile('usr/sbin/BTServer').read()
        require(signed_bt, 'e19ad8e77ed50d6f1447fd00ac7f1954d2bf75c6045612f73d3a52329709c8c9')
        for member in source.getmembers():
            if member.name == 'usr/sbin/BTServer':
                continue
            member.mtime = 0
            member.uname = member.gname = ''
            target.addfile(member, source.extractfile(member) if member.isfile() else None)
    files = {'kernel.patch': binary_patch(old_kernel, kernel),
             'BTServer.patch': binary_patch(bt, signed_bt), 'rootfs.tar': rootfs_stream.getvalue()}
    manifest = {'format': 1, 'version': 'cs59-v1', 'device': 'iPod4,1', 'target': '11D257', 'base': '10B500',
                'inputs': {'kernel': digest(old_kernel), 'BTServer': digest(bt)},
                'outputs': {'kernel': digest(kernel), 'BTServer': digest(signed_bt)},
                'files': {name: digest(data) for name, data in files.items()},
                'limitations': ['System sound effects unresolved', 'Settings wallpaper gallery unresolved', 'Rotation unresolved'],
                'device_tree': 'Original Legacy iOS Kit N81 tree; bootloaders/DRA unchanged'}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (args.output / name).write_bytes(data)
    bundle = gzip.compress(tar_bytes(files), compresslevel=9, mtime=0)
    # Normalize gzip's OS field across Python/platform versions.
    bundle = bundle[:9] + b'\xff' + bundle[10:]
    (args.output / 'touch4-ios7-11D257-v1.tar.gz').write_bytes(bundle)
    print(json.dumps({'bundle': digest(bundle), 'inputs': manifest['inputs'], 'outputs': manifest['outputs'], 'files': manifest['files']}, indent=2))


if __name__ == '__main__':
    main()
