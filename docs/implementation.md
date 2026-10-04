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

### Wallpaper

Create `/Library/Wallpaper/iPod` links with `~ipod` names pointing at existing
`iPhone` PNGs and thumbnails. There are 67 links and no additional image data.
The user confirms that only the default iOS 7 wallpaper displays; the stock
Settings gallery/directory still does not work normally. This is a partial
resource repair, not a complete gallery fix.

## Verification

```sh
python3 tests/test_kit_integration.py --kit /path/to/Legacy-iOS-Kit
bash -n restore.sh
# Optional, after generating the candidate; requires Unicorn 2.1.4:
python3 tools/test_bridge.py \
  saved/touch4-ios7/11D257/hardware/kernel.n81.macho
```

Offline validation reproduced the original v6 linked kernel and the v7
kernel-only output exactly. The latter raw kernel is
`c082f2b423e04aa60a71840c573557d9564d70542f45468de6c60fc2159ff0a8`;
with the tested Kit template its Img3 is
`b473817cb826a8aad426dfc3b1d9b45335921f6c699b054dee04b794aba8e434`.
Assembly source compilation reproduces all 132 bridge bytes. All six
regular overlay files match HFS readback; every wallpaper link target exists.
BTServer permissions and MobileGestalt ownership were checked. Five host
integration tests cover input rejection, opt-in filenames, supported-device
scope and original/experimental Just Boot selection, plus enabling the repair in the normal restore menu, with no USB operations.


Music playback is verified; charging, locking and keyboard sound effects remain unresolved. The new default integration is host-tested, with a fresh real-device restore pending.
