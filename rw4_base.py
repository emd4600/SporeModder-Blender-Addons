"""
This module contains:
  - FileReader, FileWriter: classes for reading/writing binary files, supporting different types (int, float, byte,...).
  - RenderWare: a class which allows parsing or creating rw4 files.
  - Classes for all supported RenderWare4 objects, as well as methods for reading/writing them.
"""

__author__ = 'Eric'

import struct
from collections import namedtuple
from .file_io import FileReader, FileWriter, ArrayFileReader
from . import rw4_enums


class ModelError(Exception):
    def __init__(self, message, cause_object=None):
        super().__init__(message)
        self.cause_object = cause_object


class RWMatrix:
    def __init__(self, rows, columns):
        # We store the columns, rows is just len(self.data)
        self.columns = columns
        self.data = []
        for i in range(0, rows):
            self.data.append([None] * columns)

    def __getitem__(self, item):
        return self.data[item]

    def read(self, file: FileReader):
        for i in range(0, len(self.data)):
            for j in range(0, self.columns):
                self.data[i][j] = file.read_float()

    def write(self, file: FileWriter):
        for i in range(0, len(self.data)):
            for j in range(0, self.columns):
                file.write_float(self.data[i][j])


class RWHeader:
    def __init__(self, render_ware, rw_type_code=0, sub_references=None, p_sub_reference_offsets=0):
        self.render_ware = render_ware
        self.rw_type_code = rw_type_code
        self.p_section_infos = 0
        self.p_buffer_data = 0
        self.section_count = 0

        self.section_manifest = SectionManifest(
            render_ware,
            field_0=4,
            field_4=12
        )

        self.section_types = SectionTypes(
            render_ware,
            field_4=12
        )

        self.section_external_arenas = SectionExternalArenas(
            render_ware,
            field_0=3,
            field_4=0x18,
            field_8=1,
            field_c=0xffb00000,
            field_10=1,
            field_14=0,
            field_18=0,
            field_1c=0
        )

        self.section_sub_references = SectionSubReferences(
            render_ware,
            sub_references=sub_references,
            field_4=0,
            field_8=0,
            p_sub_reference_offsets=p_sub_reference_offsets
        )

        self.section_atoms = SectionAtoms(
            render_ware,
            field_0=0,
            field_4=0
        )

    def read(self, file: FileReader):
        file.seek(28)
        self.rw_type_code = file.read_int()

        file.read_int()  # this one is sectionCount too, but apparently Spore uses the second one
        self.section_count = file.read_int()  # 24h
        file.read_int()  # 0x10 if it's a model, 4 if it's a texture
        file.read_int()  # always 0 ?
        self.p_section_infos = file.read_int()  # 30h
        file.read_int()  # always 0x98
        file.read_int()  # always 0 ?
        file.read_int()  # always 0 ?
        file.read_int()  # always 0 ?
        self.p_buffer_data = file.read_int()

        # we don't need to continue, nothing important here

    def write(self, file: FileWriter, buffers_size):
        file.write(
            b'\x89RW4w32\x00\x0D\x0A\x1A\x0A\x00\x20\x04\x00454\x00000\x00\x00\x00\x00\x00')

        file.pack('<iiiiiiiiiii',
                  self.rw_type_code, self.section_count, self.section_count, 16, 0,
                  self.p_section_infos, 152,
                  0, 0, 0,
                  self.p_buffer_data)

        file.pack('<ii', 16, buffers_size)
        file.pack('<iiiii', 4, 0, 1, 0, 1)
        file.pack('<i', 0)  # 0x00C00758 ?
        file.pack('<iiiii', 4, 0, 1, 0, 1)
        file.pack('<iiiiiii', 0, 1, 0, 0, 0, 0, 0)

        p_section_manifest = file.tell()
        file.write_int(SectionManifest.type_code)
        self.section_manifest.write(file)

        self.section_manifest.p_section_types = file.tell() - p_section_manifest
        file.write_int(SectionTypes.type_code)
        self.section_types.write(file)

        self.section_manifest.p_section_external_arenas = file.tell() - p_section_manifest
        file.write_int(SectionExternalArenas.type_code)
        self.section_external_arenas.write(file)

        self.section_manifest.p_section_sub_references = file.tell() - p_section_manifest
        file.write_int(SectionSubReferences.type_code)
        self.section_sub_references.write(file)

        self.section_manifest.p_section_atoms = file.tell() - p_section_manifest
        file.write_int(SectionAtoms.type_code)
        self.section_atoms.write(file)

        # Write the section manifest again now we have all offsets
        previous_offset = file.tell()
        file.seek(p_section_manifest + 4)
        self.section_manifest.write(file)
        file.seek(previous_offset)


INDEX_OBJECT = 0
INDEX_NO_OBJECT = 1
INDEX_SUB_REFERENCE = 2

SubReference = namedtuple('SubReference', ('rw_object', 'offset'))


