# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline research helper: use zero header padding for one LC_LOAD_DYLIB.

This does not touch a connected device. Re-sign the resulting copy afterwards.
"""
import argparse
from pathlib import Path
import struct

def add_dependency(source, install_name):
    blob = bytearray(source)
    if struct.unpack_from('<II', blob)[0:2] != (0xfeedface, 12):
        raise ValueError('Expected an ARM Mach-O32 image')
    count, size = struct.unpack_from('<II', blob, 16)
    offset = 28
    file_sections = []
    for _ in range(count):
        cmd, cmdsize = struct.unpack_from('<II', blob, offset)
        if cmdsize < 8 or offset + cmdsize > 28 + size:
            raise ValueError('Invalid load command')
        if cmd == 1:
            nsects = struct.unpack_from('<I', blob, offset + 48)[0]
            for index in range(nsects):
                section = struct.unpack_from('<16s16s9I', blob, offset + 56 + index * 68)
                if section[4] and section[8] & 0xff not in (1, 12):
                    file_sections.append(section[4])
        if cmd == 12:
            nameoff = struct.unpack_from('<I', blob, offset + 8)[0]
            if blob[offset + nameoff:offset + cmdsize].split(b'\0')[0].decode() == install_name:
                raise ValueError('Dependency already present')
        offset += cmdsize
    if offset != 28 + size or not file_sections:
        raise ValueError('Unsupported command/section layout')
    name = install_name.encode() + b'\0'
    command_size = (24 + len(name) + 3) & ~3
    if offset + command_size > min(file_sections) or any(blob[offset:offset + command_size]):
        raise ValueError('No zero-filled header padding')
    command = struct.pack('<6I', 12, command_size, 24, 0, 0x10000, 0x10000)
    blob[offset:offset + command_size] = (command + name).ljust(command_size, b'\0')
    struct.pack_into('<II', blob, 16, count + 1, size + command_size)
    return bytes(blob)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('install_name')
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('Use a separate output file')
    args.output.write_bytes(add_dependency(args.source.read_bytes(), args.install_name))
