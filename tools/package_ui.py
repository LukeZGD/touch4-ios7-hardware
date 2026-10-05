# SPDX-License-Identifier: GPL-3.0-or-later
"""Extend immutable v3 resources with public-template system sound/gallery repairs."""
import argparse
import gzip
import io
import json
from pathlib import Path
import plistlib
import tarfile
from package import digest, require, tar_bytes

HERE = Path(__file__).resolve().parents[1]
BASE_SHA = '17675510a16c33de668856d95debecaa3806f54301d2b3b3562544c7cbfe139b'
DEFAULT_SHA = '7d5ceb7e563514ec8c451bedf5a48961f7d3600e67207181d77917d614c78930'
GESTALT = 'private/var/mobile/Library/Caches/com.apple.MobileGestalt.plist'
SOUND = 'System/Library/Frameworks/MediaToolbox.framework/N81/SystemSoundRingerSettings.plist'
EVENTS = ('KeyPressed', 'PINKeyPressed', 'ScreenLocked', 'ScreenUnlocked',
          'ConnectedToPower', 'KeyPressClickPreview')


def static_wallpaper(data):
    cache = plistlib.loads(data)
    extra = cache['CacheExtra']
    if (cache['CacheVersion'] != '11D257' or
            extra['h9jDsbgj7xIVeIQ8S3/X3Q'] != 'iPod4,1' or
            extra['/YYygAofPDbhrwToVsXdeA'] != 'N81AP'):
        raise ValueError('Unsupported MobileGestalt template identity/build')
    blob = bytearray(cache['CacheData'])
    # 248 eight-byte answer slots, followed by 248 validity bytes.
    # UIProceduralWallpaperCapability is answer 232, not property index 117.
    if len(blob) != 2232 or blob[1984 + 232] != 1 or blob[1856:1864] != b'\x01' + b'\0' * 7:
        raise ValueError('Unsupported MobileGestalt answer layout/value')
    blob[1856] = 0
    cache['CacheData'] = bytes(blob)
    return plistlib.dumps(cache, fmt=plistlib.FMT_BINARY)


def sound_policy(data):
    require(data, DEFAULT_SHA)
    policy = plistlib.loads(data)
    for event in EVENTS:
        if event not in policy:
            raise ValueError('Missing stock sound event: ' + event)
        policy[event] = {'RingVibrateIgnore,SilentVibrateIgnore,RingerSwitchIgnore': ['Beep']}
    return plistlib.dumps(policy, fmt=plistlib.FMT_BINARY)


def build(default):
    base = (HERE / 'artifacts/touch4-ios7-11D257-v3.tar.gz').read_bytes()
    require(base, BASE_SHA)
    with tarfile.open(fileobj=io.BytesIO(base)) as archive:
        old = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
    manifest = json.loads(old['manifest.json'])
    for name, record in manifest['files'].items():
        require(old[name], record['sha256'])
    policy = sound_policy(default)
    overlay = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(old['rootfs.tar'])) as source, \
            tarfile.open(fileobj=overlay, mode='w', format=tarfile.USTAR_FORMAT) as target:
        for member in source:
            data = source.extractfile(member).read() if member.isfile() else None
            if member.name == GESTALT:
                data = static_wallpaper(data)
                member.size = len(data)
                gestalt = data
            target.addfile(member, io.BytesIO(data) if data is not None else None)
        # hfsplus untar needs these parents even on an unmodified N92 rootfs.
        parents = ('System', 'System/Library', 'System/Library/Frameworks',
                   'System/Library/Frameworks/MediaToolbox.framework',
                   'System/Library/Frameworks/MediaToolbox.framework/N81')
        existing = {m.name.rstrip('/') for m in source.getmembers()}
        for path in parents:
            if path not in existing:
                info = tarfile.TarInfo(path)
                info.type, info.mode = tarfile.DIRTYPE, 0o755
                info.uid, info.gid = 0, 0
                target.addfile(info)
        info = tarfile.TarInfo(SOUND)
        info.size, info.mode = len(policy), 0o644
        info.uid, info.gid = 0, 0
        target.addfile(info, io.BytesIO(policy))
    files = {name: old[name] for name in
             ('kernel.patch', 'BTServer.patch', 'backboardd.patch', 'VirtualAudio.patch')}
    files['rootfs.tar'] = overlay.getvalue()
    manifest['version'] = 'cs59-motion-capture-ui-v4'
    manifest['inputs']['Default-SystemSoundRingerSettings.plist'] = digest(default)
    manifest['outputs']['N81-SystemSoundRingerSettings.plist'] = digest(policy)
    manifest['outputs']['MobileGestalt.plist'] = digest(gestalt)
    manifest['files'] = {name: digest(data) for name, data in files.items()}
    manifest['limitations'] = [
        'Dynamic wallpaper assets are not supplied; N81 uses the static gallery layout',
        'App-specific CoreMotion is not repaired by the backboardd-only module',
        'Capture/UI repairs full device reboot and fresh v4 full restore not yet tested',
        'Broader microphone routes, DSP modes, gains and notification/mute behavior not tested']
    manifest['ui'] = {
        'sound_policy': {'path': '/' + SOUND, 'source': 'Public iPhone3,3 11D257 Default policy',
                         'events': list(EVENTS), 'other_default_policies_preserved': True},
        'wallpaper': {'path': '/' + GESTALT, 'source': 'Existing Kit N81 template with Bluetooth fix',
                      'answer': 'UIProceduralWallpaperCapability', 'slot': 232,
                      'byte_offset': 1856, 'before': 1, 'after': 0,
                      'validity_and_other_cached_answers_preserved': True},
        'additional_binary_or_boot_chain_changes': False,
        'hardware_validation': {'device': '8 GB iPod4,1 / N81AP',
            'system_sound_effects': 'passed; user confirmed after live config installation',
            'wallpaper_categories_and_static_gallery': 'accepted by user after live cache installation',
            'category_thumbnail_before': '0x0', 'category_thumbnail_after': '90x135',
            'native_static_gallery_items': 66,
            'full_device_reboot': 'not tested', 'fresh_v4_full_restore': 'not tested'}}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    bundle = gzip.compress(tar_bytes(files), compresslevel=9, mtime=0)
    files['touch4-ios7-11D257-v4.tar.gz'] = bundle[:9] + b'\xff' + bundle[10:]
    files['N81-SystemSoundRingerSettings.plist'] = policy
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--default-sound-policy', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = build(args.default_sound_policy.read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (args.output / name).write_bytes(data)
    print(json.dumps({name: digest(data) for name, data in files.items()}, indent=2))


if __name__ == '__main__':
    main()