class RenderWare4:

    def __init__(self):
        self.objects = []
        self.header = RWHeader(self)
        self.excluded_types = []

    def get_objects(self, type_code):
        return [x for x in self.objects if x is not None and x.type_code == type_code]

    def get_object(self, index):
        section_type = index >> 0x16
        if section_type == INDEX_OBJECT:
            return self.objects[index]
        elif section_type == INDEX_SUB_REFERENCE:
            return self.objects[self.header.section_sub_references.sub_references[index & 0x3FFFF].rwObject]
        elif section_type == INDEX_NO_OBJECT and (index & 0x3FFFF) == 0:
            return None
        else:
            raise NameError("Unsupported index %x" % index)

    def get_index(self, rw_object, section_type=INDEX_OBJECT):
        if section_type == INDEX_OBJECT:
            if rw_object is None:
                return -1
            return self.objects.index(rw_object)
        elif section_type == INDEX_SUB_REFERENCE:
            index = INDEX_SUB_REFERENCE << 0x16
            for reference in self.header.section_sub_references.sub_references:
                if reference.rw_object == rw_object:
                    return index
                index += 1
            else:
                return -1
        elif section_type == INDEX_NO_OBJECT and rw_object is None:
            return INDEX_NO_OBJECT << 0x16
        else:
            raise NameError("Unsupported get_index for sectionType %x" % section_type)

    def create_object(self, type_code):
        """
        Creates an instance of an object, whose type depends on the given type code.
        :param type_code:
        :return:
        """
        for supportedObject in RWObject.__subclasses__():
            if supportedObject.type_code == type_code:
                obj = supportedObject(self)
                self.objects.append(obj)
                return obj

        return None

    def add_object(self, obj):
        """
        Adds an object, which will be written into the RenderWare4 data.
        :param obj:
        :return:
        """
        self.objects.append(obj)

    def add_sub_reference(self, rw_object, offset):
        """
        Adds a subreference that is 'offset' bytes ahead from the object data.
        :returns: The int that is used to index this sub reference.
        """
        reference = SubReference(rw_object=rw_object, offset=offset)
        self.header.section_sub_references.sub_references.append(reference)
        return (len(self.header.section_sub_references.sub_references) - 1) | (INDEX_SUB_REFERENCE << 0x16)

    def read(self, file: FileReader):

        self.header.read(file)

        file.seek(self.header.p_section_infos)

        for i in range(self.header.section_count):
            section_info = RWSectionInfo(self)
            section_info.read(file)
            obj = self.create_object(section_info.type_code)
            if obj is not None:
                obj.section_info = section_info
            else:
                # add a None object anyways so indices work correctly
                self.objects.append(None)

        for obj in self.objects:
            if obj is not None and obj.type_code not in self.excluded_types:
                self.seek_to_data(file, obj)
                obj.read(file)

    def write(self, file: FileWriter):
        def write_alignment(alignment):
            file_pos = file.tell()
            padding = ((file_pos + alignment - 1) & ~(alignment - 1)) - file_pos
            file.write(bytearray(padding))

        # First we need to create the list with all the type_codes
        self.header.section_count = len(self.objects)

        self.header.section_types.type_codes.append(0)
        self.header.section_types.type_codes.append(0x10030)
        self.header.section_types.type_codes.append(0x10031)
        self.header.section_types.type_codes.append(0x10032)
        self.header.section_types.type_codes.append(0x10010)

        # We do them in a separate list because apparently they have to be sorted
        used_type_codes = []
        for obj in self.objects:
            if obj.type_code not in used_type_codes and obj.type_code != 0x10030:
                used_type_codes.append(obj.type_code)

        self.header.section_types.type_codes.extend(sorted(used_type_codes))

        # Now write the header
        self.header.write(file, 0)

        # Create section infos for every object
        for obj in self.objects:
            obj.section_info = RWSectionInfo(
                self,
                field_04=0,
                alignment=obj.alignment,
                type_code_index=self.header.section_types.type_codes.index(obj.type_code),
                type_code=obj.type_code
            )

        # Write all objects except BaseResources
        for obj in self.objects:
            if obj.type_code != BaseResource.type_code:
                # write padding so it is aligned
                write_alignment(obj.alignment)

                obj.section_info.p_data = file.tell()
                obj.write(file)
                obj.section_info.data_size = file.tell() - obj.section_info.p_data

        # Write section infos, remember the position where we write them since we will have to write them again
        self.header.p_section_infos = file.tell()
        for obj in self.objects:
            obj.section_info.write(file)

        # ??
        self.header.section_sub_references.p_sub_reference_offsets = file.tell()

        # Apparently this is necessary?
        file.write(bytearray(48))

        # Now write the BaseResources
        self.header.p_buffer_data = file.tell()
        for obj in self.objects:
            if obj.type_code == BaseResource.type_code:
                # write padding so it is aligned
                write_alignment(obj.alignment)

                start_pos = file.tell()
                obj.section_info.p_data = start_pos - self.header.p_buffer_data
                obj.write(file)
                obj.section_info.data_size = file.tell() - start_pos

        buffers_size = file.tell() - self.header.p_buffer_data

        # Write the section infos again with all the correct data
        file.seek(self.header.p_section_infos)
        for obj in self.objects:
            obj.section_info.write(file)

        # We write the header again with all the correct data
        file.seek(0)
        self.header.write(file, buffers_size)

    def seek_to_data(self, file, rw_object):
        if self.header is not None and rw_object is not None and rw_object.section_info is not None:
            if rw_object.section_info.type_code == BaseResource.type_code:
                file.seek(self.header.p_buffer_data + rw_object.section_info.p_data)
            else:
                file.seek(rw_object.section_info.p_data)


class RWSectionInfo:
    def __init__(self, render_ware: RenderWare4, p_data=0, field_04=0, data_size=0, alignment=0, type_code_index=0,
                 type_code=0):
        self.render_ware = render_ware
        self.p_data = p_data  # 00h
        self.field_04 = field_04
        self.data_size = data_size  # 08h
        self.alignment = alignment  # 0Ch
        self.type_code_index = type_code_index  # 10h
        self.type_code = type_code  # 14h

    def read(self, file: FileReader):
        self.p_data = file.read_int()
        self.field_04 = file.read_int()
        self.data_size = file.read_int()
        self.alignment = file.read_int()
        self.type_code_index = file.read_int()
        self.type_code = file.read_int()

    def write(self, file: FileWriter):
        file.write_int(self.p_data)
        file.write_int(self.field_04)
        file.write_int(self.data_size)
        file.write_int(self.alignment)
        file.write_int(self.type_code_index)
        file.write_int(self.type_code)


class RWObject:
    type_code = 0
    alignment = 4

    def __init__(self, render_ware: RenderWare4):
        self.render_ware = render_ware
        self.section_info = None

    def read(self, file: FileReader):
        pass

    def write(self, file: FileWriter):
        pass


class SectionManifest(RWObject):
    type_code = 0x10004

    def __init__(self, render_ware: RenderWare4, field_0=4, field_4=12):
        super().__init__(render_ware)
        # all offsets are relative to the beginning of this section
        self.field_0 = field_0
        self.field_4 = field_4
        self.p_section_types = 0
        self.p_section_external_arenas = 0
        self.p_section_sub_references = 0
        self.p_section_atoms = 0

    def read(self, file: FileReader):
        self.field_0 = file.read_int()
        self.field_4 = file.read_int()
        self.p_section_types = file.read_int()
        self.p_section_external_arenas = file.read_int()
        self.p_section_sub_references = file.read_int()
        self.p_section_atoms = file.read_int()

    def write(self, file: FileWriter):
        file.write_int(self.field_0)
        file.write_int(self.field_4)
        file.write_int(self.p_section_types)
        file.write_int(self.p_section_external_arenas)
        file.write_int(self.p_section_sub_references)
        file.write_int(self.p_section_atoms)


class SectionTypes(RWObject):
    type_code = 0x10005

    def __init__(self, render_ware: RenderWare4, field_4=12):
        super().__init__(render_ware)
        self.field_4 = field_4
        self.type_codes = []

    def read(self, file: FileReader):
        count = file.read_int()
        self.field_4 = file.read_int()

        for i in range(count):
            self.type_codes.append(file.read_int())

    def write(self, file: FileWriter):
        file.write_int(len(self.type_codes))
        file.write_int(self.field_4)

        for x in self.type_codes:
            file.write_int(x)


class SectionExternalArenas(RWObject):
    type_code = 0x10006

    def __init__(self, render_ware: RenderWare4,
                 field_0=3, field_4=0x18, field_8=1, field_c=0xffb00000,
                 field_10=1, field_14=0, field_18=0, field_1c=0):
        super().__init__(render_ware)
        self.field_0 = field_0
        self.field_4 = field_4
        self.field_8 = field_8
        self.field_c = field_c
        self.field_10 = field_10
        self.field_14 = field_14
        self.field_18 = field_18
        self.field_1c = field_1c

    def read(self, file: FileReader):
        self.field_0 = file.read_int()
        self.field_4 = file.read_int()
        self.field_8 = file.read_int()
        self.field_c = file.read_int()
        self.field_10 = file.read_int()
        self.field_14 = file.read_int()
        self.field_18 = file.read_int()
        self.field_1c = file.read_int()

    def write(self, file: FileWriter):
        file.write_int(self.field_0)
        file.write_int(self.field_4)
        file.write_int(self.field_8)
        file.write_uint(self.field_c)
        file.write_int(self.field_10)
        file.write_int(self.field_14)
        file.write_int(self.field_18)
        file.write_int(self.field_1c)


