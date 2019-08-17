import struct


class FileReader:
    def __init__(self, buffer):
        self.buffer = buffer

    def read_byte(self, endian='<'):
        return struct.unpack(endian + 'b', self.buffer.read(1))[0]

    def read_ubyte(self, endian='<'):
        return struct.unpack(endian + 'B', self.buffer.read(1))[0]

    def read_short(self, endian='<'):
        return struct.unpack(endian + 'h', self.buffer.read(2))[0]

    def read_ushort(self, endian='<'):
        return struct.unpack(endian + 'H', self.buffer.read(2))[0]

    def read_int(self, endian='<'):
        return struct.unpack(endian + 'i', self.buffer.read(4))[0]

    def read_uint(self, endian='<'):
        return struct.unpack(endian + 'I', self.buffer.read(4))[0]

    def read_float(self, endian='<'):
        return struct.unpack(endian + 'f', self.buffer.read(4))[0]

    def read_double(self, endian='<'):
        return struct.unpack(endian + 'd', self.buffer.read(8))[0]

    def read_boolean(self, endian='<'):
        return struct.unpack(endian + '?', self.buffer.read(1))[0]

    def read(self, n):
        return self.buffer.read(n)

    def seek(self, offset):
        self.buffer.seek(offset)

    def skip_bytes(self, n_bytes):
        self.buffer.seek(n_bytes, 1)

    def unpack(self, fmt):
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, self.buffer.read(size))

    def tell(self):
        return self.buffer.tell()


class ArrayFileReader(FileReader):
    def __init__(self, data):
        super(ArrayFileReader, self).__init__(data)
        self.offset = 0

    def read_byte(self, endian='<'):
        self.offset += 1
        return struct.unpack_from(endian + 'b', self.buffer, self.offset - 1)[0]

    def read_ubyte(self, endian='<'):
        self.offset += 1
        return struct.unpack_from(endian + 'B', self.buffer, self.offset - 1)[0]

    def read_short(self, endian='<'):
        self.offset += 2
        return struct.unpack_from(endian + 'h', self.buffer, self.offset - 2)[0]

    def read_ushort(self, endian='<'):
        self.offset += 2
        return struct.unpack_from(endian + 'H', self.buffer, self.offset - 2)[0]

    def read_int(self, endian='<'):
        self.offset += 4
        return struct.unpack_from(endian + 'i', self.buffer, self.offset - 4)[0]

    def read_uint(self, endian='<'):
        self.offset += 4
        return struct.unpack_from(endian + 'I', self.buffer, self.offset - 4)[0]

    def read_float(self, endian='<'):
        self.offset += 4
        return struct.unpack_from(endian + 'f', self.buffer, self.offset - 4)[0]

    def read_boolean(self, endian='<'):
        self.offset += 1
        return struct.unpack_from(endian + '?', self.buffer, self.offset - 1)[0]

    def skip_bytes(self, n_bytes):
        self.offset += n_bytes

    def seek(self, offset):
        self.offset = offset

    def read(self, n_bytes):
        result = self.buffer[self.offset:self.offset + n_bytes]
        self.offset += n_bytes
        return result

    def unpack(self, fmt):
        result = struct.unpack_from(fmt, self.buffer, self.offset)
        self.offset += struct.calcsize(fmt)
        return result

    def tell(self):
        return self.offset


class FileWriter:
    def __init__(self, buffer):
        self.buffer = buffer

    def write_byte(self, value, endian='<'):
        self.buffer.write(struct.pack(endian + 'b', value))

    def write_ubyte(self, value, endian='<'):
        self.buffer.write(struct.pack(endian + 'B', value))

    def write_short(self, value, endian='<'):
        self.buffer.write(struct.pack(endian + 'h', value))

    def write_ushort(self, value, endian='<'):
        self.buffer.write(struct.pack(endian + 'H', value))

    def write_int(self, value, endian='<'):
        self.buffer.write(struct.pack(endian + 'i', value))

    def write_uint(self, value, endian='<'):
        self.buffer.write(struct.pack(endian + 'I', value))

    def write_float(self, value, endian='<'):
        self.buffer.write(struct.pack(endian + 'f', value))

    def write_double(self, value, endian='<'):
        self.buffer.write(struct.pack(endian + 'd', value))

    def write_boolean(self, value, endian='<'):
        self.buffer.write(struct.pack(endian + '?', value))

    def write(self, array):
        self.buffer.write(array)

    def pack(self, fmt, *args):
        self.buffer.write(struct.pack(fmt, *args))

    def tell(self):
        return self.buffer.tell()

    def seek(self, n):
        self.buffer.seek(n)


