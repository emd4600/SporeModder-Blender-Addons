import struct


class FileReader:
    def __init__(self, buffer):
        self.buffer = buffer

    def __len__(self):
        return len(self.buffer)

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

    def __len__(self):
        return len(self.buffer)

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

    def tell(self):
        return len(self.buffer)

    def seek(self, n):
        raise NotImplementedError()


class ResourceKey:
    def __init__(self, group_id=-1, instance_id=-1, type_id=-1):
        self.group_id = group_id
        self.instance_id = instance_id
        self.type_id = type_id

    def read(self, reader: FileReader, endian='<'):
        self.instance_id, self.type_id, self.group_id = reader.unpack(endian + 'III')


def write_alignment(file: FileWriter, alignment):
    file_pos = file.tell()
    padding = ((file_pos + alignment - 1) & ~(alignment - 1)) - file_pos
    file.write(bytearray(padding))


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
    0x0989FD18: 'Splash',
    0xDFB699F5: 'Call',
    0xBD2312BF: 'Talk',
    0xB8F33895: 'Cycle',
    0x70FAA1FE: 'Pack',
    0x35EFD0FB: 'Unpack',
    0x40969046: 'Animate',
    0x407759E6: 'Pop',
    0xE59072D6: 'Hoist',
    0xFDF757AC: 'Ching',
    0x2E1BC9BA: 'Breaking',
    0x310FFCC1: 'Spin',
    0x7007F1E9: 'Hatch',
    0xB9DEFBFD: 'Bobble',
    0xBCA068E2: 'Hold',
    0x5AF184FB: 'Peel',
    0x449D8DAE: 'Awake',
    0x090D7F4D: 'Swim',
    0x91DED948: 'Dias',
    0xC602CD31: 'Tree',
    0x7E680939: 'FlagMotion',
    0x019E577C: 'herbivore1',
    0x019E577F: 'herbivore2',
    0xC7E19209: 'carnivore1',
    0xC7E1920A: 'carnivore2',
    0x86F9D089: 'omnivore1',
    0x86F9D08A: 'omnivore2',
    0x5CD8CD16: 'upgrade01',
    0x5BD8CBA6: 'upgrade12',
    0x5ED8D07E: 'upgrade23',
    0x5DD8CE8E: 'upgrade34',
    0xA502DC0B: 'runtime',
    0xBC27846D: 'DeformAxisUpLeft',
    0x0C292EFF: 'DeformAxisUpFront',
    0x29771A9E: 'DeformAxisRightFront',
    0x2BE7B75B: 'DeformAxisLeftFront',
    0xB9D307D8: 'DeformRadius',
    0xBB7F0931: 'DeformRadiusTop',
    0x3AF5266F: 'DeformRadiusMiddle',
    0x808C04D9: 'DeformRadiusBottom',
    0x92BF11C2: 'DeformAxisFront',
    0x2E6521F4: 'DeformAxisForward',
    0x9BFE8BF8: 'DeformAxisBack',
    0x2D3BFA19: 'DeformAxisRight',
    0x7CC96C02: 'DeformAxisLeft',
    0xD02751DE: 'DeformAxisUp',
    0xE6F2C2B9: 'DeformAxisDown',
    0x884317A9: 'DeformBoneBaseJoint',
    0x1B486C71: 'DeformBoneEndJoint',
    0x1F59DA43: 'DeformBoneMiddle',
    0x267AFA7C: 'DeformThickness',  #TODO
    0x837EB7F4: 'DeformAxleLength',  #TODO
    0xF320BA37: 'BoneLength',
    0x503283AA: 'Nudge',
    0xD0BE09E0: 'joint1',
    0xD0BE09E2: 'joint3',
    0xD0BE09E3: 'joint2',
    0xD0BE09E4: 'joint5',
    0xD0BE09E5: 'joint4',
    0xD0BE09E6: 'joint7',
    0xD0BE09E7: 'joint6',
    0xD0BE09E8: 'joint9',
    0xD0BE09E9: 'joint8',
    0x7B298B90: 'joint10',
    0x7B298B91: 'joint11',
    0x7B298B92: 'joint12',
    0x7B298B93: 'joint13',
    0x7B298B94: 'joint14',
    0x7B298B95: 'joint15',
    0x7B298B96: 'joint16',
    0x7B298B97: 'joint17',
    0x7B298B98: 'joint18',
    0x7B298B99: 'joint19',
    0x7E299069: 'joint20',
    0x7E299068: 'joint21',
    0x7E29906B: 'joint22',
    0x7E29906A: 'joint23',
    0x7E29906D: 'joint24',
    0x7E29906C: 'joint25',
    0x7E29906F: 'joint26',
    0x7E29906E: 'joint27',
    0x7E299061: 'joint28',
    0x7E299060: 'joint29',
    0x66B08008: 'down_joint',
    0x7279E1FB: 'up_joint',
    0xDF4D5328: 'right_joint',
    0xCE218D7F: 'left_joint',
    0x5635C0CD: 'back_joint',
    0xF28D197F: 'front_joint',
    0x7BD05F71: 'root',
    0xC045A9A3: 'tool',
    0x4CF9B596: 'base',
    0x6DFE676D: 'body',
    0x002AE8E9: 'spike',
    0x7FFECF23: 'upper',
    0x467E1EA9: 'mid',
    0x32860993: 'global_node',
    0x89332E8F: 'tail_1',
    0x89332E8C: 'tail_2',
    0x89332E8D: 'tail_3',
    0x41945228: 'neck',
    0x2E8647BD: 'jaw',
    0x6F772BAB: 'bl',
    0x6B772517: 'fl',
    0x6F772BB5: 'br',
    0x6B772509: 'fr',
    0x4DA6B724: 'rotate',
    0x050C5D2F: '0',
    0x050C5D2E: '1',
    0x050C5D2D: '2',
    0x050C5D2C: '3',
    0x050C5D2B: '4',
    0x050C5D2A: '5',
    0x050C5D29: '6',
    0x050C5D28: '7',
    0x050C5D27: '8',
    0x050C5D26: '9',
    0x7364D4C2: 'Key 0',
    0x7364D4C3: 'Key 1',
    0x7364D4C0: 'Key 2',
    0x7364D4C1: 'Key 3',
    0x7364D4C6: 'Key 4',
    0x7364D4C7: 'Key 5',
    0x7364D4C4: 'Key 6',
    0x7364D4C5: 'Key 7',
    0x7364D4CA: 'Key 8',
    0x7364D4CB: 'Key 9',
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