class SectionSubReferences(RWObject):
    type_code = 0x10007

    def __init__(self, render_ware: RenderWare4, sub_references=None, field_4=0, field_8=0, p_sub_reference_offsets=0):
        super().__init__(render_ware)
        self.sub_references = sub_references
        if self.sub_references is None:
            self.sub_references = []

        self.field_4 = field_4
        self.field_8 = field_8
        self.p_sub_reference_offsets = p_sub_reference_offsets

    def read(self, file: FileReader):
        count = file.read_int()
        self.field_4 = file.read_int()
        self.field_8 = file.read_int()

        # this is the end of the offsets
        file.read_int()
        self.p_sub_reference_offsets = file.read_int()

        # the count again
        file.read_int()

        previous_position = file.tell()
        file.seek(self.p_sub_reference_offsets)

        for i in range(count):
            reference = SubReference(self.render_ware.get_object(file.read_int()), file.read_int())
            self.sub_references.append(reference)

        file.seek(previous_position)

    def write(self, file: FileWriter):
        file.write_int(len(self.sub_references))
        file.write_int(self.field_4)
        file.write_int(self.field_8)
        file.write_int(self.p_sub_reference_offsets + len(self.sub_references) * 8)
        file.write_int(self.p_sub_reference_offsets)
        file.write_int(len(self.sub_references))

        if self.p_sub_reference_offsets != 0:
            previous_position = file.tell()
            file.seek(self.p_sub_reference_offsets)

            for reference in self.sub_references:
                file.write_int(self.render_ware.get_index(reference.rw_object))
                file.write_int(reference.offset)

            file.seek(previous_position)


class SectionAtoms(RWObject):
    type_code = 0x10008

    def __init__(self, render_ware: RenderWare4, field_0=0, field_4=0):
        super().__init__(render_ware)
        self.field_0 = field_0
        self.field_4 = field_4

    def read(self, file: FileReader):
        self.field_0 = file.read_int()
        self.field_4 = file.read_int()

    def write(self, file: FileWriter):
        file.write_int(self.field_0)
        file.write_int(self.field_4)


class BaseResource(RWObject):
    type_code = 0x10030
    alignment = 4

    def __init__(self, render_ware: RenderWare4, data=None):
        super().__init__(render_ware)
        self.data = data

    def read(self, file: FileReader):
        self.data = file.read(self.section_info.data_size)

    def write(self, file: FileWriter):
        file.write(self.data)


class Raster(RWObject):
    type_code = 0x20003
    alignment = 4

    def __init__(self, render_ware: RenderWare4):
        super().__init__(render_ware)
        self.texture_format = 0
        self.texture_flags = 8  # 0x200 -> D3DUSAGE_AUTOGENMIPMAP, 0x10 -> D3DUSAGE_DYNAMIC
        self.volume_depth = 0  # used in volume textures
        self.dx_base_texture = 0  # IDirect3DBaseTexture9*, unused in the file
        self.width = 0
        self.height = 0
        self.field_10 = 8  # usually 8
        self.mipmap_levels = 0
        self.field_14 = 0
        self.field_18 = 0
        self.texture_data = None

    def read(self, file: FileReader):
        self.texture_format = file.read_int(endian='>')  # 00h
        self.texture_flags = file.read_short()  # 04h
        self.volume_depth = file.read_ushort()  # 06h
        self.dx_base_texture = file.read_int()  # 08h
        self.width = file.read_ushort()  # 0Ch
        self.height = file.read_ushort()  # 0Eh
        self.field_10 = file.read_byte()  # 10h
        self.mipmap_levels = file.read_byte()  # 11h
        file.read_short()
        self.field_14 = file.read_int()  # 14h
        self.field_18 = file.read_int()  # 18h
        self.texture_data = self.render_ware.get_object(file.read_int())  # 1Ch

    def write(self, file: FileWriter):
        file.write_int(self.texture_format, endian='>')
        file.write_short(self.texture_flags)
        file.write_ushort(self.volume_depth)
        file.write_int(self.dx_base_texture)
        file.write_ushort(self.width)
        file.write_ushort(self.height)
        file.write_byte(self.field_10)
        file.write_byte(self.mipmap_levels)
        file.write_short(0)  # padding
        file.write_int(self.field_14)
        file.write_int(self.field_18)
        file.write_int(self.render_ware.get_index(self.texture_data))

    def from_dds(self, dds_texture):
        self.width = dds_texture.dwWidth
        self.height = dds_texture.dwHeight
        self.volume_depth = dds_texture.dwDepth
        self.mipmap_levels = dds_texture.dwMipMapCount
        self.texture_format = dds_texture.ddsPixelFormat.dwFourCC


class VertexDescription(RWObject):
    type_code = 0x20004
    alignment = 4

    def __init__(self, render_ware: RenderWare4):
        super().__init__(render_ware)
        self.field_0 = 0
        self.field_4 = 0
        self.dx_vertex_declaration = 0  # IDirect3DVertexDeclaration9*, not used in file
        self.vertex_elements = []
        # I assume vertexSize is a byte and there is another byte before; otherwise, the value would be big-endian
        self.field_0E = 0
        self.vertex_size = 0
        self.field_10 = 0
        self.field_14 = 0
        self.vertex_class = None

    def read(self, file: FileReader):
        self.field_0 = file.read_int()
        self.field_4 = file.read_int()
        self.dx_vertex_declaration = file.read_int()

        element_count = file.read_short()
        self.field_0E = file.read_byte()
        self.vertex_size = file.read_byte()
        file.read_int()  # element flags
        self.field_14 = file.read_int()

        for i in range(0, element_count):
            element = rw4_enums.VertexElement()
            element.read(file)
            self.vertex_elements.append(element)

        self.vertex_class = rw4_enums.create_rw_vertex_class(self.vertex_elements)

    def write(self, file: FileWriter):
        file.write_int(self.field_0)
        file.write_int(self.field_4)
        file.write_int(self.dx_vertex_declaration)
        file.write_short(len(self.vertex_elements))
        file.write_byte(self.field_0E)
        file.write_byte(self.vertex_size)

        element_flags = 0
        for element in self.vertex_elements:
            element_flags |= 1 << element.rw_decl

        file.write_int(element_flags)
        file.write_int(self.field_14)

        for element in self.vertex_elements:
            element.write(file)

    def read_vertex(self, file: FileReader):
        v = rw4_enums.read_rw_vertex(self.vertex_elements, self.vertex_class, file)
        return v


