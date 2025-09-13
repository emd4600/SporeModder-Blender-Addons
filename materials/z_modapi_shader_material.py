__author__ = 'Eric'

from .rw_material import RWMaterial
from .rw_material_builder import RWMaterialBuilder, RWTextureSlot
from ..file_io import get_hash
from bpy.props import (StringProperty,
					   PointerProperty
					   )


# Ensure it's the last on the list
class ZZModAPIShaderMaterial(RWMaterial):
	material_name = "Custom Shader Material"
	material_description = "A base material for using custom shaders."
	material_has_material_color = True
	material_has_ambient_color = False

	shader_name: StringProperty(
		name="Shader Name",
		description="The name or hex code of the shader to be used.",
		default="",
	)
	
	diffuse_texture: StringProperty(
		name="Diffuse Texture",
		description="The diffuse texture of this material (leave empty if no texture desired)",
		default="",
		subtype='FILE_PATH'
	)
	
	texture_slot_1: StringProperty(
		name="Texture Slot 1",
		description="Texture slot 1",
		default="",
		subtype='FILE_PATH'
	)
	
	texture_slot_2: StringProperty(
		name="Texture Slot 2",
		description="Texture slot 2",
		default="",
		subtype='FILE_PATH'
	)
	
	texture_slot_3: StringProperty(
		name="Texture Slot 3",
		description="Texture slot 3",
		default="",
		subtype='FILE_PATH'
	)

	@staticmethod
	def set_pointer_property(cls):
		cls.material_data_ModAPIShaderMaterial = PointerProperty(
			type=ZZModAPIShaderMaterial
		)

	@staticmethod
	def get_material_data(rw4_material):
		return rw4_material.material_data_ModAPIShaderMaterial

	@staticmethod
	def draw_panel(layout, rw4_material):

		data = rw4_material.material_data_ModAPIShaderMaterial

		layout.prop(data, 'shader_name')
		layout.prop(data, 'diffuse_texture')
		layout.prop(data, 'texture_slot_1')
		layout.prop(data, 'texture_slot_2')
		layout.prop(data, 'texture_slot_3')

	@staticmethod
	def get_material_builder(exporter, rw4_material):

		material_data = rw4_material.material_data_ModAPIShaderMaterial

		material = RWMaterialBuilder()

		RWMaterial.set_general_settings(material, rw4_material, material_data)

		material.shader_id = get_hash(material_data.shader_name)
		material.unknown_booleans.append(True)
		material.unknown_booleans.append(True)  # the rest are going to be False

		# -- RENDER STATES -- #

		material.set_render_states('ALPHA')

		# -- SHADER CONSTANTS -- #
		# Add here any shader constants related with your shaders
		# For example:

		# material.add_shader_data(SHADER_DATA['materialParams'], struct.pack('<f', material_data.specularExponent))

		# -- TEXTURE SLOTS -- #

		material.texture_slots.append(RWTextureSlot(
			sampler_index=0,
			texture_raster=exporter.add_texture(material_data.diffuse_texture)
		))
		
		last_slot_index = 0
		for i, slot in enumerate([material_data.texture_slot_1, material_data.texture_slot_2, material_data.texture_slot_3]):
			if slot:
				material.texture_slots.append(RWTextureSlot(
					sampler_index=i,
					texture_raster=exporter.add_texture(slot)
				))
				
		material.texture_slots.append(RWTextureSlot(
			sampler_index=last_slot_index+1,
			texture_raster=None
		))

		return material

	@staticmethod
	def parse_material_builder(material, rw4_material):

		material_data = rw4_material.material_data_ModAPIShaderMaterial

		material_data.shader_name = "0x%X" % material.shader_id

		RWMaterial.parse_material_builder(material, rw4_material)

		return True
