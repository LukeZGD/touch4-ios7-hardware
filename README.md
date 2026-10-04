# iPod touch 4 iOS 7 hardware repairs

Build tools and versioned repair artifacts for **iPod4,1 / N81AP**, iOS
**7.1.2 / 11D257**, using Legacy iOS Kit's existing **6.1.6 / 10B500 DRA v6**
boot chain. Legacy iOS Kit downloads a pinned artifact bundle and applies
`bspatch`; its repair path does not run these Python builders or require a
locally supplied audio driver.

## What is included

- N81 Bluetooth product classification, support check, firmware and boot/sleep scripts.
- Native iOS 7 CS42L59 codec transplant and the N81 IIS configuration bridge.
- System rotation: an early backboardd dependency loads a guarded, process-local CoreMotion model correction.
- Partial wallpaper resources: the iOS 7 default wallpaper displays; the Settings gallery remains broken.

Music playback was reported clean on both wired channels and the speaker,
including playback after lock/unlock. Bluetooth was reported working in the
integrated restore test. **Charging, lock and keyboard system sound effects
remain unresolved.** Safari rotation in both directions, return to portrait, rotation lock, and lock/unlock were verified after a full OS reboot on the 8 GB N81 device. This backboardd-only fix does not repair every application's independent CoreMotion use. Repeated cold boots, Bluetooth
sleep/wake, capture paths, additional sample rates and other capacities still
need testing. The default shell/binary-patch integration is a refactor of the
tested outputs; a new full device restore is still required.

## Downloadable inputs and artifacts

- [`donors/AppleCS42L59Audio.kext`](donors/AppleCS42L59Audio.kext): the exact native donor and plist used by the offline linker.
- [`artifacts/touch4-ios7-11D257-v2.tar.gz`](artifacts/touch4-ios7-11D257-v2.tar.gz): ready-to-apply kernel, signed BTServer and signed backboardd binary patches, plus the motion module and Bluetooth/wallpaper resources.
- [`artifacts/manifest.json`](artifacts/manifest.json): input/output SHA-1, SHA-256 and sizes.
- [`artifacts/libtouch4motion.dylib`](artifacts/libtouch4motion.dylib): the exact signed module verified on hardware.
- [`tools`](tools): linker, symbol map, bridge source and artifact packager.

The donor was extracted from the locally available `11A63840h.dmg` image
(DTSDK `11A384`, `iphoneos7.0.internal`). It is not the public iOS 6 driver.
The kext is provided here as a versioned input; users do not need the complete
internal image. The full image is not included.

| Donor file | SHA-256 |
| --- | --- |
| AppleCS42L59Audio | `1970eb6c0754bd313e1b957e60d4149c9f48a60ede7363adc84419bea281cf88` |
| Info.plist | `cd15cf00a8d3face0857dbb2b2ba394f276bf3720e9b29c17afe18eb008cf7c0` |

## Legacy iOS Kit integration

Use its normal iPod touch 4 iOS 7.1.2 restore/create-IPSW flow. The repairs are
always applied for that device/build. There is no hardware toggle, additional
command-line argument, separate launcher or hardware-specific IPSW suffix.
The original NOR DeviceTree and DRA bootloader/exploit resources are retained.
The existing Aquila signature runtime is necessary for the patched Bluetooth and backboardd
services and is installed even when the optional Cydia bootstrap is disabled;
that configuration has not yet been tested on hardware.

The ordinary saved kernelcache is used for both restore and Just Boot. A
sidecar records the resource version and complete IPSW checksum; older IPSWs
without a matching record are rebuilt using their normal names. No developer
Python tools run during this repair path. Other Legacy iOS Kit paths can still
have their own Python requirements.

## Reproducing the artifacts

Maintainer-only requirements: Python 3.8+, Kit `xpwntool`, `hfsplus` and `dmg`,
and `ldid` for signing BTServer and backboardd. Rebuilding the ARMv7 motion
module also requires a macOS Xcode toolchain with ARMv7 support. `bspatch` verifies the generated artifacts.
Unicorn is optional for the Thumb bridge tests.

Extract/decrypt the public iPhone3,3 11D257 kernel and BTServer, and obtain
BlueTool from the public iPod4,1 10B500 root filesystem. Inputs are hash-pinned
in `tools/build.py`, `tools/link_audio.py` and the artifact manifest.

```sh
python3 tools/build.py kernel --input inputs/kernelcache \
  --kext donors/AppleCS42L59Audio.kext --output build/kernel \
  --xpwntool /path/to/xpwntool
python3 tools/build.py overlay --btserver inputs/BTServer \
  --bluetool inputs/BlueTool --gestalt inputs/gestalt.n81.plist \
  --output build/overlay --ldid /path/to/ldid
python3 tools/package.py --base-kernel build/kernel/kernel.original.macho \
  --patched-kernel build/kernel/kernel.n81.macho --base-btserver inputs/BTServer \
  --overlay build/overlay/rootfs.tar --output build/artifacts
```

The packager requires the exact already-tested signed BTServer output. Use
Procursus ldid v2.1.5-procursus7, as in the original build, to reproduce it.
Verify each output checksum; the generated kernel must match
`c082f2b423e04aa60a71840c573557d9564d70542f45468de6c60fc2159ff0a8`.

See [implementation details](docs/implementation.md) and [license notices](NOTICE.md).


The v2 motion resources can be reproduced without rebuilding the audio donor:

```sh
python3 tools/build_motion.py --backboardd inputs/backboardd \
  --output build/motion --ldid /path/to/ldid
python3 tools/package_motion.py --base-backboardd inputs/backboardd \
  --patched-backboardd build/motion/backboardd \
  --module build/motion/libtouch4motion.dylib --output artifacts
```

Use the unmodified public iPhone3,3 11D257 `usr/libexec/backboardd`. The builder
checks its hash, preserves executable `__text` and entitlements, and requires
the resulting signed binaries to match the hardware-tested hashes. Signing
identifiers are retained so that reproduction is byte-for-byte. The v1 archive
remains available as the immutable Bluetooth/audio/wallpaper input to the v2
packager. These Python tools run only in this independent maintainer repository.
