# Implementation and earlier hardware validation

## Technical details

### Bluetooth

N81's product hash is missing from the 11D257 BTServer classifier. It falls
into an unknown class whose Device ID vendor source is zero; registration
returns 101. At file offset `0x15b63c`, this patch replaces the iPad1,1
classifier product hash with N81's hash, using the same BCM4329B1 classification
whose vendor source is 2. This is scoped to BTServer; it does not spoof the
system model. At `0x163654`, the selected class's `isSupported` virtual pointer
changes from `0x76f1d` to the existing constant-true function `0x94f81`.
Other chipset operations and BLE flags are unchanged. Class identity and
cold-boot behavior still need broader testing.

### Audio

The public N92 kernel contains CS42L61; N81 needs CS42L59. The linker resolves
675 relocation fixups at `0x80dac000`, fixes the inherited Mikey vtable slot
introduced in 7.1, and adjusts the compiled superclass virtual call from
`0x3f0` to `0x3f4`. It preserves the prelink XML's types and ID/IDREF graph,
including 14 OSData tags, and emits XNU-compatible `<tag/>` empty tags.

The original N81 `audio0/reg` is a 32-byte legacy structure, while the current
AppleARMIISDevice expects 36 bytes. The bridge at `0x80dac400`, called from
`0x804fbc1c`, translates **only** the exact eight-word N81 structure. Other
short inputs remain rejected, and inputs of at least 36 bytes retain the
original path. The converted configuration uses flags `0x10`, 6 MHz input
MCLK and IIS slave role. `AppleEmbeddedAudio` looks up the original tree's
`codec` interrupt name instead of `mikey`. The bridge uses PC-relative branches
and constants and introduces no new absolute pointers for KASLR to fix up.

V5's flags `0x11` produced playback-dependent hiss, strongest on the right,
with normal song speed and pitch. Restarting mediaserverd did not help.
Changing only the master/slave bit to `0x10` in v6 eliminated the reported
hiss on both wired channels and the speaker. That is an isolated hardware
result; it does not validate every rate, capture path, or startup sequence.

### Rotation

11D257 CoreMotion classifies N81 as model 0. HID already supplies real sensor
events, but the high-level backend initializes without usable acceleration or
device-orientation samples. Setting this process's writable model cache to the
iOS 6 N81 enum 11 before backend initialization restores acceleration, gyro,
fusion and orientation callbacks. Loading later does not repair the cached
backend, even after manager objects are recreated.

The module constructor checks iPod4,1/N81AP, ARM Mach-O32, CoreMotion UUID
`f541183564873c8489cce9deca3e9bd5` and the original getter instructions. It
calculates the runtime slide from the loaded image, only changes the writable
model slot when both getter and slot report 0, and leaves model 11 unchanged.
Unknown versions or other recognized models are rejected. The original getter
code and the system shared-cache file are untouched.

The signed backboardd binary receives one `LC_LOAD_DYLIB` dependency on
`/usr/lib/libtouch4motion.dylib`, using verified zero-filled header padding.
Its complete 239732-byte `__text` and entitlement dictionary remain unchanged.
The binary patch includes its resulting ad hoc signature. The original
launchd configuration, boot chain and audio kernel remain unchanged by this
additional repair. The existing Aquila runtime is still needed.

On an 8 GB N81, early loading restored Safari landscape in both directions,
return to portrait, rotation lock and rotation after lock/unlock. The same
signed module and patched daemon were then installed at their final system
paths, a full OS reboot completed, and all those physical tests passed again.
This result covers system orientation through backboardd; independent app
CoreMotion processes are not fixed. A fresh full restore using the v2 Kit
bundle and a separate power-off/power-on cycle remain untested.

### Wallpaper

Create `/Library/Wallpaper/iPod` links with `~ipod` names pointing at existing
`iPhone` PNGs and thumbnails. There are 67 links and no additional image data.
The user confirms that only the default iOS 7 wallpaper displays; the stock
Settings gallery/directory still does not work normally. This is a partial
resource repair, not a complete gallery fix.

## Verification

```sh
python3 tests/test_kit_integration.py --kit /path/to/Legacy-iOS-Kit \
  --kernelcache inputs/kernelcache
python3 tests/test_motion_integration.py --kit /path/to/Legacy-iOS-Kit \
  --rootfs inputs/rootfs.dec.dmg
bash -n /path/to/Legacy-iOS-Kit/restore.sh
```

The host tests exercise the Kit's actual shell helper with native `bspatch`,
`xpwntool` and `hfsplus`: kernel round trip/idempotence, supported device scope,
resource corruption, IPSW version invalidation and cache recovery, Just Boot,
backboardd binary reproduction, entitlements and unchanged executable code,
real HFS readback/permissions, and rejection of an unsupported daemon before
rootfs writes. No test accesses USB or restores a device.

The v2 raw kernel remains
`c082f2b423e04aa60a71840c573557d9564d70542f45468de6c60fc2159ff0a8`.
The module and daemon match the full-reboot-tested outputs listed in
`artifacts/manifest.json`. Bluetooth/music hardware results and the remaining
system-sound and wallpaper-gallery limitations are unchanged. The integrated
v2 bundle still needs a fresh full device restore.
