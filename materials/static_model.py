__author__ = 'Eric'

from .rw_material import RWMaterial
from .rw_material_builder import RWMaterialBuilder, SHADER_DATA, RWTextureSlot
from .. import rw4_base
import struct
import bpy
from bpy.props import (StringProperty,
					   BoolProperty,
					   FloatProperty,
					   PointerProperty
					   )


class StaticModel(RWMaterial):
	material_name = "Static Model"
	material_description = "A simple static model which allows normal maps, used for props, backgrounds, etc."
	material_has_material_color = True
	material_has_ambient_color = False
	material_use_alpha = True

	diffuse_texture: StringProperty(
		name="Diffuse Texture",
		description="The diffuse texture of this material (leave empty if no texture desired)",
		default="",
		subtype='FILE_PATH'
	)

	normal_texture: StringProperty(
		name="Normal Texture",
		description="The normal texture of this material, alpha channel is used as specular map"
					" (leave empty if no texture desired)",
		default="",
		subtype='FILE_PATH'
	)

	material_params_1: FloatProperty(
		name="Specular Exponent",
		default=10
	)
	material_params_2: FloatProperty(
		name="Inverse Bumpiness",
		description="This value is multiplied with the 'z' coordinate of the normal map",
		default=1
	)
	material_params_3: FloatProperty(
		name="Material Params[3]",
		default=1
	)
	material_params_4: FloatProperty(
		name="Gloss",
		default=0
	)

	@staticmethod
	def set_pointer_property(cls):
		cls.material_data_StaticModel = PointerProperty(
			type=StaticModel
		)

	@staticmethod
	def get_material_data(rw4_material):
		return rw4_material.material_data_StaticModel

	@staticmethod
	def draw_panel(layout, rw4_material):

		data = rw4_material.material_data_StaticModel

		layout.prop(data, 'diffuse_texture')
		layout.prop(data, 'normal_texture')
		layout.prop(data, 'material_params_1')
		layout.prop(data, 'material_params_2')
		layout.prop(data, 'material_params_3')
		layout.prop(data, 'material_params_4')

	@staticmethod
	def get_material_builder(exporter, rw4_material):
		material_data = rw4_material.material_data_StaticModel

		material = RWMaterialBuilder()

		RWMaterial.set_general_settings(material, rw4_material, material_data)

		if exporter.has_skeleton() or exporter.is_blend_shape(): material.shader_id = 0x80000004
		else: material.shader_id = 0x80000002
		material.unknown_booleans.append(True)
		material.unknown_booleans.append(True)  # the rest are going to be False

		if material.shader_id == 0x80000004:
			material.FLAG3_RENDER_STATES = 0xc0000
		# -- SHADER CONSTANTS -- #

		material.add_shader_data(SHADER_DATA['materialParams'], struct.pack(
			'<iffff',
			0x26445C02,
			material_data.material_params_1,
			material_data.material_params_2,
			material_data.material_params_3,
			material_data.material_params_4
		))

		# Maybe not necessary: this makes it use vertex color?
		# add showIdentityPS -hasData identityColor 0x218 -exclude 0x200
		# add restoreAlphaPS -hasData 0x218 -exclude 0x200
		material.add_shader_data(0x218, struct.pack('<i', 0x028B7C00))

		# -- RENDER STATES -- #
		render_ware = exporter.render_ware
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

		material.texture_slots.append(RWTextureSlot(
			sampler_index=0,
			texture_raster=exporter.add_texture(material_data.diffuse_texture)
		))

		material.texture_slots.append(RWTextureSlot(
			sampler_index=1,
			texture_raster=exporter.add_texture(material_data.normal_texture),
			disable_stage_op=True
		))

		return material

	@staticmethod
	def parse_material_builder(material, rw4_material):

		if material.shader_id != 0x80000002 and material.shader_id != 0x80000004: #not (material.shader_id == 0x80000004 and material.rw4.material_data_StaticModel.normal_texture):
			return False

		for data in material.shader_data:
			print(data)

		# sh_data = material.get_shader_data(0x218)
		# if sh_data is None or sh_data.data is None or len(sh_data.data) != 4:
		#     return False

		material_data = rw4_material.material_data_StaticModel

		RWMaterial.parse_material_builder(material, rw4_material)

		sh_data = material.get_shader_data(SHADER_DATA['materialParams'])
		if sh_data is not None and len(sh_data.data) == struct.calcsize('<iffff'):
			values = struct.unpack('<iffff', sh_data.data)
			material_data.material_params_1 = values[1]
			material_data.material_params_2 = values[2]
			material_data.material_params_3 = values[3]
			material_data.material_params_4 = values[4]

		return True

	@staticmethod
	def set_texture(obj, material, slot_index, path):
		if slot_index == 0:
			material.rw4.material_data_StaticModel.diffuse_texture = path

			image = bpy.data.images.load(path)

			texture_node = material.node_tree.nodes.new("ShaderNodeTexImage")
			texture_node.image = image
			texture_node.location = (-524, 256)

			material.node_tree.links.new(material.node_tree.nodes["Principled BSDF"].inputs["Base Color"],
										 texture_node.outputs["Color"])

		else:
			material.rw4.material_data_StaticModel.normal_texture = path

			image = bpy.data.images.load(path)
			image.colorspace_settings.name = 'Non-Color'

			texture_node = material.node_tree.nodes.new("ShaderNodeTexImage")
			texture_node.image = image
			texture_node.location = (-524, -37)

			normal_map_node = material.node_tree.nodes.new("ShaderNodeNormalMap")
			normal_map_node.location = (-216, -86)

			material.node_tree.links.new(normal_map_node.inputs["Color"],
										 texture_node.outputs["Color"])

			material.node_tree.links.new(material.node_tree.nodes["Principled BSDF"].inputs["Normal"],
										 normal_map_node.outputs["Normal"])

			material.node_tree.links.new(material.node_tree.nodes["Principled BSDF"].inputs["Specular"],
										 texture_node.outputs["Alpha"])