class VertexBuffer(RWObject):
    type_code = 0x20005
    alignment = 4

    def __init__(self,
                 render_ware, vertex_description=None, base_vertex_index=0,
                 vertex_count=0, field_10=0, vertex_size=0, vertex_data=None):
        super().__init__(render_ware)
        self.vertex_description = vertex_description
        self.field_4 = 0
        self.base_vertex_index = base_vertex_index
        self.vertex_count = vertex_count
        self.field_10 = field_10
        self.vertex_size = vertex_size
        self.vertex_data = vertex_data

    def read(self, file: FileReader):
        self.vertex_description = self.render_ware.get_object(file.read_int())
        self.field_4 = file.read_int()
        self.base_vertex_index = file.read_int()  # 08h
        self.vertex_count = file.read_int()  # 0Ch
        self.field_10 = file.read_int()  # 10h
        self.vertex_size = file.read_int()  # 14h
        self.vertex_data = self.render_ware.get_object(file.read_int())  # 18h

    def write(self, file: FileWriter):
        file.write_int(self.render_ware.get_index(self.vertex_description))
        file.write_int(self.field_4)
        file.write_int(self.base_vertex_index)
        file.write_int(self.vertex_count)
        file.write_int(self.field_10)
        file.write_int(self.vertex_size)
        file.write_int(self.render_ware.get_index(self.vertex_data))

    def process_data(self, file: FileReader):
        if self.vertex_description is None:
            raise ModelError("Cannot process vertices without a vertex description.", self)
        elif self.vertex_data is None:
            raise ModelError("Cannot process vertices without a data buffer.", self)

        vertex_stream = ArrayFileReader(self.vertex_data.data)

        vertices = []
        for i in range(self.vertex_count):
            vertices.append(self.vertex_description.read_vertex(vertex_stream))

        return vertices

    def has_element(self, rw_decl) -> bool:
        for e in self.vertex_description.vertex_elements:
            if e.rw_decl == rw_decl:
                return True
        return False


class IndexBuffer(RWObject):
    type_code = 0x20007
    alignment = 4

    def __init__(self, render_ware: RenderWare4,
                 start_index=0, primitive_count=0, usage=8, index_format=101, primitive_type=4, index_data=None):
        super().__init__(render_ware)
        self.dx_index_buffer = 0  # IDirect3DIndexBuffer9*, not used in file
        self.start_index = start_index
        self.primitive_count = primitive_count
        self.usage = usage  # usually D3DUSAGE_WRITEONLY
        self.format = index_format  # D3DFMT_INDEX16 or D3DFMT_INDEX32, apparently Spore only supports the first one
        self.primitive_type = primitive_type  # usually D3DPRIMITIVETYPE.D3DPT_TRIANGLELIST
        self.index_data = index_data

    def read(self, file):
        self.dx_index_buffer = file.read_int()
        # this is added to every index
        self.start_index = file.read_int()
        self.primitive_count = file.read_int()
        self.usage = file.read_int()
        self.format = file.read_int()
        self.primitive_type = file.read_int()
        self.index_data = self.render_ware.get_object(file.read_int())

    def write(self, file):
        file.write_int(self.dx_index_buffer)
        file.write_int(self.start_index)
        file.write_int(self.primitive_count)
        file.write_int(self.usage)
        file.write_int(self.format)
        file.write_int(self.primitive_type)
        file.write_int(self.render_ware.get_index(self.index_data))

    def process_data(self, file: FileReader):
        if self.index_data is None:
            raise ModelError("Cannot process indices without a data buffer.", self)

        indices = []
        index_stream = ArrayFileReader(self.index_data.data)

        fmt = '<H' if self.format == rw4_enums.D3DFMT_INDEX16 else '<I'
        for i in range(self.primitive_count):
            indices.append(index_stream.unpack(fmt)[0])

        return indices


class SkinMatrixBuffer(RWObject):
    type_code = 0x7000f
    alignment = 16

    def __init__(self, render_ware: RenderWare4):
        super().__init__(render_ware)
        self.p_matrix_data = 0  # in file, offset, in the game a pointer to it
        self.data = []
        self.field_8 = 0
        self.field_C = 0

    def read(self, file: FileReader):
        self.p_matrix_data = file.read_int()
        count = file.read_int()
        self.field_8 = file.read_int()
        self.field_C = file.read_int()

        for i in range(0, count):
            matrix = RWMatrix(3, 4)
            matrix.read(file)
            self.data.append(matrix)

    def write(self, file: FileWriter):
        self.p_matrix_data = file.tell() + 16
        file.write_int(self.p_matrix_data)
        file.write_int(len(self.data))
        file.write_int(self.field_8)
        file.write_int(self.field_C)

        for matrix in self.data:
            matrix.write(file)


class AnimationSkin(RWObject):
    type_code = 0x70003
    alignment = 16

    class BonePose:
        def __init__(self):
            self.abs_bind_pose = RWMatrix(3, 3)
            self.inv_pose_translation = [0, 0, 0]

        def read(self, file):
            for i in range(3):
                for j in range(3):
                    self.abs_bind_pose[i][j] = file.read_float()

                file.read_int()  # 0

            for i in range(3):
                self.inv_pose_translation[i] = file.read_float()

            file.read_int()  # 0

            self.matrix = self.abs_bind_pose
            self.translation = self.inv_pose_translation

        def write(self, file):
            for i in range(3):
                for j in range(3):
                    file.write_float(self.abs_bind_pose[i][j])

                file.write_int(0)

            for i in range(3):
                file.write_float(self.inv_pose_translation[i])

            file.write_int(0)

    def __init__(self, render_ware: RenderWare4):
        super().__init__(render_ware)
        self.p_matrix_data = 0  # in file, offset, in the game a pointer to it
        self.data = []
        self.field_8 = 0
        self.field_C = 0

    def read(self, file: FileReader):
        self.p_matrix_data = file.read_int()
        count = file.read_int()
        self.field_8 = file.read_int()
        self.field_C = file.read_int()

        for i in range(0, count):
            pose = AnimationSkin.BonePose()
            pose.read(file)
            self.data.append(pose)

    def write(self, file: FileWriter):
        self.p_matrix_data = file.tell() + 16
        file.write_int(self.p_matrix_data)
        file.write_int(len(self.data))
        file.write_int(self.field_8)
        file.write_int(self.field_C)

        for pose in self.data:
            pose.write(file)


