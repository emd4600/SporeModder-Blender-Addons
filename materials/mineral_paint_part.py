__author__ = 'Eric'

from .rw_material import RWMaterial
from .rw_material_builder import RWMaterialBuilder, SHADER_DATA, RWTextureSlot
from .. import rw4_base
import struct

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty
                       )


class MineralPaintPart(RWMaterial):
    material_name = "MineralPaint Part"
    material_description = "A part for the Vehicle, Building, UFO and Cake editors."
    material_has_material_color = True
    material_has_ambient_color = False
    material_use_alpha = False

    diffuse_texture: StringProperty(
        name="Diffuse Texture",
        description="The diffuse texture of this material (leave empty if no texture desired)",
        default="",
        subtype='FILE_PATH'
    )

    paint_region: IntProperty(
        name="Paint Region",
        default=1
    )

    use_paint_texture: BoolProperty(
        name="Use Paint Texture",
        description="Uncheck if this material doesn't use textures (everything will be painted with a matte color).",
        default=True
    )

    uv_projection: EnumProperty(
        name="UV Projection",
        items=(
            ('0', "Project XY", ""),  # 0
            ('1', "Project XZ", ""),  # 1
            ('2', "Project YZ", ""),  # 2
            ('3', "BoxMap", ""),  # 3
            ('4', "Cylindrical Z", ""),  # 4
            ('5', "Disc", ""),  # 5
            ('6', "Cylindrical X", ""),  # 6
            ('7', "Cylindrical Y", ""),  # 7
        )
    )

    uv_scale: FloatVectorProperty(
        name="UV Scale",
        default=(1.0, 1.0),
        step=0.1,
        size=2
    )
    uv_offset: FloatVectorProperty(
        name="UV Offset",
        default=(0.0, 0.0),
        step=0.1,
        size=2
    )

    @staticmethod
    def set_pointer_property(cls):
        cls.material_data_MineralPaintPart = PointerProperty(
            type=MineralPaintPart
        )

    @staticmethod
    def get_material_data(rw4_material):
        return rw4_material.material_data_MineralPaintPart

    @staticmethod
    def draw_panel(layout, rw4_material):

        data = rw4_material.material_data_MineralPaintPart

        layout.prop(data, 'diffuse_texture')
        layout.prop(data, 'paint_region')
        layout.prop(data, 'use_paint_texture')

        if data.use_paint_texture:
            layout.prop(data, 'uv_projection')

            layout.prop(data, 'uv_scale')
            layout.prop(data, 'uv_offset')

    @staticmethod
    def get_material_builder(exporter, rw4_material):
        render_ware = exporter.render_ware
        material_data = rw4_material.material_data_MineralPaintPart

        material = RWMaterialBuilder()

        RWMaterial.set_general_settings(material, rw4_material, material_data)

        material.shader_id = 0x80000005 if exporter.is_blend_shape() else 0x80000004
        material.unknown_booleans.append(True)  # the rest are going to be False

        # -- RENDER STATES -- #

        material.set_render_states(rw4_material.alpha_type)

        # -- SHADER CONSTANTS -- #

        material.add_shader_data(SHADER_DATA['region'], struct.pack('<ii', material_data.paint_region, 0x00C7E300))

        if material_data.use_paint_texture:
            material.add_shader_data(SHADER_DATA['uvTweak'], struct.pack(
                '<iffff',
                int(material_data.uv_projection),
                material_data.uv_scale[0],
                material_data.uv_scale[1],
                material_data.uv_offset[0],
                material_data.uv_offset[1],
            ))
        else:
            material.add_shader_data(0x244, struct.pack('<i', 0))

        if exporter.has_skeleton():
            # In the shader, skinWeights.x = numWeights
            material.add_shader_data(SHADER_DATA['skinWeights'], struct.pack('<i', 4))

            material.add_shader_data(SHADER_DATA['skinBones'], struct.pack(
                '<iiiii',
                0,  # firstBone
                exporter.get_bone_count(),  # numBones
                0,
                render_ware.get_index(None, rw4_base.INDEX_NO_OBJECT),  # ?
                exporter.get_skin_matrix_buffer_index()))

        if exporter.is_blend_shape():
            material.add_shader_data(0x5, struct.pack('<i', 0))
            material.add_shader_data(0x200, struct.pack('<ii',
                                                        len(exporter.blend_shape.shape_ids),
                                                        render_ware.get_index(exporter.blend_shape,
                                                                              rw4_base.INDEX_SUB_REFERENCE)))

        # -- TEXTURE SLOTS -- #

        material.texture_slots.append(RWTextureSlot(0, exporter.add_texture(material_data.diffuse_texture)))
        material.texture_slots.append(RWTextureSlot(1, None))

        return material

    @staticmethod
    def parse_material_builder(material: RWMaterialBuilder, rw4_material):

        if material.shader_id != 0x80000004 and material.shader_id != 0x80000005:
            return False

        sh_data = material.get_shader_data(0x20F)
        if sh_data is None or sh_data.data is None or len(sh_data.data) != 8:
            return False

        material_data = rw4_material.material_data_MineralPaintPart

        material_data.paint_region = struct.unpack('<ii', sh_data.data)[0]

        RWMaterial.parse_material_builder(material, rw4_material)

        sh_data = material.get_shader_data(0x211)
        if sh_data is not None and len(sh_data.data) == struct.calcsize('<iffff'):
            material_data.use_paint_texture = True

            values = struct.unpack('<iffff', sh_data.data)
            material_data.uv_projection = str(values[0])
            material_data.uv_scale[0] = values[1]
            material_data.uv_scale[1] = values[2]
            material_data.uv_offset[0] = values[3]
            material_data.uv_offset[1] = values[4]
        else:
            material_data.use_paint_texture = False

        return True