class ArrayFileWriter(FileWriter):
    def __init__(self):
        super(ArrayFileWriter, self).__init__(bytearray())

    def write_byte(self, value, endian='<'):
        self.buffer.extend(struct.pack(endian + 'b', value))

    def write_ubyte(self, value, endian='<'):
        self.buffer.extend(struct.pack(endian + 'B', value))

    def write_short(self, value, endian='<'):
        self.buffer.extend(struct.pack(endian + 'h', value))

    def write_ushort(self, value, endian='<'):
        self.buffer.extend(struct.pack(endian + 'H', value))

    def write_int(self, value, endian='<'):
        self.buffer.extend(struct.pack(endian + 'i', value))

    def write_uint(self, value, endian='<'):
        self.buffer.extend(struct.pack(endian + 'I', value))

    def write_float(self, value, endian='<'):
        self.buffer.extend(struct.pack(endian + 'f', value))

    def write_boolean(self, value, endian='<'):
        self.buffer.extend(struct.pack(endian + '?', value))

    def write(self, array):
        self.buffer.extend(array)

    def pack(self, fmt, *args):
        self.buffer.extend(struct.pack(fmt, *args))

    def seek(self, n):
        raise NotImplementedError()


class ResourceKey:
    def __init__(self, group_id=-1, instance_id=-1, type_id=-1):
        self.group_id = group_id
        self.instance_id = instance_id
        self.type_id = type_id

    def read(self, reader: FileReader, endian='<'):
        self.instance_id, self.type_id, self.group_id = reader.unpack(endian + 'III')


SPORE_NAMES = {
    0x89e06a31: 'ClsdOpen',
    0x75d4c8cd: 'Point',
    0x998BBF67: 'TurnOn',
    0x5D8D0055: 'SmileFrown',
    0x892788C6: 'LickAir',
    0xDD0DCEF4: 'Unique',
    0x9891EEC7: 'MadSad',
    0x30EE8F49: 'Scared',
    0xAC04E296: 'Tuck',
    0x47F0B3DC: 'Bend',
    0x39E912E1: 'DroopRaise',
    0x70E47545: 'Scale',
    0x98C942B6: 'Data1',
    0x98C942B5: 'Data2',
    0x98C942B4: 'Data3',
    0x98C942B3: 'Data4',
    0x98C942B2: 'Data5',
    0x114BB90C: 'Breathe',
    0x15054351: 'Stun',
    0xC2299AA7: 'Impact',
    0x6FB760FF: 'Idle',
    0xB37B55B2: 'Move',
    0x2F056C5D: 'Stop',
    0x0AC4AEED: 'Attack',
    0xFD29BD8E: 'ChargeUp',
    0x2D7AE6C2: 'ChargeHold',
    0x0EFD249C: 'ChargeRelease',
    0xBC27846D: 'DeformAxisUpLeft',
    0x0C292EFF: 'DeformAxisUpFront',
    0x29771A9E: 'DeformAxisRightFront',
    0x2BE7B75B: 'DeformAxisLeftFront',
    0xB9D307D8: 'DeformRadius',
    0xBB7F0931: 'DeformRadiusTop',
    0x808C04D9: 'DeformRadiusBottom',
    0x92BF11C2: 'DeformAxisFront',
    0x2E6521F4: 'DeformAxisForward',
    0x9BFE8BF8: 'DeformAxisBack',
    0x2D3BFA19: 'DeformAxisRight',
    0x7CC96C02: 'DeformAxisLeft',
    0xD02751DE: 'DeformAxisUp',
    0xD0BE09E0: 'joint1',
    0xD0BE09E2: 'joint3',
    0xD0BE09E3: 'joint2',
    0xD0BE09E4: 'joint5',
    0xD0BE09E5: 'joint4',
    0xD0BE09E6: 'joint7',
    0xD0BE09E7: 'joint6',
    0xD0BE09E8: 'joint9',
    0xD0BE09E9: 'joint8'
}


def get_hash(name: str) -> int:
    """
    Returns the hash ID of the given string; if the string starts with 0x or #, it
    is interpreted as an hexadecimal number; otherwise, its FNV hash will be returned.
    :param name:
    :return:
    """
    if len(name) == 0:
        return 0
    elif name[0:2] == '0x':
        return int(name, 16)
    elif name[0] == '#':
        return int(name[1:], 16)
    else:
        string = name.lower()
        hval = 0x811c9dc5
        fnv_32_prime = 0x01000193
        uint32_max = (2 ** 32)
        for s in string:
            hval = (hval * fnv_32_prime) % uint32_max
            hval ^= ord(s)
        return hval


def get_name(hash_id: int) -> str:
    """
    Returns the string representation of a given 32-bit ID. If the ID is the hash of any of
    the known names in SPORE_NAMES, then it returns that name; otherwise, it will
    return the hexadecimal representation of the ID.
    :param hash_id:
    :return:
    """
    if hash_id in SPORE_NAMES:
        return SPORE_NAMES[hash_id]
    else:
        return f"0x{hash_id:08x}"
