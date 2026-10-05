# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify the v4 overlay delta and reproducibility using public inputs only."""
import argparse
import io
from pathlib import Path
import plistlib
import sys
import tarfile
import unittest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--default-sound-policy', type=Path, required=True)
args, unittest_args = parser.parse_known_args()
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'tools'))
from package_ui import build, static_wallpaper, GESTALT, SOUND, EVENTS


def unpack(data):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        return {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}


class UIResources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.default = args.default_sound_policy.read_bytes()
        cls.old = unpack((PROJECT / 'artifacts/touch4-ios7-11D257-v3.tar.gz').read_bytes())
        cls.new = unpack((PROJECT / 'artifacts/touch4-ios7-11D257-v4.tar.gz').read_bytes())
        cls.before = unpack(cls.old['rootfs.tar'])
        cls.after = unpack(cls.new['rootfs.tar'])

    def test_exact_overlay_delta_preserves_existing_repairs(self):
        self.assertEqual(set(self.after) - set(self.before), {SOUND})
        self.assertEqual(set(self.before) - set(self.after), set())
        self.assertEqual([p for p in self.before if self.before[p] != self.after[p]], [GESTALT])
        for name in ('kernel.patch', 'BTServer.patch', 'backboardd.patch', 'VirtualAudio.patch'):
            self.assertEqual(self.old[name], self.new[name])
        before, after = [plistlib.loads(b[GESTALT]) for b in (self.before, self.after)]
        self.assertEqual([i for i, (a, b) in enumerate(zip(before['CacheData'], after['CacheData'])) if a != b], [1856])
        self.assertEqual(after['CacheData'][1856], 0)
        self.assertEqual(after['CacheData'][2216], 1)
        self.assertTrue(after['CacheExtra']['bluetooth'])
        before.pop('CacheData'); after.pop('CacheData')
        self.assertEqual(before, after)

    def test_policy_changes_only_six_device_events(self):
        before, after = plistlib.loads(self.default), plistlib.loads(self.after[SOUND])
        self.assertEqual(set(before), set(after))
        self.assertEqual({k for k in before if before[k] != after[k]}, set(EVENTS))
        for key in EVENTS:
            self.assertEqual(after[key], {'RingVibrateIgnore,SilentVibrateIgnore,RingerSwitchIgnore': ['Beep']})

    def test_archive_reproduces_byte_for_byte(self):
        result = build(self.default)
        for name, data in result.items():
            self.assertEqual(data, (PROJECT / 'artifacts' / name).read_bytes(), name)

    def test_rejects_unknown_template_before_build(self):
        original = plistlib.loads(self.before[GESTALT])
        for field, value in [('CacheVersion', 'unknown'), ('CacheData', b'\0' * 2232),
                             ('CacheData', original['CacheData'][:-1])]:
            candidate = dict(original); candidate[field] = value
            with self.assertRaises(ValueError):
                static_wallpaper(plistlib.dumps(candidate))
        with self.assertRaises(ValueError):
            build(self.default + b'bad')


if __name__ == '__main__':
    unittest.main(argv=[__file__, *unittest_args])
