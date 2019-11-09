__author__ = 'Eric'

from .rw_material import RWMaterial
from .rw_material_builder import RWMaterialBuilder, SHADER_DATA, RWTextureSlot
from .. import rw4_base
import struct
import bpy
import bpy.utils.previews
import os
from mathutils import Vector
from math import acos, fabs
from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty
                       )

custom_icons = None


def uvproj_project_xy(co, _, uv_scale, uv_offset):
    return (co.x * uv_scale.x + uv_offset.x,
            co.y * uv_scale.y + uv_offset.y)


def uvproj_project_xz(co, _, uv_scale, uv_offset):
    return (co.x * uv_scale.x + uv_offset.x,
            co.z * uv_scale.y + uv_offset.y)


def uvproj_project_yz(co, _, uv_scale, uv_offset):
    return (co.y * uv_scale.x + uv_offset.x,
            co.z * uv_scale.y + uv_offset.y)


def uvproj_cylindrical_x(co, _, uv_scale, uv_offset):
    centre = co.yz - uv_offset
    return (acos(centre.x / centre.length) * uv_scale.x * (4 / 3.14159),
            co.x * uv_scale.y)


def uvproj_cylindrical_y(co, _, uv_scale, uv_offset):
    centre = co.xz - uv_offset
    return (acos(centre.x / centre.length) * uv_scale.x * (4 / 3.14159),
            co.y * uv_scale.y)


def uvproj_cylindrical_z(co, _, uv_scale, uv_offset):
    centre = co.xy - uv_offset
    return (acos(centre.x / centre.length) * uv_scale.x * (4 / 3.14159),
            co.z * uv_scale.y)


def uvproj_disc(co, _, uv_scale, uv_offset):
    centre = co.xy - uv_offset
    return (acos(centre.x / centre.length) * uv_scale.x * (4 / 3.14159),
            centre.length * uv_scale.y)


def hlsl_product(a, b):
    return Vector([a1 * a2 for a1, a2 in zip(a, b)])


def hlsl_step(a, x):
    return Vector([(1.0 if x_ >= a_ else 0.0) for a_, x_ in zip(a, x)])


def hlsl_sign(v):
    values = []
    for x in v:
        if x == 0.0:
            values.append(0.0)
        elif x > 0.0:
            values.append(1.0)
        else:
            values.append(-1.0)
    return Vector(values)


def uvproj_boxmap(co, normal, uv_scale, uv_offset):
    an = Vector([fabs(x) for x in normal])
    box_mask = hlsl_step(an.yzx, an)
    box_mask = Vector(hlsl_product(box_mask, hlsl_step(an.zxy, an)))
    sn = hlsl_sign(normal)
    box_mask = hlsl_product(box_mask, Vector((sn.x, -sn.y, 1.0)))
    uv_x = box_mask.dot(co.yxx) * uv_scale.x
    box_mask = hlsl_product(box_mask, Vector((sn.x, -sn.y, sn.z)))
    uv_y = box_mask.dot(co.zzy) * uv_scale.y
    return uv_x, uv_y


UV_PROJECTION_METHODS = {
    'ProjectXY': uvproj_project_xy,
    'ProjectXZ': uvproj_project_xz,
    'ProjectYZ': uvproj_project_yz,
    'BoxMap': uvproj_boxmap,
    'CylindricalX': uvproj_cylindrical_x,
    'CylindricalY': uvproj_cylindrical_y,
    'CylindricalZ': uvproj_cylindrical_z,
    'Disc': uvproj_disc
}

UV_PROJECTION = {
    'ProjectXY': 0,
    'ProjectXZ': 1,
    'ProjectYZ': 2,
    'BoxMap': 3,
    'CylindricalX': 6,
    'CylindricalY': 7,
    'CylindricalZ': 4,
    'Disc': 5
}


def apply_uv_projection(_, __):
    return
    #TODO consider in future updates
    obj = bpy.context.active_object
    mesh = obj.data
    mat = obj.active_material
    rw = mat.rw4.material_data_MineralPaintPart
    if not mesh.uv_layers:
        uv_data = mesh.uv_layers.new().data
    else:
        uv_data = mesh.uv_layers.active.data
    applied_vertices = [None] * len(mesh.vertices)

    for poly in obj.data.polygons:
        if mesh.materials[poly.material_index] != mat:
            continue

        for i in range(poly.loop_start, poly.loop_start + poly.loop_total):
            uv = applied_vertices[mesh.loops[i].vertex_index]
            if uv is None:
                vertex = mesh.vertices[mesh.loops[i].vertex_index]
                uv = UV_PROJECTION_METHODS[rw.uv_projection](
                    Vector(vertex.co), Vector(vertex.normal), Vector(rw.uv_scale), Vector(rw.uv_offset)
                )
                applied_vertices[mesh.loops[i].vertex_index] = uv

            uv_data[i].uv[0] = uv[0]
            uv_data[i].uv[1] = uv[1]


