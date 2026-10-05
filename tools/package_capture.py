# SPDX-License-Identifier: GPL-3.0-or-later
"""Extend immutable v2 resources with the tested userspace capture repair."""
import argparse
import gzip
import io
import json
from pathlib import Path
import tarfile
from build_capture import ORIGINAL, PATCHED, MODULE, INSTALL_NAME
from package import binary_patch, digest, require, tar_bytes

HERE = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base-virtualaudio', 'patched-virtualaudio', 'module', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    before, after, module = (p.read_bytes() for p in
                            [args.base_virtualaudio, args.patched_virtualaudio, args.module])
    for blob, sha in [(before, ORIGINAL), (after, PATCHED), (module, MODULE)]:
        require(blob, sha)
    with tarfile.open(HERE / 'artifacts/touch4-ios7-11D257-v2.tar.gz') as archive:
        old = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
    manifest = json.loads(old['manifest.json'])
    for name, record in manifest['files'].items():
        require(old[name], record['sha256'])
    overlay = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(old['rootfs.tar'])) as source, \
            tarfile.open(fileobj=overlay, mode='w', format=tarfile.USTAR_FORMAT) as target:
        for member in source:
            target.addfile(member, source.extractfile(member) if member.isfile() else None)
        info = tarfile.TarInfo(INSTALL_NAME.lstrip('/'))
        info.size, info.mode = len(module), 0o755
        target.addfile(info, io.BytesIO(module))
    files = {name: old[name] for name in ['kernel.patch', 'BTServer.patch', 'backboardd.patch']}
    files.update({'VirtualAudio.patch': binary_patch(before, after), 'rootfs.tar': overlay.getvalue()})
    manifest['version'] = 'cs59-motion-capture-v3'
    manifest['inputs']['VirtualAudio'] = digest(before)
    manifest['outputs']['VirtualAudio'] = digest(after)
    manifest['outputs']['libtouch4audioroute.dylib'] = digest(module)
    manifest['files'] = {name: digest(data) for name, data in files.items()}
    manifest['limitations'] = ['System sound effects unresolved', 'Settings wallpaper gallery unresolved',
        'App-specific CoreMotion is not repaired by the backboardd-only module',
        'Capture repair full device reboot and fresh v3 full restore not yet tested',
        'Broader microphone routes, DSP modes and gain behavior not tested']
    manifest['motion']['hardware_validation']['fresh_v2_full_restore'] = 'passed'
    manifest['capture'] = {'install_name': INSTALL_NAME, 'scope': 'VirtualAudio plugin process',
        'virtualaudio_uuid': 'd67d8d297bb836faae231b0b458cbe98',
        'guard': 'iPod4,1/N81AP, UUID, getter bytes, writable cache, previous model 0',
        'model': 16, 'profile': 'existing K93 single-microphone routing database and handlers',
        'shared_cache_modified': False, 'additional_kernel_changes': False,
        'launch_configuration_modified': False,
        'hardware_validation': {'device': '8 GB iPod4,1 / N81AP',
            'voice_memos_record_and_playback': 'passed; user confirmed',
            'video_record_and_playback': 'passed; user confirmed',
            'music_after_guarded_patch': 'passed; user confirmed',
            'full_device_reboot': 'not tested', 'fresh_v3_full_restore': 'not tested'}}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (args.output / name).write_bytes(data)
    (args.output / 'libtouch4audioroute.dylib').write_bytes(module)
    bundle = gzip.compress(tar_bytes(files), compresslevel=9, mtime=0)
    bundle = bundle[:9] + b'\xff' + bundle[10:]
    (args.output / 'touch4-ios7-11D257-v3.tar.gz').write_bytes(bundle)
    print(json.dumps({'bundle': digest(bundle), 'files': manifest['files'],
                      'outputs': manifest['outputs']}, indent=2))


if __name__ == '__main__':
    main()