class Mesh(RWObject):
    type_code = 0x20009
    alignment = 4

    def __init__(self, render_ware: RenderWare4, field_0=0, primitive_type=0, index_buffer=None, triangle_count=0,
                 first_index=0, primitive_count=0, first_vertex=0, vertex_count=0):
        super().__init__(render_ware)
        self.field_0 = field_0
        self.primitive_type = primitive_type
        self.index_buffer = index_buffer
        self.triangle_count = triangle_count
        self.first_index = first_index
        self.primitive_count = primitive_count
        self.first_vertex = first_vertex
        self.vertex_count = vertex_count
        self.vertex_buffers = []

    def read(self, file: FileReader):
        self.field_0 = file.read_int()
        self.primitive_type = file.read_int()
        self.index_buffer = self.render_ware.get_object(file.read_int())
        self.triangle_count = file.read_int()
        vertex_buffers_count = file.read_int()
        self.first_index = file.read_int()
        self.primitive_count = file.read_int()
        self.first_vertex = file.read_int()
        self.vertex_count = file.read_int()

        for i in range(0, vertex_buffers_count):
            self.vertex_buffers.append(self.render_ware.get_object(file.read_int()))

    def write(self, file: FileWriter):
        file.write_int(self.field_0)
        file.write_int(self.primitive_type)
        file.write_int(self.render_ware.get_index(self.index_buffer))
        file.write_int(self.triangle_count)
        file.write_int(len(self.vertex_buffers))
        file.write_int(self.first_index)
        file.write_int(self.primitive_count)
        file.write_int(self.first_vertex)
        file.write_int(self.vertex_count)

        for buffer in self.vertex_buffers:
            file.write_int(self.render_ware.get_index(buffer))


class MeshCompiledStateLink(RWObject):
    type_code = 0x2001a
    alignment = 4

    def __init__(self, render_ware: RenderWare4, mesh=None):
        super().__init__(render_ware)
        self.mesh = mesh
        self.compiled_states = []

    def read(self, file: FileReader):
        self.mesh = self.render_ware.get_object(file.read_int())
        count = file.read_int()

        for i in range(0, count):
            self.compiled_states.append(self.render_ware.get_object(file.read_int()))

    def write(self, file: FileWriter):
        file.write_int(self.render_ware.get_index(self.mesh))
        file.write_int(len(self.compiled_states))

        for compiledState in self.compiled_states:
            file.write_int(self.render_ware.get_index(compiledState))


class CompiledState(RWObject):
    type_code = 0x2000b
    alignment = 16

    def __init__(self, render_ware: RenderWare4):
        super().__init__(render_ware)
        self.render_ware = render_ware
        self.data = bytearray()

    def read(self, file: FileReader):
        size = file.read_int()
        self.data = file.read(size - 4)

    def write(self, file: FileWriter):
        file.write_int(len(self.data) + 4)
        file.write(self.data)


class SkinsInK(RWObject):
    type_code = 0x7000c
    alignment = 4

    def __init__(self, render_ware: RenderWare4, field_0=None, skin_matrix_buffer=None, skeleton=None, animation_skin=None):
        super().__init__(render_ware)
        self.field_0 = field_0
        self.field_4 = 0  # this is a pointer to a function but it always gets replaced by Spore
        self.skin_matrix_buffer = skin_matrix_buffer
        self.skeleton = skeleton
        self.animation_skin = animation_skin

    def read(self, file: FileReader):
        self.field_0 = self.render_ware.get_object(file.read_int())
        self.field_4 = file.read_int()
        self.skin_matrix_buffer = self.render_ware.get_object(file.read_int())
        self.skeleton = self.render_ware.get_object(file.read_int())
        self.animation_skin = self.render_ware.get_object(file.read_int())

    def write(self, file: FileWriter):
        file.write_int(self.render_ware.get_index(self.field_0, INDEX_NO_OBJECT))
        file.write_int(self.field_4)
        file.write_int(self.render_ware.get_index(self.skin_matrix_buffer))
        file.write_int(self.render_ware.get_index(self.skeleton))
        file.write_int(self.render_ware.get_index(self.animation_skin))


class SkeletonBone:
    TYPE_ROOT = 0
    TYPE_LEAF = 1
    TYPE_BRANCH = 2
    TYPE_BRANCH_LEAF = 3

    def __init__(self, name, flags=0, parent=None):
        self.name = name
        self.flags = flags
        self.parent = parent
        self.parent_index = -1
        self.matrix = None
        self.translation = None


class Skeleton(RWObject):
    type_code = 0x70002
    alignment = 4

    def __init__(self, render_ware: RenderWare4, skeleton_id=0):
        super().__init__(render_ware)
        self.bones = []
        self.skeleton_id = skeleton_id

    def read(self, file: FileReader):

        p_bone_flags = file.read_int()
        p_bone_parents = file.read_int()
        p_bone_names = file.read_int()
        bone_count = file.read_int()
        self.skeleton_id = file.read_uint()
        file.read_int()  # boneCount again?

        for i in range(bone_count):
            self.bones.append(SkeletonBone(-1))

        file.seek(p_bone_names)
        for bone in self.bones:
            bone.name = file.read_uint()

        file.seek(p_bone_flags)
        for bone in self.bones:
            bone.flags = file.read_int()

        file.seek(p_bone_parents)
        for bone in self.bones:
            index = file.read_int()
            if index != -1:
                bone.parent = self.bones[index]
                bone.parent_index = index

    def write(self, file: FileWriter):
        base_pos = file.tell()
        # we will calculate the offsets
        file.write_int(base_pos + 24 + len(self.bones) * 4)  # pBoneFlags
        file.write_int(base_pos + 24 + len(self.bones) * 8)  # pBoneParents
        file.write_int(base_pos + 24)  # pBoneNames
        file.write_int(len(self.bones))
        file.write_uint(self.skeleton_id)
        file.write_int(len(self.bones))

        for bone in self.bones:
            file.write_uint(bone.name)

        for bone in self.bones:
            file.write_int(bone.flags)

        for bone in self.bones:
            if bone.parent is None:
                file.write_int(-1)
            else:
                file.write_int(self.bones.index(bone.parent))


class BoundingBox(RWObject):
    type_code = 0x80005
    alignment = 16

    def __init__(self, render_ware: RenderWare4, bound_box=None):
        super().__init__(render_ware)
        self.bound_box = bound_box
        self.field_0C = 0
        self.field_1C = 0

    def read(self, file: FileReader):
        if self.bound_box is None:
            self.bound_box = []

        self.bound_box.append([file.read_float(), file.read_float(), file.read_float()])
        self.field_0C = file.read_int()

        self.bound_box.append([file.read_float(), file.read_float(), file.read_float()])
        self.field_1C = file.read_int()

    def write(self, file: FileWriter):
        file.write_float(self.bound_box[0][0])
        file.write_float(self.bound_box[0][1])
        file.write_float(self.bound_box[0][2])
        file.write_int(self.field_0C)
        file.write_float(self.bound_box[1][0])
        file.write_float(self.bound_box[1][1])
        file.write_float(self.bound_box[1][2])
        file.write_int(self.field_1C)