def projection_items_callback(_, __):
    global custom_icons
    if custom_icons is None:
        custom_icons = bpy.utils.previews.new()
        addon_path = os.path.dirname(os.path.realpath(__file__))
        icons_dir = os.path.join(os.path.dirname(addon_path), "icons")
        for name in ("ProjectXY", "ProjectXZ", "ProjectYZ", "BoxMap",
                     "CylindricalX", "CylindricalY", "CylindricalZ", "Disc"):
            custom_icons.load(name, os.path.join(icons_dir, f"{name}.png"), 'IMAGE')

    return ('ProjectXY', "Project XY", "Applies texture as a plane with edges parallel to the X and Y axes."
                                       " The texture is projected along the Z axis",
            custom_icons["ProjectXY"].icon_id, 0), \
           ('ProjectXZ', "Project XZ", "Applies texture as a plane with edges parallel to the X and Z axes."
                                    " The texture is projected along the Y axis",
            custom_icons["ProjectXZ"].icon_id, 1), \
           ('ProjectYZ', "Project YZ", "Applies texture as a plane with edges parallel to the Y and Z axes."
                                       " The texture is projected along the X axis",
            custom_icons["ProjectYZ"].icon_id, 2), \
           ('CylindricalX', "Cylindrical X", "", custom_icons["CylindricalX"].icon_id, 6), \
           ('CylindricalY', "Cylindrical Y", "", custom_icons["CylindricalY"].icon_id, 7), \
           ('CylindricalZ', "Cylindrical Z", "", custom_icons["CylindricalZ"].icon_id, 4), \
           ('BoxMap', "BoxMap", "", custom_icons["BoxMap"].icon_id, 3), \
           ('Disc', "Disc", "", custom_icons["Disc"].icon_id, 5)


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
        description="When painting, all materials with the same paint region value will use the same paint",
        default=7
    )

    paint_mode: EnumProperty(
        name="Paint Mode",
        items=(
            ('PAINT', "Paint (Texture)", ""),
            ('PAINT_COLOR', "Paint (only Color)", "This mesh will be paintable, but it won't use the paint texture, "
                                                  "only the color.'"),
            ('TEXTURE', "Model Texture", "Use the texture exported with the model. This mesh won't be paintable.'"),
        ),
        default='PAINT'
    )

    uv_projection: EnumProperty(
        name="UV Projection",
        description="The projection decides how the paint texture is applied to the model. You should choose the "
                    "option more appropiate for the geometry of the model",
        items=projection_items_callback,
        update=apply_uv_projection
    )

    uv_scale: FloatVectorProperty(
        name="UV Scale",
        default=(1.0, 1.0),
        step=0.1,
        size=2,
        update=apply_uv_projection
    )
    uv_offset: FloatVectorProperty(
        name="UV Offset",
        default=(0.0, 0.0),
        step=0.1,
        size=2,
        update=apply_uv_projection
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

        layout.prop(data, 'paint_mode')
        layout.separator()

        if data.paint_mode == 'TEXTURE':
            layout.prop(data, 'diffuse_texture')
        else:
            layout.prop(data, 'paint_region')
            if data.paint_mode == 'PAINT':
                layout.label(text="Paint Texture might not work depending on the region.", icon='ERROR')

        if data.paint_mode == 'PAINT':
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

        region = 50 if material_data.paint_mode == 'TEXTURE' else material_data.paint_region
        diffuse_texture = ""

        material.add_shader_data(SHADER_DATA['region'], struct.pack('<ii', region, 0x00C7E300))

        if material_data.paint_mode == 'TEXTURE':
            diffuse_texture = material_data.diffuse_texture
            material.add_shader_data(0x217, struct.pack('<i', 0))

        elif material_data.paint_mode == 'PAINT':
            material.add_shader_data(SHADER_DATA['uvTweak'], struct.pack(
                '<iffff',
                UV_PROJECTION[material_data.uv_projection],
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

        material.texture_slots.append(RWTextureSlot(0, exporter.add_texture(diffuse_texture)))
        material.texture_slots.append(RWTextureSlot(1, None))

        return material

    @staticmethod
    def parse_material_builder(material: RWMaterialBuilder, rw4_material):

        if material.shader_id != 0x80000004 and material.shader_id != 0x80000005:
            return False

        sh_data = material.get_shader_data(SHADER_DATA['region'])
        if sh_data is None or sh_data.data is None or len(sh_data.data) != 8:
            return False

        material_data = rw4_material.material_data_MineralPaintPart

        material_data.paint_region = struct.unpack('<ii', sh_data.data)[0]

        RWMaterial.parse_material_builder(material, rw4_material)

        sh_data = material.get_shader_data(SHADER_DATA['uvTweak'])
        if sh_data is not None and len(sh_data.data) == struct.calcsize('<iffff'):
            material_data.use_paint_texture = True

            values = struct.unpack('<iffff', sh_data.data)
            material_data.uv_projection = next(key for key in UV_PROJECTION if UV_PROJECTION[key] == values[0])
            material_data.uv_scale[0] = values[1]
            material_data.uv_scale[1] = values[2]
            material_data.uv_offset[0] = values[3]
            material_data.uv_offset[1] = values[4]

        else:
            sh_data = material.get_shader_data(0x244)
            if sh_data is not None and len(sh_data.data) == 4:
                material_data.paint_mode = 'PAINT_COLOR'
            else:
                material_data.paint_mode = 'TEXTURE'

        return True

    @staticmethod
    def set_texture(obj, material, slot_index, path):
        material.rw4.material_data_SkinPaintPart.diffuse_texture = path

        image = bpy.data.images.load(path)

        texture_node = material.node_tree.nodes.new("ShaderNodeTexImage")
        texture_node.image = image
        texture_node.location = (-524, 256)

        material.node_tree.links.new(material.node_tree.nodes["Principled BSDF"].inputs["Base Color"],
                                     texture_node.outputs["Color"])
