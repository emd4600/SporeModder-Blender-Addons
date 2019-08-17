__author__ = 'Eric'

from .rw_material import RWMaterial
from .rw_material_builder import RWMaterialBuilder, SHADER_DATA, RWTextureSlot
from .. import rw4_base
import struct

from bpy.props import (StringProperty,
                       BoolProperty,
                       PointerProperty,
                       )


class SkinPaintPart(RWMaterial):
    material_name = "SkinPaint Part"
    material_description = "A part for the Cell, Creature, Outfit and Flora editors."
    material_has_material_color = True
    material_has_ambient_color = False
    material_use_alpha = False

    diffuse_texture: StringProperty(
        name="Diffuse Texture",
        description="The diffuse texture of this material (leave empty if no texture desired)",
        default="",
        subtype='FILE_PATH'
    )

    @staticmethod
    def set_pointer_property(cls):
        cls.material_data_SkinPaintPart = PointerProperty(
            type=SkinPaintPart
        )

    @staticmethod
    def get_material_data(rw4_material):
        return rw4_material.material_data_SkinPaintPart

    @staticmethod
    def draw_panel(layout, rw4_material):
        data = rw4_material.material_data_SkinPaintPart
        layout.prop(data, 'diffuse_texture')

    @staticmethod
    def get_material_builder(exporter, rw4_material):
        render_ware = exporter.render_ware

        material = RWMaterialBuilder()

        RWMaterial.set_general_settings(material, rw4_material, rw4_material.material_data_SkinPaintPart)

        material.shader_id = 0x80000004
        material.unknown_booleans.append(True)  # the rest are going to be False

        # -- RENDER STATES -- #

        material.set_render_states(rw4_material.alpha_type)

        # -- SHADER CONSTANTS -- #

        # In the shader, skinWeights.x = numWeights
        material.add_shader_data(SHADER_DATA['skinWeights'], struct.pack('<i', 4))

        material.add_shader_data(SHADER_DATA['skinBones'], struct.pack(
            '<iiiii',
            0,  # firstBone
            exporter.get_bone_count(),  # numBones
            0,
            render_ware.get_index(None, section_type=rw4_base.INDEX_NO_OBJECT),  # ?
            exporter.get_skin_matrix_buffer_index()
        ))

        # Used for selecting skinPaint shader
        material.add_shader_data(0x216, struct.pack('<i', 0))

        # -- TEXTURE SLOTS -- #

        material.texture_slots.append(
            RWTextureSlot(0, exporter.add_texture(rw4_material.material_data_SkinPaintPart.diffuse_texture)))

        material.texture_slots.append(RWTextureSlot(1, None))

        return material

    @staticmethod
    def parse_material_builder(material: RWMaterialBuilder, rw4_material):
        if material.shader_id != 0x80000004:
            return False

        shader_data = material.get_shader_data(0x216)
        if shader_data is None or shader_data.data is None or len(shader_data.data) != 4:
            return False

        RWMaterial.parse_material_builder(material, rw4_material)

        return True