class MorphHandle(RWObject):
    type_code = 0xff0000
    alignment = 4

    def __init__(self, render_ware: RenderWare4, handle_id=0, default_time=0.0, animation=None):
        super().__init__(render_ware)
        self.handle_id = handle_id
        self.field_4 = 0
        self.start_pos = [0.0, 0.0, 0.0]
        self.end_pos = [0.0, 0.0, 0.0]
        self.default_time = default_time
        self.animation = animation

    def read(self, file):
        self.handle_id = file.read_uint()
        self.field_4 = file.read_uint()
        self.start_pos[0] = file.read_double()
        self.start_pos[1] = file.read_double()
        self.start_pos[2] = file.read_double()
        self.end_pos[0] = file.read_double()
        self.end_pos[1] = file.read_double()
        self.end_pos[2] = file.read_double()
        self.default_time = file.read_float()
        self.animation = self.render_ware.get_object(file.read_int())

    def write(self, file):
        file.write_uint(self.handle_id)
        file.write_uint(self.field_4)
        file.write_double(self.start_pos[0])
        file.write_double(self.start_pos[1])
        file.write_double(self.start_pos[2])
        file.write_double(self.end_pos[0])
        file.write_double(self.end_pos[1])
        file.write_double(self.end_pos[2])
        file.write_float(self.default_time)
        file.write_int(self.render_ware.get_index(self.animation))


class TriangleKDTreeProcedural(RWObject):
    type_code = 0x80003
    alignment = 16

    def __init__(self, render_ware: RenderWare4):
        super().__init__(render_ware)
        self.bound_box = None
        self.triangles = []
        self.vertices = []
        self.field_20 = 0x00D59208
        self.field_24 = 8
        # 28h: triangle_count
        self.field_2C = 0
        # 30h: vertex_count

        self.triangle_unknowns = []
        self.bound_box_2 = None
        self.unknown_data = []

    def read(self, file: FileReader):
        if self.bound_box is None:
            self.bound_box = BoundingBox(self.render_ware)

        if self.bound_box_2 is None:
            self.bound_box_2 = BoundingBox(self.render_ware)

        self.bound_box.read(file)

        self.field_20 = file.read_int()
        self.field_24 = file.read_int()

        triangle_count = file.read_int()
        self.field_2C = file.read_int()
        vertex_count = file.read_int()

        p_triangles = file.read_int()
        p_vertex_offsets = file.read_int()
        p4 = file.read_int()
        p3 = file.read_int()

        # Read vertices
        file.seek(p_vertex_offsets)
        for i in range(vertex_count):
            self.vertices.append((file.read_float(), file.read_float(), file.read_float()))
            file.read_int()

        # Read triangles
        file.seek(p_triangles)
        for i in range(triangle_count):
            # it has one integer more, which is usually 0 (?)
            self.triangles.append((file.read_int(), file.read_int(), file.read_int(), file.read_int()))

        file.seek(p3)
        x = 0
        for i in range(triangle_count):
            if i & 7 == 0:
                x = file.read_int()

            self.triangle_unknowns.append((x >> ((i & 7) * 4)) & 0xf)

        file.seek(p4)
        file.read_int()  # self.vertexPos - 8 * 4
        unknown_count = file.read_int()
        file.read_int()  # self.triCount
        file.read_int()  # 0
        self.bound_box_2.read(file)
        for i in range(unknown_count):
            self.unknown_data.append(
                (file.read_int(), file.read_int(), file.read_int(), file.read_int(), file.read_int(), file.read_int(),
                 file.read_float(), file.read_float())
            )

    def write(self, file: FileWriter):
        self.bound_box.write(file)

        file.write_int(self.field_20)
        file.write_int(self.field_24)
        file.write_int(len(self.triangles))
        file.write_int(self.field_2C)
        file.write_int(len(self.vertices))

        pointers_offset = file.tell()

        p_triangles = 0
        p_vertices = 0
        p4 = 0
        p3 = 0

        file.write_int(p_triangles)
        file.write_int(p_vertices)
        file.write_int(p4)
        file.write_int(p3)

        # Write vertices
        pos = file.tell()
        p_vertices = (pos + 15) & ~15

        file.write(bytearray(p_vertices - pos))

        for vertex in self.vertices:
            file.write_float(vertex[0])
            file.write_float(vertex[1])
            file.write_float(vertex[2])
            file.write_int(0)

        # Write triangles
        p_triangles = file.tell()
        for triangle in self.triangles:
            file.write_int(triangle[0])
            file.write_int(triangle[1])
            file.write_int(triangle[2])
            file.write_int(triangle[3])

        p3 = file.tell()

        count = len(self.triangle_unknowns) // 8
        packs = []
        for i in range(count):
            packs.append(self.triangle_unknowns[i * 8] + (self.triangle_unknowns[i * 8 + 1] << 4) +
                         (self.triangle_unknowns[i * 8 + 2] << 8) + (self.triangle_unknowns[i * 8 + 3] << 12) +
                         (self.triangle_unknowns[i * 8 + 4] << 16) + (self.triangle_unknowns[i * 8 + 5] << 20) +
                         (self.triangle_unknowns[i * 8 + 6] << 24) + (self.triangle_unknowns[i * 8 + 7] << 28))

        tri_pack = len(self.triangle_unknowns) % 8
        if tri_pack > 0:
            pack = 0
            for i in range(tri_pack):
                pack += self.triangle_unknowns[count * 8 + i] << (i * 4)
            for i in range(8 - tri_pack):
                pack += 15 << ((i + tri_pack) * 4)
            packs.append(pack)

        for p in packs:
            file.write(struct.pack('I', p))

        pos = file.tell()
        p4 = (pos + 15) & ~15
        file.write(bytearray(p4 - pos))

        file.write_int(p_vertices - 8 * 4)
        file.write_int(len(self.unknown_data))
        file.write_int(len(self.triangles))
        file.write_int(0)

        self.bound_box_2.write(file)

        for i in range(len(self.unknown_data)):
            file.write_int(self.unknown_data[i][0])
            file.write_int(self.unknown_data[i][1])
            file.write_int(self.unknown_data[i][2])
            file.write_int(self.unknown_data[i][3])
            file.write_int(self.unknown_data[i][4])
            file.write_int(self.unknown_data[i][5])
            file.write_float(self.unknown_data[i][6])
            file.write_float(self.unknown_data[i][7])

        # Write the pointer offsets
        final_pos = file.tell()

        file.seek(pointers_offset)
        file.write_int(p_triangles)
        file.write_int(p_vertices)
        file.write_int(p4)
        file.write_int(p3)

        file.seek(final_pos)


class Animations(RWObject):
    type_code = 0xff0001
    alignment = 4

    def __init__(self, render_ware: RenderWare4):
        super().__init__(render_ware)
        self.animations = {}

    def read(self, file: FileReader):
        file.read_int()  # index to subreference to this object
        count = file.read_int()
        for i in range(count):
            name = file.read_uint()
            self.animations[name] = self.render_ware.get_object(file.read_int())

    def write(self, file: FileWriter):
        file.write_int(self.render_ware.get_index(self, INDEX_SUB_REFERENCE))
        file.write_int(len(self.animations))

        for item in self.animations.items():
            file.write_uint(item[0])
            file.write_int(self.render_ware.get_index(item[1]))

    def add(self, name_id, keyframe_anim):
        self.animations[name_id] = keyframe_anim


class Keyframe:
    components = 0
    size = 0

    def __init__(self):
        self.time = 0.0

    def read(self, file):
        pass

    def write(self, file):
        pass


