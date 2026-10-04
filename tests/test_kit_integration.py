# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise Kit's shell repair path with real BSPATCH/xpwntool and no USB access."""
import argparse
import hashlib
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kit', type=Path, required=True)
parser.add_argument('--kernelcache', type=Path, required=True, help='Decrypted original 11D257 N92 Img3')
args, unittest_args = parser.parse_known_args()
KIT = args.kit.resolve()
CACHE = args.kernelcache.resolve()
PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = (KIT/'restore.sh').read_text()
HELPER = KIT/'resources/patch/touch4-ios7/repairs.sh'
SHA_KERNEL = 'c082f2b423e04aa60a71840c573557d9564d70542f45468de6c60fc2159ff0a8'


def function(name):
    return re.search(r'^'+name+r'\(\) \{\n.*?^\}', SCRIPT, re.M|re.S).group()


def run(script, cwd):
    return subprocess.run(['bash', '-c', script], cwd=cwd, capture_output=True, text=True)


class Integration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='touch4 shell test ')
        self.root = Path(self.temp.name)
        self.work = self.root/'work'
        self.work.mkdir()
        self.save = self.root/'saved/touch4-ios7/11D257'
        self.save.mkdir(parents=True)
        shutil.copy2(PROJECT/'artifacts/touch4-ios7-11D257-v1.tar.gz', self.save/'repairs-v1.tar.gz')
        self.common = ('source '+shlex.quote(str(HELPER))+'\n'+
            'error() { echo "$*" >&2; exit 97; }; log() { :; };\n'+
            'file_download() { echo "Unexpected network request" >&2; exit 98; };\n'+
            'device_type=iPod4,1; device_target_build=11D257; device_base_build=10B500;\n'+
            'device_ecid=test-device; sha1sum="shasum -a 1"; bspatch=/usr/bin/bspatch;\n'+
            'dir='+shlex.quote(str(KIT/'bin/macos'))+';\n')

    def tearDown(self):
        self.temp.cleanup()

    def fixed_cache(self):
        source=self.work/'input kernelcache'
        shutil.copy2(CACHE,source)
        p=run(self.common+'touch4_ios7_resources; touch4_ios7_kernel "input kernelcache" "../saved/touch4-ios7/11D257/kernelcache"',self.work)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        return self.save/'kernelcache'

    def test_normal_output_name_and_menu(self):
        p=run(function('ipsw_custom_set')+'\ndevice_type=iPod4,1; device_target_vers=7.1.2; device_target_build=11D257; ipsw_custom_set; echo "$ipsw_custom"',self.work)
        self.assertEqual(p.stdout.strip(),'../iPod4,1_7.1.2_11D257_Custom')
        for removed in ['--touch4-hardware-fixes','Toggle Hardware Repairs','HardwareV1','touch4_hardware_profile']:
            self.assertNotIn(removed,SCRIPT)
        self.assertFalse((KIT/'restore-touch4-ios7.command').exists())
        self.assertFalse((KIT/'resources/patch/touch4-ios7/hardware').exists())
        self.assertIn('touch4_ios7_kernel',function('ipsw_prepare_specialios7'))

    def test_non_touch4_does_not_download(self):
        p=run(self.common+'device_type=iPad1,1; touch4_ios7_resources',self.work)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_corrupt_bundle_fails(self):
        (self.save/'repairs-v1.tar.gz').write_bytes(b'bad')
        p=run(self.common+'file_download() { printf bad > "$2"; }; touch4_ios7_resources',self.work)
        self.assertEqual(p.returncode,97)
        self.assertFalse((self.save/'repairs-v1/kernel.patch').exists())

    def test_kernel_roundtrip_and_idempotence(self):
        fixed=self.fixed_cache();before=fixed.read_bytes()
        p=run(self.common+'touch4_ios7_resources; touch4_ios7_kernel "../saved/touch4-ios7/11D257/kernelcache" "../saved/touch4-ios7/11D257/kernelcache"',self.work)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertEqual(fixed.read_bytes(),before)
        self.assertEqual(hashlib.sha256((self.work/'touch4-ios7-kernel/original').read_bytes()).hexdigest(),SHA_KERNEL)

    def test_unversioned_ipsw_is_rebuilt(self):
        image=self.root/'old.ipsw';image.write_bytes(b'old')
        p=run(self.common+'touch4_ios7_resources; touch4_ios7_cached_ipsw "../old.ipsw"',self.work)
        self.assertEqual(p.returncode,1)

    def test_cached_ipsw_checks_contents_and_recovers_kernel(self):
        fixed=self.fixed_cache()
        with zipfile.ZipFile(self.root/'current.ipsw','w') as archive:
            archive.writestr('kernelcache.release.n81',fixed.read_bytes())
        p=run(self.common+'touch4_ios7_resources; touch4_ios7_record_ipsw "../current.ipsw"',self.work)
        self.assertEqual(p.returncode,0,p.stderr)
        original=fixed.read_bytes();fixed.unlink()
        p=run(self.common+'touch4_ios7_resources; touch4_ios7_cached_ipsw "../current.ipsw"',self.work)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(fixed.read_bytes(),original)
        with (self.root/'current.ipsw').open('ab') as f:f.write(b'changed')
        p=run(self.common+'touch4_ios7_resources; touch4_ios7_cached_ipsw "../current.ipsw"',self.work)
        self.assertEqual(p.returncode,1)

    def test_justboot_repairs_original_cache_before_USB(self):
        (self.root/'resources/patch/touch4-ios7').mkdir(parents=True)
        shutil.copy2(HELPER,self.root/'resources/patch/touch4-ios7/repairs.sh')
        shutil.copy2(CACHE,self.save/'kernelcache')
        (self.save.parent/'test-device').write_text('device_target_build=11D257\n')
        body=self.common+function('device_justboot_specialios7')+'''
device_enter_mode() { echo USB; };
device_find_mode() { :; }; patch_ibss() { :; }; sleep() { :; };
record() { printf '%s\n' "$*"; }; irecovery=record;
device_justboot_specialios7
'''
        p=run(body,self.work)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('-f ../saved/touch4-ios7/11D257/kernelcache\n',p.stdout)
        self.assertIn('-f ../resources/patch/touch4-ios7/DeviceTree.n81ap.img3\n',p.stdout)
        self.assertEqual(hashlib.sha256((self.work/'touch4-ios7-kernel/check').read_bytes()).hexdigest(),SHA_KERNEL)
        (self.save/'kernelcache').write_bytes(b'invalid')
        p=run(body,self.work)
        self.assertEqual(p.returncode,97)
        self.assertNotIn('USB',p.stdout)

    def test_repair_path_has_no_python_or_local_donor(self):
        self.assertNotIn('python3',HELPER.read_text())
        self.assertNotIn('python3',function('ipsw_prepare_specialios7'))
        self.assertNotIn('python3',function('device_justboot_specialios7'))
        self.assertNotIn('hardware_kext',SCRIPT)


if __name__=='__main__':
    unittest.main(argv=[__file__,*unittest_args])
