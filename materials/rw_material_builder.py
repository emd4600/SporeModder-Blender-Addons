__author__ = 'Eric'

import struct
from collections import namedtuple, OrderedDict
from .. import rw4_enums
from .. import rw4_base
from ..file_io import ArrayFileWriter, FileReader


class RWTextureSlot:
    """
    This class represents one texture slot of a material. The slot has a slot inedx, a reference to the
    texture, and sampler/stage states.
    """
    def __init__(self, sampler_index=0, texture_raster=None, set_default_states=True):
        self.texture_stage_states = OrderedDict()
        self.sampler_states = OrderedDict()
        self.texture_raster = texture_raster
        self.sampler_index = sampler_index

        if set_default_states:
            if texture_raster is not None:
                self.texture_stage_states[rw4_enums.D3DTSS_COLOROP] = rw4_enums.D3DTOP_MODULATE
                self.texture_stage_states[rw4_enums.D3DTSS_COLORARG1] = rw4_enums.D3DTA_TEXTURE
                self.texture_stage_states[rw4_enums.D3DTSS_COLORARG2] = rw4_enums.D3DTA_DIFFUSE
                self.texture_stage_states[rw4_enums.D3DTSS_ALPHAOP] = rw4_enums.D3DTOP_MODULATE
                self.texture_stage_states[rw4_enums.D3DTSS_ALPHAARG1] = rw4_enums.D3DTA_TEXTURE
                self.texture_stage_states[rw4_enums.D3DTSS_ALPHAARG2] = rw4_enums.D3DTA_DIFFUSE
            else:
                self.texture_stage_states[rw4_enums.D3DTSS_COLOROP] = rw4_enums.D3DTOP_DISABLE
                self.texture_stage_states[rw4_enums.D3DTSS_ALPHAOP] = rw4_enums.D3DTOP_DISABLE

            self.sampler_states[rw4_enums.D3DSAMP_ADDRESSU] = rw4_enums.D3DTADDRESS_WRAP
            self.sampler_states[rw4_enums.D3DSAMP_ADDRESSV] = rw4_enums.D3DTADDRESS_WRAP
            self.sampler_states[rw4_enums.D3DSAMP_MAGFILTER] = rw4_enums.D3DTEXF_LINEAR
            self.sampler_states[rw4_enums.D3DSAMP_MINFILTER] = rw4_enums.D3DTEXF_LINEAR
            self.sampler_states[rw4_enums.D3DSAMP_MIPFILTER] = rw4_enums.D3DTEXF_POINT


ShaderData = namedtuple('ShaderData', ('index', 'offset', 'data'))

SHADER_DATA = {
    'skinWeights': 0x003,
    'skinBones': 0x004,
    'modelToClip': 0x006,
    'modelToCamera': 0x007,
    'modelToWorld': 0x008,
    'worldToClip': 0x00C,
    'cameraToWorld': 0x00D,
    'worldToCamera': 0x00E,
    'worldToClipTranspose': 0x00F,
    'cameraToWorldTranspose': 0x010,
    'worldToCameraTranspose': 0x011,
    'cameraToClip': 0x012,
    'lightPosModel': 0x014,
    'lightDirCamera': 0x19,
    'worldCameraPosition': 0x01F,
    'worldCameraDirection': 0x021,
    'materialColor': 0x022,
    'ambient': 0x023,
    'time': 0x027,
    'pulse': 0x028,
    'worldToModel': 0x02A,

    'objectTypeColor': 0x202,
    'frameInfo': 0x203,
    'screenInfo': 0x204,
    'mNoiseScale': 0x205,
    'customParams': 0x206,
    'geomToRTT': 0x20A,
    'geomToRTTViewTrans': 0x20B,
    'tintParams': 0x20C,
    'region': 0x20F,
    'materialParams': 0x210,
    'uvTweak': 0x211,
    'editorColors[]': 0x212,
    'editorColors': 0x213,
    'dirLightsWorld': 0x214,
    'dirLightsModel': 0x215,
    'sunDirAndCelStrength': 0x219,
    'shCoeffs': 0x21A,
    'cameraDisntace': 0x21B,
    'bakedPaint': 0x21C,
    'uvSubRect': 0x21E,
    'mousePosition': 0x21F,
    'expandAmount': 0x220,
    'cameraParams': 0x222,
    'shadowMapInfo': 0x223,
    'foggingCPU': 0x225,
    'patchLocation': 0x226,
    'clipToWorld': 0x228,
    'clipToCamera': 0x229,
    'identityColor': 0x22E,
    'pcaTexture': 0x22F,
    'rolloverRegion': 0x230,
    'renderDepth': 0x231,
    'terrainTint': 0x233,
    'utfWin': 0x234,
    'deadTerrainTint': 0x235,
    'cellStage': 0x236,
    'terrainBrushFilterKernel': 0x23C,
    'terraformValues': 0x23D,
    'worldToPatch': 0x23E,
    'terrainBrushCubeMatRot': 0x241,
    'terrainSynthParams': 0x242,
    'debugPSColor': 0x246,
    'gameInfo': 0x248,
    'ramp': 0x24A,
    'sunDir': 0x24B,
    'tramp': 0x24C,
    'terrainLighting': 0x24D,
    'beachColor': 0x250,
    'cliffColor': 0x251,
    'viewTransform': 0x252,
    'minWater': 0x255,
    'worldCameraNormal': 0x256,

    'terrainTransform': 0x301,
    'decalState': 0x304,
    'terrainState': 0x305,

    # There are up to 2048 indices, but apparently above 1024 they give trouble
    # The ModAPI doesn't support it anymore, but we keep it to detect old shaders
    'ModAPIShader': 0x3FF
}


