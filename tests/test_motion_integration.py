# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify binary patch and real HFS rootfs integration, without USB access."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kit', type=Path, required=True)
parser.add_argument('--rootfs', type=Path, required=True, help='Decrypted, unmodified public iPhone3,3 11D257 HFS image')
args, unittest_args = parser.parse_known_args()
KIT, ROOTFS = args.kit.resolve(), args.rootfs.resolve()
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'tools'))
from build_motion import text


def sha(data):
    return hashlib.sha256(data).hexdigest()


class MotionIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='touch4 motion hfs ')
        self.root = Path(self.temp.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.save = self.root / 'saved/touch4-ios7/11D257'
        self.save.mkdir(parents=True)
        shutil.copyfile(PROJECT / 'artifacts/touch4-ios7-11D257-v4.tar.gz', self.save / 'repairs-v4.tar.gz')
        self.manifest = json.loads((PROJECT / 'artifacts/manifest.json').read_text())
        self.helper = KIT / 'resources/patch/touch4-ios7/repairs.sh'
        self.hfs = KIT / 'bin/macos/hfsplus'
        self.common = ('source ' + shlex.quote(str(self.helper)) + '\n' +
            'error() { echo "$*" >&2; exit 97; }; log() { :; };\n' +
            'file_download() { echo "Unexpected network request" >&2; exit 98; };\n' +
            'device_type=iPod4,1; device_target_build=11D257; sha1sum="shasum -a 1"; bspatch=/usr/bin/bspatch;\n' +
            'dir=' + shlex.quote(str(KIT / 'bin/macos')) + ';\n')

    def tearDown(self):
        self.temp.cleanup()

    def extract(self, image, path, output):
        p = subprocess.run([str(self.hfs), str(image), 'extract', path, str(output)], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return output.read_bytes()

    def test_binary_roundtrip_preserves_entitlements_and_text(self):
        source = self.root / 'backboardd-original'
        before = self.extract(ROOTFS, 'usr/libexec/backboardd', source)
        target = self.root / 'backboardd'
        p = subprocess.run(['/usr/bin/bspatch', str(source), str(target), str(PROJECT / 'artifacts/backboardd.patch')], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        after = target.read_bytes()
        self.assertEqual(sha(before), self.manifest['inputs']['backboardd']['sha256'])
        self.assertEqual(sha(after), self.manifest['outputs']['backboardd']['sha256'])
        self.assertEqual(text(before), text(after))
        ent = lambda f: plistlib.loads(subprocess.check_output(['ldid', '-e', str(f)]))
        self.assertEqual(ent(source), ent(target))

    def test_real_hfs_shell_path_and_permissions(self):
        image = self.work / 'rootfs.dec'
        # APFS clone keeps this test cheap and leaves the original image intact.
        p = subprocess.run(['cp', '-c', str(ROOTFS), str(image)], capture_output=True)
        if p.returncode:
            shutil.copyfile(ROOTFS, image)
        # Match ipsw_prepare_specialios7's existing 1589 MiB growth step.
        p = subprocess.run([str(self.hfs), str(image), 'grow', str(1589 * 1024 * 1024)], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        launch_path = 'System/Library/LaunchDaemons/com.apple.backboardd.plist'
        original_launch = self.extract(ROOTFS, launch_path, self.root / 'launch-original')
        p = subprocess.run(['bash', '-c', self.common + 'touch4_ios7_resources; touch4_ios7_rootfs'], cwd=self.work, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for path, key in [('usr/sbin/BTServer', 'BTServer'), ('usr/libexec/backboardd', 'backboardd'),
                          ('usr/lib/libtouch4motion.dylib', 'libtouch4motion.dylib'),
                          ('Library/Audio/Plug-Ins/HAL/VirtualAudio.plugin/VirtualAudio', 'VirtualAudio'),
                          ('usr/lib/libtouch4audioroute.dylib', 'libtouch4audioroute.dylib')]:
            result = self.extract(image, path, self.root / key)
            self.assertEqual(sha(result), self.manifest['outputs'][key]['sha256'])
        self.assertEqual(self.extract(image, launch_path, self.root / 'launch-after'), original_launch)
        # Read the UI repairs from the actual HFS output, including tar ownership.
        import io
        import tarfile
        with tarfile.open(fileobj=io.BytesIO((PROJECT / 'artifacts/rootfs.tar').read_bytes())) as overlay:
            for path in ['private/var/mobile/Library/Caches/com.apple.MobileGestalt.plist',
                         'System/Library/Frameworks/MediaToolbox.framework/N81/SystemSoundRingerSettings.plist']:
                expected = overlay.extractfile(path).read()
                self.assertEqual(self.extract(image, path, self.root / Path(path).name), expected)
                listing = subprocess.check_output([str(self.hfs), str(image), 'ls', str(Path(path).parent)], text=True)
                line = next(line for line in listing.splitlines() if line.rstrip().endswith(' ' + Path(path).name))
                owner = '501\\s+501' if 'MobileGestalt' in path else '0\\s+0'
                self.assertRegex(line, r'^100644\s+' + owner + r'\s+')
        # The helper's actual chmod/chown operations and tar modes are checked
        # by the HFS listing, not merely by searching shell source text.
        for path, basename in [('usr/libexec', 'backboardd'), ('usr/lib', 'libtouch4motion.dylib'),
                               ('usr/lib', 'libtouch4audioroute.dylib')]:
            listing = subprocess.check_output([str(self.hfs), str(image), 'ls', path], text=True)
            line = next(line for line in listing.splitlines() if line.rstrip().endswith(' ' + basename))
            self.assertRegex(line, r'^100755\s+0\s+0\s+')
        listing = subprocess.check_output([str(self.hfs), str(image), 'ls',
            'Library/Audio/Plug-Ins/HAL/VirtualAudio.plugin'], text=True)
        line = next(line for line in listing.splitlines() if line.rstrip().endswith(' VirtualAudio'))
        self.assertRegex(line, r'^100775\s+0\s+80\s+')
        (PROJECT / 'build/motion').mkdir(parents=True, exist_ok=True)
        (PROJECT / 'build/motion/hfs-shell-validation.txt').write_text(p.stdout + p.stderr)

    def test_unknown_backboardd_rejected_before_rootfs_writes(self):
        # Feed a real valid BTServer and an unsupported daemon to the native
        # shell guards. Record any rootfs mutation requested by the helper.
        bt = self.root / 'BTServer'
        self.extract(ROOTFS, 'usr/sbin/BTServer', bt)
        fake = self.root / 'fake-bin'
        fake.mkdir()
        hfs = fake / 'hfsplus'
        hfs.write_text('#!/bin/bash\nif [[ $2 == extract ]]; then\n'
                       ' if [[ $3 == usr/sbin/BTServer ]]; then cp ' + shlex.quote(str(bt)) + ' "$4"; else printf unsupported > "$4"; fi\n'
                       'else touch ' + shlex.quote(str(self.root / 'MUTATION')) + '; fi\n')
        hfs.chmod(0o755)
        p = subprocess.run(['bash', '-c', self.common + 'touch4_ios7_resources; dir=' + shlex.quote(str(fake)) + '; touch4_ios7_rootfs'], cwd=self.work, capture_output=True, text=True)
        self.assertEqual(p.returncode, 97, p.stdout + p.stderr)
        self.assertIn('Unsupported 11D257 backboardd', p.stderr)
        self.assertFalse((self.root / 'MUTATION').exists())

    def test_capture_binary_roundtrip_preserves_executable_and_entitlements(self):
        original = self.root / 'VirtualAudio-original'
        before = self.extract(ROOTFS, 'Library/Audio/Plug-Ins/HAL/VirtualAudio.plugin/VirtualAudio', original)
        patched = self.root / 'VirtualAudio-patched'
        p = subprocess.run(['/usr/bin/bspatch', str(original), str(patched),
                            str(PROJECT / 'artifacts/VirtualAudio.patch')], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        after = patched.read_bytes()
        self.assertEqual(sha(before), self.manifest['inputs']['VirtualAudio']['sha256'])
        self.assertEqual(sha(after), self.manifest['outputs']['VirtualAudio']['sha256'])
        self.assertEqual(text(before), text(after))
        self.assertEqual(subprocess.check_output(['ldid', '-e', str(original)]), b'')
        self.assertEqual(subprocess.check_output(['ldid', '-e', str(patched)]), b'')

    def test_unknown_virtualaudio_rejected_before_rootfs_writes(self):
        bt, bb = self.root / 'BTServer', self.root / 'backboardd'
        self.extract(ROOTFS, 'usr/sbin/BTServer', bt)
        self.extract(ROOTFS, 'usr/libexec/backboardd', bb)
        fake = self.root / 'fake-bin'
        fake.mkdir()
        hfs = fake / 'hfsplus'
        hfs.write_text('#!/bin/bash\nif [[ $2 == extract ]]; then\n'
            ' case "$3" in\n'
            ' usr/sbin/BTServer) cp ' + shlex.quote(str(bt)) + ' "$4";;\n'
            ' usr/libexec/backboardd) cp ' + shlex.quote(str(bb)) + ' "$4";;\n'
            ' *) printf unsupported > "$4";;\n'
            ' esac\nelse touch ' + shlex.quote(str(self.root / 'MUTATION')) + '; fi\n')
        hfs.chmod(0o755)
        p = subprocess.run(['bash', '-c', self.common + 'touch4_ios7_resources; dir=' +
            shlex.quote(str(fake)) + '; touch4_ios7_rootfs'], cwd=self.work, capture_output=True, text=True)
        self.assertEqual(p.returncode, 97, p.stdout + p.stderr)
        self.assertIn('Unsupported 11D257 VirtualAudio', p.stderr)
        self.assertFalse((self.root / 'MUTATION').exists())


if __name__ == '__main__':
    unittest.main(argv=[__file__, *unittest_args])