class LocRotScaleKeyframe(Keyframe):
    components = 0x601
    size = 48

    def __init__(self):
        super().__init__()
        self.loc = [0.0, 0.0, 0.0]
        self.rot = [0.0, 0.0, 0.0, 1.0]
        self.scale = [1.0, 1.0, 1.0]

    def read(self, file: FileReader):
        for i in range(4):
            self.rot[i] = file.read_float()

        for i in range(3):
            self.loc[i] = file.read_float()

        for i in range(3):
            self.scale[i] = file.read_float()

        file.read_int()
        self.time = file.read_float()

    def write(self, file: FileWriter):
        for i in range(4):
            file.write_float(self.rot[i])

        for i in range(3):
            file.write_float(self.loc[i])

        for i in range(3):
            file.write_float(self.scale[i])

        file.write_int(0)
        file.write_float(self.time)

    def set_scale(self, scale):
        self.scale = scale

    def set_rotation(self, quaternion):
        self.rot[0] = quaternion.x
        self.rot[1] = quaternion.y
        self.rot[2] = quaternion.z
        self.rot[3] = quaternion.w

    def set_translation(self, offset):
        self.loc = offset


class LocRotKeyframe(Keyframe):
    components = 0x101
    size = 36

    def __init__(self):
        super().__init__()
        self.loc = [0.0, 0.0, 0.0]
        self.rot = [0.0, 0.0, 0.0, 1.0]

    def read(self, file: FileReader):
        for i in range(4):
            self.rot[i] = file.read_float()

        for i in range(3):
            self.loc[i] = file.read_float()

        self.time = file.read_float()

    def write(self, file: FileWriter):
        for i in range(4):
            file.write_float(self.rot[i])

        for i in range(3):
            file.write_float(self.loc[i])

        file.write_float(self.time)

    def set_rotation(self, quaternion):
        self.rot[0] = quaternion.x
        self.rot[1] = quaternion.y
        self.rot[2] = quaternion.z
        self.rot[3] = quaternion.w

    def set_translation(self, offset):
        self.loc = offset


class BlendFactorKeyframe(Keyframe):
    components = 0x100
    size = 8

    def __init__(self):
        super().__init__()
        self.factor = 0.0

    def read(self, file: FileReader):
        self.factor = file.read_float()
        self.time = file.read_float()

    def write(self, file: FileWriter):
        file.write_float(self.factor)
        file.write_float(self.time)


class AnimationChannel:
    def __init__(self, keyframe_class=None):
        self.channel_id = 0
        self.keyframe_class = keyframe_class
        self.keyframes = []

    def set_keyframe_class(self, pose_components):
        for cls in Keyframe.__subclasses__():
            if cls.components == pose_components:
                self.keyframe_class = cls
                break

    def new_keyframe(self, time):
        keyframe = self.keyframe_class()
        keyframe.time = time
        self.keyframes.append(keyframe)
        return keyframe

    def read_keyframes(self, file: FileReader, count: int, position: int):
        if self.keyframe_class is not None:
            file.seek(position)
            for i in range(count):
                keyframe = self.keyframe_class()
                keyframe.read(file)
                self.keyframes.append(keyframe)


class KeyframeAnim(RWObject):
    type_code = 0x70001
    alignment = 16

    frames_per_second = 24

    def __init__(self, render_ware: RenderWare4, skeleton_id=0, length=0.0):
        super().__init__(render_ware)
        self.skeleton_id = skeleton_id
        self.field_C = 0
        self.field_1C = 0
        self.length = length
        self.field_24 = 12
        self.flags = 0
        self.channels = []

    def read(self, file):
        base_pos = file.tell()

        p_channel_names = file.read_int()

        channel_count = file.read_int()
        self.skeleton_id = file.read_uint()
        self.field_C = file.read_int()

        p_channel_data = file.read_int()
        p_padding_end = file.read_int()  # probably not just padding

        file.read_int()  # channel_count again
        self.field_1C = file.read_int()
        self.length = file.read_float()
        self.field_24 = file.read_int()
        self.flags = file.read_int()

        p_channel_info = file.read_int()

        for i in range(channel_count):
            self.channels.append(AnimationChannel())

        file.seek(p_channel_names)
        for channel in self.channels:
            channel.channel_id = file.read_uint()

        channel_positions = []
        channel_pose_sizes = []
        file.seek(p_channel_info)
        for channel in self.channels:
            channel_positions.append(file.read_int())
            channel_pose_sizes.append(file.read_int())

            channel.set_keyframe_class(file.read_int())

        # this approach works except for the last channel
        for i in range(channel_count - 1):
            keyframe_count = (channel_positions[i + 1] - channel_positions[i]) // channel_pose_sizes[i]

            self.channels[i].read_keyframes(file, keyframe_count, base_pos + channel_positions[i])

        # now do the last channel
        if self.channels[-1].keyframe_class is not None:
            file.seek(base_pos + channel_positions[-1])

            last_time = 0
            while True:
                keyframe = self.channels[-1].keyframe_class()
                keyframe.read(file)

                if keyframe.time < last_time:
                    break
                else:
                    last_time = keyframe.time
                    self.channels[-1].keyframes.append(keyframe)

    def write(self, file: FileWriter):

        def write_offset(dst_pos, offset):
            file.seek(dst_pos)
            file.write_int(offset)

        base_pos = file.tell()

        p_channel_names = 0
        p_channel_data = 0
        p_padding_end = 0
        p_channel_info = 0

        pp_channel_names = 0
        pp_channel_data = 0
        pp_padding_end = 0
        pp_channel_info = 0

        pp_channel_names = file.tell()
        file.write_int(p_channel_names)

        file.write_int(len(self.channels))
        file.write_uint(self.skeleton_id)
        file.write_int(self.field_C)

        pp_channel_data = file.tell()
        file.write_int(p_channel_data)

        pp_padding_end = file.tell()
        file.write_int(p_padding_end)

        file.write_int(len(self.channels))
        file.write_int(self.field_1C)
        file.write_float(self.length)
        file.write_int(self.field_24)
        file.write_int(self.flags)

        pp_channel_info = file.tell()
        file.write_int(p_channel_info)

        # Channel names
        p_channel_names = file.tell()
        for channel in self.channels:
            file.write_uint(channel.channel_id)

        # Channel info
        p_channel_info = file.tell()
        for channel in self.channels:
            file.write_int(0)  # channel data pos
            file.write_int(channel.keyframe_class.size)
            file.write_int(channel.keyframe_class.components)

        # Channel data
        channel_data_offsets = []
        p_channel_data = file.tell()

        for channel in self.channels:
            channel_data_offsets.append(file.tell() - base_pos)

            for keyframe in channel.keyframes:
                keyframe.write(file)

        # Padding
        if len(self.channels) > 0:
            padding = len(self.channels) * len(self.channels[0].keyframes) * 2 * self.channels[0].keyframe_class.size
        else:
            padding = 48

        file.write(bytearray(padding))
        p_padding_end = file.tell()

        # write all offsets
        final_position = file.tell()

        write_offset(pp_channel_names, p_channel_names)
        write_offset(pp_channel_data, p_channel_data)
        write_offset(pp_padding_end, p_padding_end)
        write_offset(pp_channel_info, p_channel_info)

        for i in range(len(self.channels)):
            write_offset(p_channel_info + 12 * i, channel_data_offsets[i])

        file.seek(final_position)