class RWMaterialBuilder:
    """
    This class is used to generate a compiled state from a material configuration.
    """

    FLAG_SHADER_DATA = 0x8
    FLAG_MATERIAL_COLOR = 0x10
    FLAG_AMBIENT_COLOR = 0x20
    FLAG_VERTEX_DESCRIPTION = 0x100000
    FLAG_USE_BOOLEANS = 0x8000

    FLAG3_RENDER_STATES = 0x20000

    def __init__(self):
        self.material_color = None
        self.ambient_color = None
        self.texture_slots = []
        self.render_states = OrderedDict()
        self.shader_data = []
        self.vertex_description = None
        self.shader_id = 0
        self.primitive_type = 4
        # 17 booleans. If you don't want to use it, directly assign it to None
        self.unknown_booleans = []

    def get_shader_data(self, index):
        for sh_data in self.shader_data:
            if sh_data.index == index:
                return sh_data

        return None

    def add_shader_data(self, index, data, offset=0):
        self.shader_data.append(ShaderData(index=index, offset=offset, data=data))

    @staticmethod
    def write_state(stream, state, value):
        stream.extend(struct.pack('<II',
                                  state,  # state
                                  value  # value
                                  ))

    def write(self, render_ware, stream):

        flags1 = 0
        flags2 = 0
        flags3 = 0

        # always used? don't really know what it does
        flags1 |= 4
        flags2 |= 0x8000

        # always used? don't really know what it does
        flags1 |= 4
        flags2 |= 0x8000

        if self.material_color is not None:
            flags1 |= RWMaterialBuilder.FLAG_MATERIAL_COLOR

        if self.ambient_color is not None:
            flags1 |= RWMaterialBuilder.FLAG_AMBIENT_COLOR

        if self.unknown_booleans is not None:
            flags1 |= RWMaterialBuilder.FLAG_USE_BOOLEANS

        if len(self.shader_data) > 0:
            flags1 |= RWMaterialBuilder.FLAG_SHADER_DATA
            flags2 |= RWMaterialBuilder.FLAG_SHADER_DATA

        if self.vertex_description is not None:
            flags1 |= RWMaterialBuilder.FLAG_VERTEX_DESCRIPTION
            flags2 |= RWMaterialBuilder.FLAG_VERTEX_DESCRIPTION

        if len(self.render_states) > 0:
            flags3 |= RWMaterialBuilder.FLAG3_RENDER_STATES

        for slot in self.texture_slots:
            flags3 |= 1 << slot.sampler_index

        stream.extend(struct.pack('<IIIIIII',
                                  self.primitive_type,
                                  flags1,
                                  flags2,
                                  flags3,
                                  0,  # field_14, also sued as flags
                                  self.shader_id,
                                  0  # just padding
                                  ))

        if self.vertex_description is not None:
            vertex_description_stream = ArrayFileWriter()
            self.vertex_description.write(vertex_description_stream)

            stream.extend(vertex_description_stream.buffer)

        if len(self.shader_data) > 0:
            for constant in self.shader_data:
                stream.extend(struct.pack('<HHI',
                                          constant.index,
                                          constant.offset,
                                          len(constant.data)
                                          ))
                if constant.offset > 0:
                    stream.extend(bytearray(constant.offset))
                stream.extend(constant.data)

            stream.extend(bytearray(8))

        if self.material_color is not None:
            stream.extend(struct.pack('<ffff',
                                      self.material_color[0],
                                      self.material_color[1],
                                      self.material_color[2],
                                      self.material_color[3]))

        if self.ambient_color is not None:
            stream.extend(struct.pack('<fff',
                                      self.ambient_color[0],
                                      self.ambient_color[1],
                                      self.ambient_color[2]))

        if self.unknown_booleans is not None:
            for i in range(17):
                if i >= len(self.unknown_booleans):
                    stream.extend(struct.pack('<?', False))
                else:
                    stream.extend(struct.pack('<?', self.unknown_booleans[i]))

        if len(self.render_states) > 0:
            stream.extend(struct.pack('<I', 0))

            for state in self.render_states.keys():
                RWMaterialBuilder.write_state(stream, state, self.render_states[state])

            stream.extend(struct.pack('<ii', -1, -1))

        if len(self.texture_slots) > 0:
            stream.extend(struct.pack('<i', -1))

            for texture_slot in self.texture_slots:

                flags = 0
                for state in texture_slot.texture_stage_states.keys():
                    flags |= 1 << (state - 1)

                stream.extend(struct.pack('<iii',
                                          texture_slot.sampler_index,
                                          render_ware.get_index(texture_slot.texture_raster),
                                          flags))

                if flags != 0:
                    for state in texture_slot.texture_stage_states:
                        RWMaterialBuilder.write_state(stream, state, texture_slot.texture_stage_states[state])

                    stream.extend(struct.pack('<i', -1))

                flags = 0
                for state in texture_slot.sampler_states.keys():
                    flags |= 1 << (state - 1)

                stream.extend(struct.pack('<i', flags))
                if flags != 0:
                    for state in texture_slot.sampler_states.keys():
                        RWMaterialBuilder.write_state(stream, state, texture_slot.sampler_states[state])

                    stream.extend(struct.pack('<i', -1))

            stream.extend(struct.pack('<i', -1))

    def from_compiled_state(self, data_reader: FileReader):
        """Reads the compiled state stream."""

        data_reader.skip_bytes(4)  # primitiveType
        flags1 = data_reader.read_uint()
        data_reader.read_uint()  # flags2
        flags3 = data_reader.read_uint()
        field_14 = data_reader.read_uint()
        self.shader_id = data_reader.read_uint()

        data_reader.skip_bytes(4)  # just padding

        if (flags1 & 1) != 0:
            if (flags1 & 2) != 0:
                data_reader.skip_bytes(4)
            else:
                data_reader.skip_bytes(0x40)

        if (flags1 & RWMaterialBuilder.FLAG_VERTEX_DESCRIPTION) != 0:
            rw4_base.VertexDescription(None).read(data_reader)

        if (flags1 & RWMaterialBuilder.FLAG_SHADER_DATA) != 0:

            index = data_reader.read_short()
            while index != 0:
                if index > 0:
                    self.shader_data.append(ShaderData(
                        index=index,
                        offset=data_reader.read_short(),
                        data=data_reader.read(data_reader.read_int())
                    ))
                else:
                    data_reader.skip_bytes(4)
                    
                index = data_reader.read_short()
                
            data_reader.skip_bytes(6)

        if (flags1 & RWMaterialBuilder.FLAG_MATERIAL_COLOR) != 0:
            self.material_color = data_reader.unpack('<ffff')

        if (flags1 & RWMaterialBuilder.FLAG_AMBIENT_COLOR) != 0:
            self.ambient_color = data_reader.unpack('<fff')

        if (flags1 & 0x3FC0) != 0:
            for i in range(8):
                if (flags1 & (1 << (6 + i))) != 0:
                    data_reader.skip_bytes(4)

        if (flags1 & RWMaterialBuilder.FLAG_USE_BOOLEANS) != 0:
            for i in range(0x11):
                self.unknown_booleans.append(data_reader.read_boolean())

        if (flags1 & 0xF0000) != 0:
            if (flags1 & 0x10000) != 0:
                data_reader.skip_bytes(4)

            if (flags1 & 0xE0000) != 0:
                if (flags1 & 0x20000) != 0:
                    data_reader.skip_bytes(12)

                if (flags1 & 0x40000) != 0:
                    data_reader.skip_bytes(4)

                if (flags1 & 0x80000) != 0:
                    data_reader.skip_bytes(4)

        if field_14 != 0:
            if (field_14 & 0x20000) != 0:
                data_reader.skip_bytes(0x1C)

            if (field_14 & 0x40000) != 0:
                data_reader.skip_bytes(0x44)

            if (field_14 & 0x80000) != 0:
                data_reader.skip_bytes(0x44)

        if (flags3 & RWMaterialBuilder.FLAG3_RENDER_STATES) != 0:
            data_reader.skip_bytes(4)

            while True:
                state = data_reader.read_int()
                value = data_reader.read_int()

                if state == -1 and value == -1:
                    break

                self.render_states[state] = value

    def set_render_states(self, alpha_mode='NO_ALPHA'):
        """
        Assigns predefined sets of render states, depending on the alpha mode.
        :param alpha_mode: Possible options are 'NO_ALPHA', 'ALPHA', 'EXCLUDING_ALPHA'
        """

        if alpha_mode == 'NO_ALPHA':
            self.render_states[rw4_enums.D3DRS_ZWRITEENABLE] = 1
            self.render_states[rw4_enums.D3DRS_ALPHATESTENABLE] = 0
            self.render_states[rw4_enums.D3DRS_CULLMODE] = rw4_enums.D3DCULL_CW
            self.render_states[rw4_enums.D3DRS_ZFUNC] = rw4_enums.D3DCMP_LESSEQUAL
            self.render_states[rw4_enums.D3DRS_ALPHABLENDENABLE] = 0

        elif alpha_mode == 'ALPHA':
            self.render_states[rw4_enums.D3DRS_ZWRITEENABLE] = 1
            self.render_states[rw4_enums.D3DRS_ALPHATESTENABLE] = 1
            self.render_states[rw4_enums.D3DRS_SRCBLEND] = rw4_enums.D3DBLEND_SRCALPHA
            self.render_states[rw4_enums.D3DRS_DESTBLEND] = rw4_enums.D3DBLEND_INVSRCALPHA
            self.render_states[rw4_enums.D3DRS_CULLMODE] = rw4_enums.D3DCULL_CW
            self.render_states[rw4_enums.D3DRS_ZFUNC] = rw4_enums.D3DCMP_LESSEQUAL
            self.render_states[rw4_enums.D3DRS_ALPHAREF] = 0
            self.render_states[rw4_enums.D3DRS_ALPHAFUNC] = rw4_enums.D3DCMP_GREATER
            self.render_states[rw4_enums.D3DRS_ALPHABLENDENABLE] = 1

        elif alpha_mode == 'EXCLUDING_ALPHA':
            self.render_states[rw4_enums.D3DRS_ZWRITEENABLE] = 1
            self.render_states[rw4_enums.D3DRS_ALPHATESTENABLE] = 1
            self.render_states[rw4_enums.D3DRS_CULLMODE] = rw4_enums.D3DCULL_CW
            self.render_states[rw4_enums.D3DRS_ZFUNC] = rw4_enums.D3DCMP_LESSEQUAL
            self.render_states[rw4_enums.D3DRS_ALPHAREF] = 127
            self.render_states[rw4_enums.D3DRS_ALPHAFUNC] = rw4_enums.D3DCMP_GREATER
            self.render_states[rw4_enums.D3DRS_ALPHABLENDENABLE] = 0
            self.render_states[rw4_enums.D3DRS_FOGENABLE] = 0

        else:
            raise NameError("Unsupported render states %s" % alpha_mode)

    def detect_render_states(self):
        """
        Returns the detected alpha mode ('NO_ALPHA', 'ALPHA', 'EXCLUDING') depending on the render states of this
        material. Returns None if it cannot be detected.
        """
        if rw4_enums.D3DRS_ALPHATESTENABLE not in self.render_states:
            return None
        if self.render_states[rw4_enums.D3DRS_ALPHATESTENABLE] == 0:
            return 'NO_ALPHA'
        else:
            if rw4_enums.D3DRS_ALPHAREF not in self.render_states or self.render_states[rw4_enums.D3DRS_ALPHAREF] == 0:
                return 'ALPHA'
            else:
                return 'EXCLUDING_ALPHA'
