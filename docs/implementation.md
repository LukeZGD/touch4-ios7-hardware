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

### Voice Memos and video recording

The CS42L59 input stream exists in the IOAudio2 registry, but VirtualAudio
classifies the unsupported N81 product as model 0. Voice Memos logs
`Category cvm is not supported`; Camera fails to initialize its input AudioUnit
with `nohw`. Selecting VirtualAudio's existing model 16 K93 single-microphone
routing database and handlers restored both recording paths on the test device.

The guarded module loads through a new `LC_LOAD_DYLIB` dependency on
`/usr/lib/libtouch4audioroute.dylib`. It requires iPod4,1/N81AP, ARM Mach-O32,
VirtualAudio UUID `d67d8d297bb836faae231b0b458cbe98`, expected getter bytes at
`0x15778`, and a writable segment containing the model cache at `0x2adf88`.
It initializes the getter and changes only an unknown cached model 0 to 16;
an already-correct 16 is left unchanged. The complete plugin executable code
and empty entitlements are retained. Existing N81 tuning files and the codec
driver remain unchanged. This capture repair introduces no additional kernel,
shared-cache, DeviceTree, bootloader or launch-configuration patches.

After installation and a mediaserverd restart, the constructor returned 1
and AVAudioSession reported an available microphone. The user confirmed Voice
Memos recording/playback, video recording/playback and music playback with the
guarded outputs. A full device reboot and fresh restore with v3 have not yet
been tested. The borrowed K93 profile does not establish correctness of all
microphone routes, gains or DSP modes. Raw device logs and recordings are not
included in this repository. System sound effects are handled separately by the v4 policy below.

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
CoreMotion processes are not fixed. The device owner subsequently completed
a fresh full restore through the normal v2 Kit flow and reported no problems.
A separate power-off/power-on cycle remains untested.

### Wallpaper

The existing 67 `/Library/Wallpaper/iPod` links retain `~ipod` names pointing
at stock iPhone PNGs and thumbnails. The gallery's blank APPLE WALLPAPER section
was a separate layout failure: MobileGestalt reported procedural wallpapers
as supported, but this firmware has no procedural wallpaper resources. The
category layout takes its size from a missing dynamic thumbnail, producing
zero-sized static buttons and labels.

V4 changes only `CacheData[1856]` from 1 to 0 in the existing Kit N81 template
(with its Bluetooth correction retained). In 11D257, cached boolean answer
232 is `UIProceduralWallpaperCapability` (hash `UZyrJHlX635ocWEjBkt9YA`).
The layout is 248 eight-byte answers followed by 248 validity bytes at 1984;
the validity byte at 2216 remains 1. Plain/hash CacheExtra overrides are
ineffective because this answer uses the cached fast path. The underlying
DeviceTree property's index 117 is not this answer's cache index.

The builder checks the template build, device, board, length and original
answer/validity before writing. All other data and CacheExtra are preserved.
No personal device cache, wallpaper database, shared-cache binary or DeviceTree
is published or patched. Static-only layout produces 90×135 thumbnails and
nonzero category frames. A native gallery probe enumerated 66 factory items
and decoded their thumbnails; the owner accepted the resulting wallpaper fix.
Dynamic wallpapers are not supplied. Full reboot/fresh v4 restore is untested.

### System sound effects

11D257 CoreMedia loads `SystemSoundRingerSettings.plist` under the model-specific
MediaToolbox directory. The existing N81 directory had the legacy
`SystemSoundBehaviour.plist` but lacked the newer policy. V4 installs
`/System/Library/Frameworks/MediaToolbox.framework/N81/SystemSoundRingerSettings.plist`,
built from the public 11D257 Default policy. For KeyPressed, PINKeyPressed,
ScreenLocked, ScreenUnlocked, ConnectedToPower and KeyPressClickPreview,
it selects `RingVibrateIgnore,SilentVibrateIgnore,RingerSwitchIgnore: [Beep]`
for N81 hardware without a ringer switch. All other Default event policies
remain unchanged; callers still control lock/keyboard sound preferences.

After live installation and an audio-service restart, the model-specific
readback succeeded and the owner confirmed system sound effects worked.
No new audio binary, codec tuning, launch job or boot patch is needed. Broader
notification/mute behavior and a full reboot/fresh v4 restore remain untested.

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
backboardd/VirtualAudio binary patches, entitlements and unchanged executable code,
real HFS readback/permissions, and rejection of unsupported binaries before
rootfs writes. No test accesses USB or restores a device.

The v2/v3/v4 raw kernel remains
`c082f2b423e04aa60a71840c573557d9564d70542f45468de6c60fc2159ff0a8`.
The module and daemon match the full-reboot-tested outputs listed in
`artifacts/manifest.json`. Bluetooth/music hardware results are unchanged. The v4 overlay adds the
system sound policy and static-gallery capability correction described above. A fresh
full restore with the integrated v2 bundle subsequently passed (user-reported).
The v3 bundle adds only the capture-routing dependency and module to the
previous repairs. Its separate validation record is `tests/validation-capture.json`.

V4 reproduction and guarded overlay-delta tests are in `tests/test_ui_resources.py`.
The actual HFS test reads back both new plists and checks permissions/ownership.