class BlendShape(RWObject):
    type_code = 0xff0002
    alignment = 4

    def __init__(self, render_ware: RenderWare4, object_id=-1, shape_ids=None):
        super().__init__(render_ware)
        self.id = object_id
        self.shape_ids = [] if shape_ids is None else shape_ids

    def read(self, file: FileReader):
        file.read_int()  # gets replaced by code
        file.read_int()  # pointer to function, gets replaced

        file.read_int()  # index to subreference in this same object
        shape_count = file.read_int()
        file.read_int()  # index to subreference in this same object
        file.read_int()  # shape count again
        self.id = file.read_uint()

        # This is a buffer for the shape times, gets replaced by code
        file.skip_bytes(shape_count * 4)
        self.shape_ids.extend(file.unpack(f'<{shape_count}I'))

    def write(self, file: FileWriter):
        file.write_int(0)
        file.write_int(0)

        file.write_int(self.render_ware.add_sub_reference(self, 0x1C))
        file.write_int(len(self.shape_ids))
        file.write_int(self.render_ware.add_sub_reference(self, 0x1C + len(self.shape_ids) * 4))
        file.write_int(len(self.shape_ids))
        file.write_uint(self.id)

        file.pack(f'{len(self.shape_ids)}x')
        file.pack(f'{len(self.shape_ids)}I', *self.shape_ids)


class BlendShapeBuffer(RWObject):
    type_code = 0x200af
    alignment = 16

    INDEX_POSITION = 0
    INDEX_NORMAL = 1
    INDEX_TANGENT = 2
    INDEX_TEXCOORD = 3
    INDEX_BLENDINDICES = 9
    INDEX_BLENDWEIGHTS = 10

    def __init__(self, render_ware: RenderWare4, shape_count=0, vertex_count=0):
        super().__init__(render_ware)
        self.shape_count = shape_count
        self.vertex_count = vertex_count
        self.offsets = []
        self.data = None

    def read(self, file: FileReader):
        if file.read_int() != 1:
            raise IOError("Unsupported BlendShadeBuffer type")

        offsets = file.unpack('<11I')
        # The offsets must be relative to self.data
        for offset in offsets:
            self.offsets.append(-1 if offset == 0 else offset - 64)

        self.shape_count = file.read_int()
        self.vertex_count = file.read_int()
        # ??
        file.skip_bytes(8)

        self.data = file.read(self.section_info.data_size - 64)

    def write(self, file: FileWriter):
        file.write_int(1)
        for offset in self.offsets:
            file.write_uint(offset + 64)

        file.write_int(self.shape_count)
        file.write_int(self.vertex_count)
        file.write_int(0)
        file.write_int(self.shape_count)


class DDSTexture:
    DDSD_CAPS = 0x1
    DDSD_HEIGHT = 0x2
    DDSD_WIDTH = 0x4
    DDSD_PITCH = 0x8
    DDSD_PIXELFORMAT = 0x1000
    DDSD_MIPMAPCOUNT = 0x20000
    DDSD_LINEARSIZE = 0x80000
    DDSD_DEPTH = 0x800000

    DDSCAPS_COMPLEX = 0x8
    DDSCAPS_MIPMAP = 0x400000
    DDSCAPS_TEXTURE = 0x1000

    DDSCAPS2_CUBEMAP = 0x200
    DDSCAPS2_POSITIVEX = 0x400
    DDSCAPS2_NEGATIVEX = 0x800
    DDSCAPS2_POSITIVEY = 0x1000
    DDSCAPS2_NEGATIVEY = 0x2000
    DDSCAPS2_POSITIVEZ = 0x4000
    DDSCAPS2_NEGATIVEZ = 0x8000
    DDSCAPS2_VOLUME = 0x200000

    class DDSPixelFormat:
        DDPF_ALPHAPIXELS = 0x1
        DDPF_ALPHA = 0x2
        DDPF_FOURCC = 0x4
        DDPF_RGB = 0x40
        DDPF_YUV = 0x200
        DDPF_LUMINANCE = 0x200000

        def __init__(self):
            self.dwSize = 32
            self.dwFlags = 0
            self.dwFourCC = 0
            self.dwRGBBitCount = 32
            self.dwRBitMask = 0x00ff0000
            self.dwGBitMask = 0x0000ff00
            self.dwBBitMask = 0x000000ff
            self.dwABitMask = 0xff000000

        def read(self, file):
            self.dwSize = file.read_int()
            self.dwFlags = file.read_int()
            self.dwFourCC = file.read_int(endian='>')
            self.dwRGBBitCount = file.read_int()
            self.dwRBitMask = file.read_int()
            self.dwGBitMask = file.read_int()
            self.dwBBitMask = file.read_int()
            self.dwABitMask = file.read_int()

    def __init__(self):
        self.dwSize = 124
        self.dwFlags = 0
        self.dwHeight = 0
        self.dwWidth = 0
        self.dwPitchOrLinearSize = 0
        self.dwDepth = 0
        self.dwMipMapCount = 0
        self.ddsPixelFormat = DDSTexture.DDSPixelFormat()
        self.dwCaps = 0
        self.dwCaps2 = 0
        self.dwCaps3 = 0
        self.dwCaps4 = 0

        self.data = None

        # these are required in every .dds file
        self.dwFlags |= DDSTexture.DDSD_CAPS
        self.dwFlags |= DDSTexture.DDSD_HEIGHT
        self.dwFlags |= DDSTexture.DDSD_WIDTH
        self.dwFlags |= DDSTexture.DDSD_PIXELFORMAT

        self.dwCaps |= DDSTexture.DDSCAPS_TEXTURE

    def read(self, file: FileReader, read_data=True):

        # magic, 0x44445320
        file.read_int()

        self.dwSize = file.read_int()
        self.dwFlags = file.read_int()
        self.dwHeight = file.read_int()
        self.dwWidth = file.read_int()
        self.dwPitchOrLinearSize = file.read_int()
        self.dwDepth = file.read_int()
        self.dwMipMapCount = file.read_int()

        # DWORD           dwReserved1[11];
        for i in range(11):
            file.read_int()

        self.ddsPixelFormat.read(file)

        self.dwCaps = file.read_int()
        self.dwCaps2 = file.read_int()
        self.dwCaps3 = file.read_int()
        self.dwCaps4 = file.read_int()

        # DWORD           dwReserved2;
        file.read_int()

        if read_data:
            if self.ddsPixelFormat.dwFourCC != rw4_enums.D3DFMT_DXT5:
                raise ModelError("Only DXT5 textures supported", self)

            # go to the end of the file to calculate size
            file.buffer.seek(0, 2)
            buffer_size = file.tell() - 128

            file.seek(128)

            self.data = file.read(buffer_size)
