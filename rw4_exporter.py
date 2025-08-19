__author__ = 'Eric'

import bpy
from . import rw4_base, rw4_enums, file_io, rw4_validation
from . import rw4_material_config
from mathutils import Matrix, Quaternion, Vector
from random import choice
import re


def show_message_box(message: str, title: str, icon='ERROR'):
	def draw(self, context):
		self.layout.label(text=message)

	bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def show_multi_message_box(messages, title: str, icon='ERROR'):
	def draw(self, context):
		for message in messages:
			self.layout.label(text=message)

	bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def write_index_buffer(data, fmt):
	file = file_io.ArrayFileWriter()
	if fmt == rw4_enums.D3DFMT_INDEX16:
		for x in data:
			file.write_ushort(x)
	elif fmt == rw4_enums.D3DFMT_INDEX32:
		for x in data:
			file.write_uint(x)

	return file.buffer


def write_vertex_buffer(data, vertex_elements):
	data = convert_vertices(data, vertex_elements)
	file = file_io.ArrayFileWriter()
	for v in data:
		rw4_enums.write_rw_vertex(vertex_elements, v, file)

	return file.buffer


def signed_float_to_ubyte(value):
	return int(round(value * 127.5 + 127.5) & 0xFF)


def unpack_ubyte_vec3(values):
	return Vector((
		(values[0] - 127.5) / 127.5,
		(values[1] - 127.5) / 127.5,
		(values[2] - 127.5) / 127.5))


def pack_ubyte_vec3(values):
	return (
		int(round(values[0] * 127.5 + 127.5) & 0xFF),
		int(round(values[1] * 127.5 + 127.5) & 0xFF),
		int(round(values[2] * 127.5 + 127.5) & 0xFF),
		0)


def mesh_triangulate(me):
	"""
	Creates a triangulated copy of `me` and stores it on `me`.
	:param me: The Blender mesh to be triangulated
	"""
	import bmesh
	bm = bmesh.new()
	bm.from_mesh(me)
	bmesh.ops.triangulate(bm, faces=bm.faces)
	bm.to_mesh(me)
	bm.free()


def calculate_tangents(vertices, faces):
	"""
	Calculates the tangents of a processed mesh, storing them on `vertices['tangent']`
	This requires the `position`, `texcoord0` and `normal` attributes.

	:param vertices: A dictionary of vertices attributes lists.
	:param faces: A list of [i, j, k, material_index] faces
	"""
	positions = vertices["position"]
	texcoord0 = vertices["texcoord0"]
	normals = vertices["normal"]
	vertex_count = len(positions)
	tangents = [Vector((0.0, 0.0, 0.0)) for _ in range(vertex_count)]
	bitangents = [Vector((0.0, 0.0, 0.0)) for _ in range(vertex_count)]

	for f, face in enumerate(faces):
		v0_co = positions[face[0]]
		v1_co = positions[face[1]]
		v2_co = positions[face[2]]

		v0_uv = texcoord0[face[0]]
		v1_uv = texcoord0[face[1]]
		v2_uv = texcoord0[face[2]]

		dco1 = v1_co - v0_co
		dco2 = v2_co - v0_co
		duv1 = Vector((v1_uv[0], v1_uv[1])) - Vector((v0_uv[0], v0_uv[1]))
		duv2 = Vector((v2_uv[0], v2_uv[1])) - Vector((v0_uv[0], v0_uv[1]))
		tangent = dco2 * duv1.y - dco1 * duv2.y
		bitangent = dco2 * duv1.x - dco1 * duv2.x
		if dco2.cross(dco1).dot(bitangent.cross(tangent)) < 0:
			tangent.negate()
			bitangent.negate()
		tangents[face[0]] += tangent
		tangents[face[1]] += tangent
		tangents[face[2]] += tangent
		bitangents[face[0]] += bitangent
		bitangents[face[1]] += bitangent
		bitangents[face[2]] += bitangent

	for i in range(len(tangents)):
		tangents[i] = (tangents[i] - normals[i] * tangents[i].dot(normals[i])).normalized()

	vertices["tangent"] = tangents


def convert_vertices(vertices, vertex_elements):
	"""
	Converts a dictionary of vertex attributes lists into a list of Vertex objects,
	generated using the given vertex elements list.

	This method also converts the 'normal' and 'tangent' attributes into the packed 8-bit types
	required by Spore.

	:param vertices: A dictionary of vertex attributes lists
	:param vertex_elements: A list of VertexElement objects.
	:return:
	"""
	if 'normal' in vertices:
		vertices['normal'] = [pack_ubyte_vec3(v) for v in vertices['normal']]

	if 'tangent' in vertices:
		vertices['tangent'] = [pack_ubyte_vec3(v) for v in vertices['tangent']]

	vertex_class = rw4_enums.create_rw_vertex_class(vertex_elements)
	return [vertex_class(**dict(zip(vertices, v))) for v in zip(*vertices.values())]


class ExporterBone:
	def __init__(self, matrix, translation, parent=None):
		self.matrix = matrix
		self.translation = translation
		self.parent = parent

class RW4Exporter:

	def __init__(self):
		self.render_ware = rw4_base.RenderWare4()

		self.warnings = set()

		self.added_textures = {}

		self.b_armature_object = None
		self.b_mesh_objects = []
		# Used to separate collections, maps each armature action to its armature
		self.b_armature_actions = {}
		self.b_shape_keys_actions = {}

		self.bones_skin = {}  # Maps name to skin
		self.skin_matrix_buffer = None
		self.animation_skin = None
		self.skeleton = None

		self.render_ware.header.rw_type_code = rw4_enums.RW_MODEL

		self.bound_box = None

		# for TriangleKDTreeProcedural
		self.triangles = []
		self.vertices = []
		self.triangle_unknowns = []

		self.blend_shape = None

	def has_skeleton(self):
		"""
		:return: True if this models uses a skeleton, False otherwise.
		"""
		return self.b_armature_object is not None

	def is_blend_shape(self):
		"""
		:return: True if this models uses a blend shape, False otherwise.
		"""
		return self.blend_shape is not None

	def get_bone_count(self):
		"""
		:return: The amount of bones in the skeleton of this RW4, or 0 if there is no skeleton.
		"""

		if self.b_armature_object is None:
			return 0
		return len(self.b_armature_object.data.bones)

	def get_skin_matrix_buffer_index(self):
		"""
		:return: The reference index to the skin matrix buffer, or a NO_OBJECT index if it hasn't been added yet.
		"""
		if self.skin_matrix_buffer is not None:
			return self.render_ware.get_index(self.skin_matrix_buffer, rw4_base.INDEX_SUB_REFERENCE)

		else:
			return self.render_ware.get_index(None, rw4_base.INDEX_NO_OBJECT)

	def add_texture(self, path: str):
		"""
		Adds a texture to be exported in the RenderWare4. Only DDS textures are supported.
		If the path has already been exported, no new object is created.

		If the path beigns with $, a raster will be added prepared for using a texture override.

		:param path: File path to the .dds texture.
		:return: The Raster object created for this texture, or a BaseResource if texture override is used.
		"""

		if path in self.added_textures:
			return self.added_textures[path]

		if path.startswith("$"):
			buffer = rw4_base.TextureOverride(self.render_ware, path[1:])
			self.render_ware.add_object(buffer)
			self.added_textures[path] = buffer
			return buffer

		raster = rw4_base.Raster(self.render_ware)
		data_buffer = rw4_base.BaseResource(self.render_ware)
		use_emtpy_texture = True
		
		if not path.endswith(".dds"):
			if path == "":
				error = rw4_validation.error_texture_missing()
			else:
				error = rw4_validation.error_texture_not_dds(path)
				if error not in self.warnings:
					self.warnings.add(error)     
		elif path:
			try:
				with open(bpy.path.abspath(path), 'rb') as file:
					dds_texture = rw4_base.DDSTexture()
					dds_texture.read(file_io.FileReader(file))

					raster.from_dds(dds_texture)
					data_buffer.data = dds_texture.data
					use_emtpy_texture = False

			except FileNotFoundError as _:
				error = rw4_validation.error_texture_does_not_exist(path)
				if error not in self.warnings:
					self.warnings.add(error)

			except BaseException as _:
				error = rw4_validation.error_texture_error(path)
				if error not in self.warnings:
					self.warnings.add(error)

		if use_emtpy_texture:
			# Just create an empty texture
			raster.width = 64
			raster.height = 64
			raster.mipmap_levels = 7
			raster.texture_format = rw4_enums.D3DFMT_DXT5
			data_buffer.data = bytearray(5488)  # ?

		self.added_textures[path] = raster

		raster.texture_data = data_buffer

		# Add the objects we just created
		self.render_ware.add_object(raster)
		self.render_ware.add_object(data_buffer)

		return raster

	def process_vertex_bones(self, obj, b_vertex, vertex_dict, base255):
		"""
		Adds the bone indices and weights of the given vertex into the vertex attributes.

		:param obj: The Blender mesh object.
		:param b_vertex: The Blender vertex.
		:param vertex_dict: A dictionary of vertex attributes lists.
		:param base255: If True, weights will be converted to 0-255 integer range
		:returns: False if there was an error with the bones and exporting must stop
		"""
		indices = [0, 0, 0, 0]
		# Special case: if there are no bone weights, we must do this or the model will be invisible
		weights = [255, 0, 0, 0] if base255 else [1.0, 0, 0, 0]
		total_weight = 0
		for i, gr in enumerate(b_vertex.groups):
			v_group = obj.vertex_groups[gr.group]
			bone_query = [j for j, bone in enumerate(self.b_armature_object.data.bones) if bone.name == v_group.name]
			if not bone_query:
				error = rw4_validation.error_no_bone_for_vertex_group(v_group)
				if error not in self.warnings:
					self.warnings.add(error)
				continue
				
			index = bone_query[0]
			
			if index * 3 > 255:
				error = rw4_validation.error_too_many_bones(self.b_armature_object)
				if error not in self.warnings:
					self.warnings.add(error)
				break

			if i == 4:
				error = rw4_validation.error_vertex_bone_limit(obj)
				if error not in self.warnings:
					self.warnings.add(error)
				break

			weight = round(gr.weight * 255) if base255 else gr.weight
			total_weight += weight
			indices[i] = index * 3
			weights[i] = weight

		if base255:
			if total_weight == 256:
				for i in range(4):
					if weights[i] != 0:
						weights[i] = weights[i] - 1
						total_weight -= 1
						break
			elif total_weight == 254:
				for i in range(4):
					if weights[i] != 0:
						weights[i] = weights[i] + 1
						total_weight += 1
						break

			if total_weight != 255:
				error = rw4_validation.error_not_normalized(obj)
				if error not in self.warnings:
					self.warnings.add(error)
					return False
		else:
			epsilon = 0.002
			if total_weight > 1.0 + epsilon or total_weight < 1.0 - epsilon:
				error = rw4_validation.error_not_normalized(obj)
				if error not in self.warnings:
					self.warnings.add(error)

		vertex_dict['blendIndices'].append(indices)
		vertex_dict['blendWeights'].append(weights)
		return True

	def process_mesh(self, obj, mesh, use_texcoord, use_bones, base255):
		"""
		Spore models only have one UV per-vertex, whereas Blender can have more than just one.
		This method converts a Blender mesh into a valid Spore mesh.

		The output vertices is a dictionary that assigns a list of values for each vertex attribute ('position', etc)
		The output triangles is a list of [i, j, k, material_index] elements.
		The output indices_map is such as indices_map[i] is the index of the original vertex that
		corresponds to the new vertex of index i.

		The output normals and tangents are in float numbers, and not converted to the packed 8-bit type.

		:param obj: The Blender mesh object that must be processed.
		:param mesh: The triangulated Blender mesh.
		:param use_texcoord: Whether UV texcoords must be processed.
		:param use_bones: Whether bone indices/weights must be processed.
		:param base255: If True, bone weights will be converted to 0-255 integer range.
		:returns: A tuple of (vertices, triangles, indices_map)
		"""
		# The result; triangles are (i, j, k, material_index)
		triangles = [None] * len(mesh.polygons)
		positions = []
		normals = []
		texcoords = []
		indices_map = []
		vertices = {'position': positions, 'normal': normals}

		if use_bones:
			vertices['blendIndices'] = []
			vertices['blendWeights'] = []

		if not use_texcoord:
			# No need to process if we don't have UV coords

			for t, face in enumerate(mesh.polygons):
				triangles[t] = (mesh.loops[face.loop_start].vertex_index,
								mesh.loops[face.loop_start + 1].vertex_index,
								mesh.loops[face.loop_start + 2].vertex_index,
								face.material_index)

			for i, b_vertex in enumerate(mesh.vertices):
				positions.append(Vector((b_vertex.co[0], b_vertex.co[1], b_vertex.co[2])))
				normals.append(Vector((b_vertex.normal[0], b_vertex.normal[1], b_vertex.normal[2])))
				if use_bones:
					if not self.process_vertex_bones(obj, b_vertex, vertices, base255):
						return None, None, None

				indices_map.append(i)

		else:
			# Each item of this list is a list of all the new vertex indices that
			# represent that vertex
			new_vertex_indices = [[] for _ in range(len(mesh.vertices))]
			current_processed_index = 0

			uv_data = mesh.uv_layers.active.data

			for t, face in enumerate(mesh.polygons):

				triangles[t] = [-1, -1, -1, face.material_index]

				for i in range(face.loop_start, face.loop_start + 3):
					index = mesh.loops[i].vertex_index

					# Has a vertex with these UV coordinates been already processed?
					for processed_index in new_vertex_indices[index]:
						uv = texcoords[processed_index]
						if uv[0] == uv_data[i].uv[0] and uv[1] == -uv_data[i].uv[1]:
							triangles[t][i - face.loop_start] = processed_index
							break

					# If no vertex with UVs has been processed
					else:
						b_vertex = mesh.vertices[index]

						# We will calculate the tangents later, once we have everything
						positions.append(Vector((b_vertex.co[0], b_vertex.co[1], b_vertex.co[2])))
						normals.append(Vector((b_vertex.normal[0], b_vertex.normal[1], b_vertex.normal[2])))
						# Flip vertical UV coordinates so it uses DirectX system
						texcoords.append(Vector((uv_data[i].uv[0], -uv_data[i].uv[1])))

						if use_bones:
							if not self.process_vertex_bones(obj, b_vertex, vertices, base255):
								return None, None, None

						indices_map.append(index)
						triangles[t][i - face.loop_start] = current_processed_index
						new_vertex_indices[index].append(current_processed_index)
						current_processed_index += 1

			vertices['texcoord0'] = texcoords
			calculate_tangents(vertices, triangles)

		if len(vertices) > 65536:
			error = rw4_validation.error_vertices_limit(obj)
			if error not in self.warnings:
				self.warnings.add(error)

		return vertices, triangles, indices_map

	def create_vertex_description(self, use_texcoord: bool, use_bones: bool):
		"""
		Creates the VertexDescription object used to define a certain vertex format.
		The elements will be:
		 - position
		 - normal
		 - texcoord0 (if use_texcoord)
		 - tangent (if use_texcoord)
		 - blendIndices (if use_bones)
		 - blendWeights (if use_bones)

		:param use_texcoord: If UV texcoords must be included in this description.
		:param use_bones: If bone indices/weights must be included in this description.
		:return: The VertexDescription object.
		"""
		description = rw4_base.VertexDescription(self.render_ware)
		offset = 0

		element = rw4_enums.VertexElement(
			stream=0,
			offset=offset,
			element_type=rw4_enums.D3DDECLTYPE_FLOAT3,
			method=rw4_enums.D3DDECLMETHOD_DEFAULT,
			usage=rw4_enums.D3DDECLUSAGE_POSITION,
			usage_index=0,
			rw_decl=rw4_enums.RWDECL_POSITION
		)
		description.vertex_elements.append(element)
		offset += 12  # 3 floats, 4 bytes each

		element = rw4_enums.VertexElement(
			stream=0,
			offset=offset,
			element_type=rw4_enums.D3DDECLTYPE_UBYTE4,
			method=rw4_enums.D3DDECLMETHOD_DEFAULT,
			usage=rw4_enums.D3DDECLUSAGE_NORMAL,
			usage_index=0,
			rw_decl=rw4_enums.RWDECL_NORMAL
		)
		description.vertex_elements.append(element)
		offset += 4

		if use_texcoord:
			element = rw4_enums.VertexElement(
				stream=0,
				offset=offset,
				element_type=rw4_enums.D3DDECLTYPE_UBYTE4,
				method=rw4_enums.D3DDECLMETHOD_DEFAULT,
				usage=rw4_enums.D3DDECLUSAGE_TANGENT,
				usage_index=0,
				rw_decl=rw4_enums.RWDECL_TANGENT
			)
			description.vertex_elements.append(element)
			offset += 4

			element = rw4_enums.VertexElement(
				stream=0,
				offset=offset,
				element_type=rw4_enums.D3DDECLTYPE_FLOAT2,
				method=rw4_enums.D3DDECLMETHOD_DEFAULT,
				usage=rw4_enums.D3DDECLUSAGE_TEXCOORD,
				usage_index=0,
				rw_decl=rw4_enums.RWDECL_TEXCOORD0
			)
			description.vertex_elements.append(element)
			offset += 8

		if use_bones:
			element = rw4_enums.VertexElement(
				stream=0,
				offset=offset,
				element_type=rw4_enums.D3DDECLTYPE_UBYTE4,
				method=rw4_enums.D3DDECLMETHOD_DEFAULT,
				usage=rw4_enums.D3DDECLUSAGE_BLENDINDICES,
				usage_index=0,
				rw_decl=rw4_enums.RWDECL_BLENDINDICES
			)
			description.vertex_elements.append(element)
			offset += 4

			element = rw4_enums.VertexElement(
				stream=0,
				offset=offset,
				element_type=rw4_enums.D3DDECLTYPE_UBYTE4N,
				method=rw4_enums.D3DDECLMETHOD_DEFAULT,
				usage=rw4_enums.D3DDECLUSAGE_BLENDWEIGHT,
				usage_index=0,
				rw_decl=rw4_enums.RWDECL_BLENDWEIGHTS
			)
			description.vertex_elements.append(element)
			offset += 4

		description.vertex_size = offset
		description.field_14 = 0x51010101

		return description

	def export_as_vertex_buffer(self, vertices, vertex_desc):
		"""
		Exports a list of vertices as a vertex buffer. This will add to the RW4
		a VertexBuffer and BaseResource objects containing the vertices data.

		:param vertices: A dictionary of vertex attributes lists.
		:param vertex_desc: The VertexDescription used for this buffer.
		:return: The created VertexBuffer object.
		"""
		vertex_buffer = rw4_base.VertexBuffer(
			self.render_ware,
			vertex_description=vertex_desc,
			base_vertex_index=0,
			vertex_count=len(vertices['position']),
			field_10=8,
			vertex_size=vertex_desc.vertex_size
		)

		vertex_buffer.vertex_data = rw4_base.BaseResource(
			self.render_ware,
			data=write_vertex_buffer(vertices, vertex_desc.vertex_elements),
		)

		self.render_ware.add_object(vertex_buffer)
		self.render_ware.add_object(vertex_buffer.vertex_data)

		return vertex_buffer

	def export_as_blend_shape(self, vertices, faces, indices_map, obj):
		"""
		Exports a list of vertices as a blend shape. This will add to the RW4 a BlendShape
		and BlendShapeBuffer objects containing the vertices data for all shape keys of the object.
		The Blender mesh is expected to use relative shape keys.

		:param vertices: A dictionary of vertex attributes lists.
		:param faces: A list of face indices tuples.
		:param indices_map: A list that contains the index to the Blender vertices for every processed vertex index.
		:param obj: The Blender mesh object being exported.
		"""
		#TODO remove influence from bones, to avoid problems when using to_mesh
		self.blend_shape = rw4_base.BlendShape(
			self.render_ware,
			object_id=file_io.get_hash(obj.name),
			shape_ids=[file_io.get_hash(block.name) for block in obj.data.shape_keys.key_blocks[1:]]
		)

		vertex_count = len(vertices['position'])

		blend_shape_buffer = rw4_base.BlendShapeBuffer(
			self.render_ware,
			shape_count=len(obj.data.shape_keys.key_blocks) - 1,
			vertex_count=vertex_count
		)

		positions = vertices['position']

		data = file_io.ArrayFileWriter()
		blend_shape_buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_POSITION] = data.tell()

		for v in positions:
			data.pack('<fff', *v)
			data.write_int(0)

		for shape_key in obj.data.shape_keys.key_blocks[1:]:
			for i in range(vertex_count):
				data.pack('<fff', *(Vector(shape_key.data[indices_map[i]].co) - Vector(positions[i])))
				data.write_int(0)

		blend_shape_buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_NORMAL] = data.tell()
		for v in vertices['normal']:
			data.pack('<fff', *v)
			data.write_int(0)

		tangent_data = file_io.ArrayFileWriter() if 'tangent' in vertices else None
		# For normals and tangents, we need to use to_mesh using the shape influence
		# Save the old ones to restore them later
		shape_values = [shape_key.value for shape_key in obj.data.shape_keys.key_blocks[1:]]

		for shape_key in obj.data.shape_keys.key_blocks[1:]:
			shape_key.value = 0.0

		for shape_key in obj.data.shape_keys.key_blocks[1:]:
			shape_key.value = 1.0
			blender_mesh = obj.to_mesh()

			for i in range(vertex_count):
				data.pack('<fff', *blender_mesh.vertices[indices_map[i]].normal)
				data.write_int(0)

			if tangent_data is not None:
				blended_vertices = dict(**vertices)
				blended_vertices['position'] = [blender_mesh.vertices[indices_map[i]].co for i in range(vertex_count)]
				blended_vertices['normal'] = [blender_mesh.vertices[indices_map[i]].normal for i in range(vertex_count)]
				calculate_tangents(blended_vertices, faces)

				for v in blended_vertices['tangent']:
					tangent_data.pack('<fff', *v)
					tangent_data.write_int(0)

			obj.to_mesh_clear()
			shape_key.value = 0.0

		for shape_key, value in zip(obj.data.shape_keys.key_blocks[1:], shape_values):
			shape_key.value = value

		if 'tangent' in vertices:
			blend_shape_buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_TANGENT] = data.tell()
			for v in vertices['tangent']:
				data.pack('<fff', *v)
				data.write_int(0)
			data.write(tangent_data.buffer)

		if 'texcoord0' in vertices:
			blend_shape_buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_TEXCOORD] = data.tell()
			for v in vertices['texcoord0']:
				data.pack('<ff', *v)
				data.write_int(0)
				data.write_int(1)

		if 'blendIndices' in vertices:
			blend_shape_buffer.bone_indices_count = 4
			blend_shape_buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_BLENDINDICES] = data.tell()
			for v in vertices['blendIndices']:
				data.pack('<HHHH', *v)
		else:
			blend_shape_buffer.bone_indices_count = 0

		if 'blendWeights' in vertices:
			blend_shape_buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_BLENDWEIGHTS] = data.tell()
			for v in vertices['blendWeights']:
				data.pack('<ffff', v[0], v[1], v[2], v[3])

		blend_shape_buffer.data = data.buffer
		self.render_ware.add_object(self.blend_shape)
		self.render_ware.add_object(blend_shape_buffer)

		self.blend_shape.shape_times_index = self.render_ware.add_sub_reference(self.blend_shape, 0x1C)
		self.blend_shape.shape_ids_index = \
			self.render_ware.add_sub_reference(self.blend_shape, 0x1C + len(self.blend_shape.shape_ids) * 4)

	def export_mesh_object(self, obj):
		"""
		Exports a Blender mesh into the RW4.

		Each Blender mesh will have it's own vertex and indices buffers. If the object uses shape keys, a
		BlendShape buffer will be used instead; when that is the case, only one Blender mesh can be exported.

		A different mesh, compiled state, and MeshCompiledStateLink will be created for every material
		in the Blender object.

		:param obj: The Blender mesh object to be exported.
		"""
		render_ware = self.render_ware

		if obj.matrix_world != Matrix.Identity(4):
			error = rw4_validation.error_transforms(obj)
			if error not in self.warnings:
				self.warnings.add(error)
			# Still, process the model as more warnings might arise, so don't return

		if not obj.material_slots:
			error = rw4_validation.error_no_material(obj)
			if error not in self.warnings:
				self.warnings.add(error)
			# Still, process the model as more warnings might arise, so don't return

		if obj.modifiers:
			if len(obj.modifiers) > 1 or obj.modifiers[0].type != 'ARMATURE':
				error = rw4_validation.error_modifiers(obj)
				if error not in self.warnings:
					self.warnings.add(error)

		use_shape_keys = obj.data.shape_keys is not None and len(obj.data.shape_keys.key_blocks) > 1
		if use_shape_keys and self.b_mesh_objects:
			error = rw4_validation.error_shape_keys_multi_models()
			if error not in self.warnings:
				self.warnings.add(error)
			return

		if use_shape_keys and not obj.data.shape_keys.use_relative:
			error = rw4_validation.error_shape_keys_not_relative()
			if error not in self.warnings:
				self.warnings.add(error)

		blender_mesh = obj.to_mesh()
		mesh_triangulate(blender_mesh)
		self.b_mesh_objects.append(obj)

		use_texcoord = blender_mesh.uv_layers.active is not None
		use_bones = self.b_armature_object is not None

		if not use_texcoord:
			#TODO depending on the material? where did the "No material" go?
			error = rw4_validation.error_no_texcoord(obj)
			if error not in self.warnings:
				self.warnings.add(error)

		# For each object, create a vertex and index buffer

		# When there is BlendShape, Spore does not add the bone indices to the vertex format, I don't know why
		vertex_desc = self.create_vertex_description(use_texcoord, use_bones and not use_shape_keys)

		vertices, triangles, indices_map = self.process_mesh(
			obj, blender_mesh, use_texcoord, use_bones, not use_shape_keys)
		
		if vertices is None:
			# There was a critical error, stop exporting
			return

		# When it's only for exporting we must remove it
		obj.to_mesh_clear()

		# Configure INDEX BUFFER
		index_buffer = rw4_base.IndexBuffer(
			render_ware,
			start_index=0,
			# we are going to use triangles
			primitive_count=len(triangles) * 3,
			usage=rw4_enums.D3DUSAGE_WRITEONLY,
			index_format=rw4_enums.D3DFMT_INDEX16,
			primitive_type=rw4_enums.D3DPT_TRIANGLELIST
		)
		# We will set the buffer data later, after we have ordered them by material

		if use_shape_keys:
			self.export_as_blend_shape(vertices, triangles, indices_map, obj)
			vertex_buffer = None

		else:
			vertex_buffer = self.export_as_vertex_buffer(vertices, vertex_desc)

		index_data = []

		for material_index, blender_material in enumerate(obj.material_slots):
			first_index = len(index_data)
			triangle_count = 0

			for tri in triangles:
				if tri[3] == material_index:
					index_data += tri[0:3]
					triangle_count += 1

			# There's no need to create a mesh if there are no triangles
			if triangle_count > 0:
				first_vertex = index_data[first_index]
				last_vertex = index_data[first_index]

				for i in range(first_index, first_index + triangle_count * 3):
					if index_data[i] < first_vertex:
						first_vertex = index_data[i]

					elif index_data[i] > last_vertex:
						last_vertex = index_data[i]

				mesh = rw4_base.Mesh(
					render_ware,
					field_0=40,  # I have no idea of what this is
					primitive_type=rw4_enums.D3DPT_TRIANGLELIST,
					primitive_count=triangle_count * 3,
					triangle_count=triangle_count,
					first_index=first_index,
					first_vertex=first_vertex,
					vertex_count=last_vertex - first_vertex + 1,
					index_buffer=index_buffer
				)
				mesh.vertex_buffers.append(vertex_buffer)

				mesh_link = rw4_base.MeshCompiledStateLink(
					render_ware,
					mesh=mesh
				)

				compiled_state = rw4_base.CompiledState(
					render_ware
				)
				mesh_link.compiled_states.append(compiled_state)

				material_data = blender_material.material.rw4
				active_material = rw4_material_config.get_active_material(material_data)

				if active_material is not None:
					material_builder = active_material.material_class.get_material_builder(self, material_data)

					material_builder.vertex_description = vertex_desc
					material_builder.primitive_type = rw4_enums.D3DPT_TRIANGLELIST

					material_builder.write(render_ware, compiled_state.data)

				# Add all the objects we just created
				render_ware.add_object(mesh)
				render_ware.add_object(mesh_link)
				render_ware.add_object(compiled_state)

		index_buffer.index_data = rw4_base.BaseResource(
			render_ware,
			data=write_index_buffer(index_data, index_buffer.format)
		)

		# Add all the objects we just created
		render_ware.add_object(index_buffer)
		render_ware.add_object(index_buffer.index_data)
		render_ware.add_object(vertex_desc)

		# Add required things for TriangleKDTreeProcedural

		# How many vertices have previous objects added?
		previous_vertex_count = len(self.vertices)
		# Copy so it doesn't get deleted when removing temporary mesh
		self.vertices += [(v[0], v[1], v[2]) for v in vertices['position']]

		for i in range(0, len(index_data), 3):
			self.triangles.append((index_data[i] + previous_vertex_count,
								   index_data[i+1] + previous_vertex_count,
								   index_data[i+2] + previous_vertex_count,
								   0))
			self.triangle_unknowns.append(choice(range(1, 13, 2)))

	def create_animation_skin(self, b_bone):
		pose = rw4_base.AnimationSkin.BonePose()
		pose.matrix = b_bone.matrix_local.to_3x3()
		pose.translation = b_bone.matrix_local.inverted().to_translation()

		self.bones_skin[b_bone.name] = pose

		return pose

	def process_bone(self, bbone, parent):
		bone = rw4_base.SkeletonBone(file_io.get_hash(bbone.name), 0, parent)

		if bbone.parent is None:
			bone.flags = rw4_base.SkeletonBone.TYPE_ROOT
		else:
			# If it's a leaf (no children)
			if not bbone.children:
				# If it's not the only children
				if len(bbone.parent.children) > 1:
					bone.flags = rw4_base.SkeletonBone.TYPE_BRANCH_LEAF
				else:
					bone.flags = rw4_base.SkeletonBone.TYPE_LEAF

			# If it's not the only children
			elif len(bbone.parent.children) > 1:
				bone.flags = rw4_base.SkeletonBone.TYPE_BRANCH
			else:
				bone.flags = rw4_base.SkeletonBone.TYPE_ROOT

		self.skin_matrix_buffer.data.append(Matrix.Identity(4))
		self.animation_skin.data.append(self.create_animation_skin(bbone))

		self.skeleton.bones.append(bone)

		for child in bbone.children:
			self.process_bone(child, bone)

	def export_armature_object(self, obj):
		if self.b_armature_object is not None:
			error = rw4_validation.error_armature_limit()
			if error not in self.warnings:
				self.warnings.add(error)
			return

		self.b_armature_object = obj
		b_armature = self.b_armature_object.data

		render_ware = self.render_ware

		self.skin_matrix_buffer = rw4_base.SkinMatrixBuffer(
			render_ware
		)

		self.skeleton = rw4_base.Skeleton(
			render_ware,
			skeleton_id=file_io.get_hash(self.b_armature_object.name)
		)

		self.animation_skin = rw4_base.AnimationSkin(
			render_ware
		)

		skins_ink = rw4_base.SkinsInK(
			render_ware,
			skin_matrix_buffer=self.skin_matrix_buffer,
			skeleton=self.skeleton,
			animation_skin=self.animation_skin,
		)

		already_processed = False
		for bbone in b_armature.bones:
			if bbone.parent is None:
				if not already_processed:
					self.process_bone(bbone, None)
					already_processed = True
					if bbone.head != Vector((0.0, 0.0, 0.0)):
						error = rw4_validation.error_root_bone_not_origin()
						if error not in self.warnings:
							self.warnings.add(error)
				else:
					error = rw4_validation.error_root_bone_limit()
					if error not in self.warnings:
						self.warnings.add(error)

		render_ware.add_object(self.skin_matrix_buffer)
		render_ware.add_object(self.skeleton)
		render_ware.add_object(self.animation_skin)
		render_ware.add_object(skins_ink)

		render_ware.add_sub_reference(self.skin_matrix_buffer, 16)

	def process_blend_shape_action(self, action, keyframe_anim):
		"""
		Processes a shape key action to fill the data of the KeyframeAnim.
		All blend shape channels will be added to the animation; if one is not keyframed in the action,
		it will be added with 0.0 influence.
		:param action: The Blender action to export.
		:param keyframe_anim: The keyframe anim where the data will be written.
		"""
		shape_ids = self.blend_shape.shape_ids
		
		# Even though the RW anim channel has a shape ID field, Spore only seems to care about the order
		# So first collect the fcurves, then add shape key channels in order
		fcurves_by_id = {}
		
		# Shape keys don't use groups
		for fcurve in action.fcurves:
			match = re.search(r'\["([a-zA-Z_\-\s0-9.]+)"\]', fcurve.data_path)
			channel_id = file_io.get_hash(match.group(1))
			
			if channel_id not in shape_ids:
				error = rw4_validation.error_action_with_missing_shapes(action, match.group(1))
				if error not in self.warnings:
					self.warnings.add(error)
				continue
			
			fcurves_by_id[channel_id] = fcurve
			
		for channel_id in shape_ids:
			if channel_id in fcurves_by_id:
				fcurve = fcurves_by_id[channel_id]
				# Ensure keyframes are sorted in chronological order and handles are set correctly
				fcurve.update()
				
				channel = rw4_base.AnimationChannel()
				channel.keyframe_class = rw4_base.BlendFactorKeyframe
				channel.channel_id = channel_id
				keyframe_anim.channels.append(channel)
				
				for i, b_keyframe in enumerate(fcurve.keyframe_points):
					time = b_keyframe.co[0] / rw4_base.KeyframeAnim.FPS
					value = fcurve.evaluate(b_keyframe.co[0])

					if i == 0 and time != 0.0:
						# Ensure the first keyframe is at 0.0, just in case
						# It will have the same value as this one
						keyframe = channel.new_keyframe(0.0)
						keyframe.factor = value

					keyframe = channel.new_keyframe(time)
					keyframe.factor = value

					if i == len(fcurve.keyframe_points)-1 and time != keyframe_anim.length:
						# Ensure the last keyframe is at 'length', just in case
						# It will have the same value as this one
						keyframe = channel.new_keyframe(keyframe_anim.length)
						keyframe.factor = value
					
			else:
				# We still need a channel for it
				channel = rw4_base.AnimationChannel()
				channel.keyframe_class = rw4_base.BlendFactorKeyframe
				channel.channel_id = channel_id
				keyframe_anim.channels.append(channel)

				#TODO maybe they should use the real weight instead of 0.0
				channel.new_keyframe(0.0).factor = 0.0
				channel.new_keyframe(keyframe_anim.length).factor = 0.0


	def process_skeleton_action(self, action, keyframe_anim):
		# 1. Get all possible keyframe times
		keyframe_times = {0}  # Ensure frame 0 is always there
		for group in action.groups:
			for channel in group.channels:
				for kf in channel.keyframe_points:
					keyframe_times.add(int(kf.co[0]))

		keyframe_times = sorted(keyframe_times)

		# 2. We need the final model space transformations used by the shader
		# We will keep the 'm' used in the importer
		keyframe_poses = {}
		for time in keyframe_times:
			bpy.context.scene.frame_set(time)

			poses = {}
			for name, skin in self.bones_skin.items():
				pose_bone = self.b_armature_object.pose.bones[name]

				# In importer:  world_r = m @ skin.matrix.inverted()
				# In importer:  world_t = t + (m @ skin.translation)
				world_r = pose_bone.matrix.to_3x3() @ pose_bone.bone.matrix_local.to_3x3().inverted()

				# in vertex shader, final pos would be world_r @ pos
				# we need to move it to pose_bone.matrix.to_translation()
				final_pos = world_r @ pose_bone.bone.head_local
				world_t = pose_bone.matrix.to_translation() - final_pos

				m = world_r @ skin.matrix
				t = world_t - (m @ skin.translation)

				poses[name] = rw4_base.AnimationSkin.BonePose(matrix=m, translation=t)

			keyframe_poses[time] = poses

		# 3. Create the channels
		channels = {}
		for name in self.bones_skin:
			channel = rw4_base.AnimationChannel(rw4_base.LocRotScaleKeyframe)
			channel.channel_id = file_io.get_hash(name)
			keyframe_anim.channels.append(channel)
			channels[name] = channel

		# 4. Add all the keyframes:
		for time, poses in keyframe_poses.items():
			scales = {}
			for name, pose in poses.items():
				keyframe = channels[name].new_keyframe(time / rw4_base.KeyframeAnim.FPS)

				parent_bone = self.b_armature_object.pose.bones[name].parent
				if parent_bone is None:
					parent_pose = rw4_base.AnimationSkin.BonePose()
					parent_inv_scale = Vector((1, 1, 1))
				else:
					parent_pose = poses[parent_bone.name]
					s = scales[parent_bone.name]
					parent_inv_scale = Vector((1.0 / s[0], 1.0 / s[1], 1.0 / s[2]))

				m = pose.matrix
				t = pose.translation

				# In importer:  m = parent_rot @ scaled_m
				scaled_m = parent_pose.matrix.inverted() @ m

				# In importer:  scaled_m = parent_inv_scale @ (pose_bone.r.to_matrix() @ scale_matrix)
				scaled_m = Matrix.Diagonal(parent_inv_scale).inverted() @ scaled_m
				keyframe.rot = scaled_m.to_quaternion()
				keyframe.scale = scaled_m.to_scale()
				scales[name] = keyframe.scale

				# In importer:  t = parent_rot @ pose_bone.t + parent_loc
				keyframe.loc = parent_pose.matrix.inverted() @ (t - parent_pose.translation)

		# for name, pose in keyframe_poses[30].items():
		#     m = pose.matrix
		#     t = pose.translation
		#     skin = self.bones_skin[name]
		#
		#     dst_r = m @ skin.matrix.inverted()
		#     dst_t = t + (m @ skin.translation)
		#
		#     for i in range(3):
		#         print(f"skin_bones_data += struct.pack('ffff', {dst_r[i][0]}, {dst_r[i][1]}, {dst_r[i][2]}, {dst_t[i]})")

	def export_actions(self, use_morphs = True):

		animations_list = rw4_base.Animations(self.render_ware)

		original_skeleton_action = None
		if self.b_armature_object is not None and self.b_armature_object.animation_data is not None:
			original_skeleton_action = self.b_armature_object.animation_data.action

		# TODO: Allow for armatures and shape keys with the same name and length to be combined into one KeyframeAnim.
		# Throw an error if they have the same name but different lengths.
		for action in bpy.data.actions:
			if not action.fcurves:
				continue

			if action.frame_range[0] != 0:
				error = rw4_validation.error_action_start_frame(action)
				if error not in self.warnings:
					self.warnings.add(error)

			if not action.use_fake_user:
				error = rw4_validation.error_action_no_fake(action)
				if error not in self.warnings:
					self.warnings.add(error)

			is_shape_key = action.id_root == 'KEY'

			if not is_shape_key:
				# If there is no armature using the action (and it's not shape key) then throw error
				if action not in self.b_armature_actions:
					error = rw4_validation.error_action_but_no_armature(action)
					if error not in self.warnings:
						self.warnings.add(error)
					continue

				# If the animation belongs to another armature, then it's in another collection and we can ignore it
				if self.b_armature_actions[action] != self.b_armature_object:
					continue
			else:
				if action not in self.b_shape_keys_actions:
					error = rw4_validation.error_action_but_no_object(action)
					if error not in self.warnings:
						self.warnings.add(error)
					continue

				# If the animation does not use any of our meshes, then it's in another collection and we can ignore it
				if self.b_shape_keys_actions[action] not in self.b_mesh_objects:
					continue

			if is_shape_key and self.blend_shape is not None or self.b_armature_object is not None:
				skeleton_id = self.blend_shape.id if is_shape_key else file_io.get_hash(self.b_armature_object.name)

			keyframe_anim = rw4_base.KeyframeAnim(self.render_ware)
			keyframe_anim.skeleton_id = skeleton_id
			keyframe_anim.length = action.frame_range[1] / rw4_base.KeyframeAnim.FPS
			keyframe_anim.flags = 3

			if is_shape_key:
				self.process_blend_shape_action(action, keyframe_anim)
			else:
				self.b_armature_object.animation_data.action = action
				self.process_skeleton_action(action, keyframe_anim)

			# Remove trailing numbers from action name
			action_name = action.name.split('.')[0]

			# Now, either add to animations list or to handles
			if action.rw4 is not None and action.rw4.is_morph_handle:
				if use_morphs: # If not using morphs (LOD1), skip this
					handle = rw4_base.MorphHandle(self.render_ware)
					handle.handle_id = file_io.get_hash(action_name)
					handle.start_pos = action.rw4.initial_pos
					handle.end_pos = action.rw4.final_pos
					handle.default_progress = action.rw4.default_progress / 100.0
					handle.animation = keyframe_anim

					self.render_ware.add_object(handle)

			else:
				animations_list.add(file_io.get_hash(action_name), keyframe_anim)

			self.render_ware.add_object(keyframe_anim)

		if animations_list.animations:
			self.render_ware.add_object(animations_list)
			self.render_ware.add_sub_reference(animations_list, 8)

		if original_skeleton_action is not None:
			self.b_armature_object.animation_data.action = original_skeleton_action

	def calc_global_bbox(self):
		"""
		:return: The bounding box that contains all exported mesh objects.
		"""
		min_bbox = self.b_mesh_objects[0].bound_box[0]
		max_bbox = self.b_mesh_objects[0].bound_box[6]
		min_bbox = [min_bbox[0], min_bbox[1], min_bbox[2]]
		max_bbox = [max_bbox[0], max_bbox[1], max_bbox[2]]

		for obj in self.b_mesh_objects[1:]:
			min_point = obj.bound_box[0]
			max_point = obj.bound_box[6]

			for i in range(3):
				if min_point[i] < min_bbox[i]:
					min_bbox[i] = min_point[i]

				if max_point[i] < max_bbox[i]:
					max_bbox[i] = max_point[i]

		return [min_bbox, max_bbox]

	def export_bbox(self):
		"""
		Exports a BoundingBox object which contains the bounding boxes of all exported meshes.
		This must be called after the meshes have been exported.
		"""
		if self.b_mesh_objects:
			self.bound_box = rw4_base.BoundingBox(
				self.render_ware,
				bound_box=self.calc_global_bbox()
			)
			self.render_ware.add_object(self.bound_box)

	def export_kdtree(self):
		"""
		Creates and exports the TriangleKDTreeProcedural based on the data collected from exported meshes.
		This must be called after the meshes and the bounding box have been exported.
		"""
		kdtree = rw4_base.TriangleKDTreeProcedural(self.render_ware)
		kdtree.bound_box = self.bound_box
		kdtree.bound_box_2 = self.bound_box
		kdtree.triangles = self.triangles
		kdtree.vertices = self.vertices
		kdtree.triangle_unknowns = self.triangle_unknowns

		self.render_ware.add_object(kdtree)

# Bit of a disgusting hack. Split the object along sharps, and store to be reset later.
split_object_meshes = {}
def split_object(obj):
	import bmesh

	editormode = bpy.context.object.mode
	# Ensure we're in object mode before editing mesh data
	if bpy.context.object and editormode != 'OBJECT':
		bpy.ops.object.mode_set(mode='OBJECT')
	
	bm = bmesh.new()
	bm_old = bmesh.new()
	bm.from_mesh(obj.data)
	bm_old.from_mesh(obj.data)

	sharp_edges = [e for e in bm.edges if not e.smooth]
	if sharp_edges:
		bmesh.ops.split_edges(bm, edges=sharp_edges)
		bm.to_mesh(obj.data)
	bm.free()
	split_object_meshes[obj] = bm_old
	# Restore Mode
	bpy.ops.object.mode_set(mode=editormode)

def remerge_objects():
	editormode = bpy.context.object.mode
	# Ensure we're in object mode before editing mesh data
	if bpy.context.object and editormode != 'OBJECT':
		bpy.ops.object.mode_set(mode='OBJECT')
	
	for obj in split_object_meshes.keys():
		split_object_meshes[obj].to_mesh(obj.data)
	split_object_meshes.clear()

	# Restore Mode
	bpy.ops.object.mode_set(mode=editormode)


def export_rw4(file, export_symmetric, export_as_lod1):
	# NOTE: We might not use Spore's conventional ordering of RW objects, since it's a lot easier to do it this way.
	# Theoretically, this has no effect on the game so it should work fine.

	current_keyframe = bpy.context.scene.frame_current
	exporter = RW4Exporter()

	# Set active collection, or fall back to scene collection if missing or empty.
	active_collection = bpy.context.view_layer.active_layer_collection.collection
	if not active_collection or active_collection is None or not active_collection.all_objects:
		active_collection = bpy.context.scene.collection
	if not active_collection.all_objects:
		show_message_box("No objects to export in the active collection.",
						 title="Export Error", icon="ERROR")
		return {'CANCELLED'}

	# Detect if just one mesh and its armature are present. Used for gathering actions
	mesh_count = 0
	for obj in bpy.context.scene.objects:
		if obj.type == 'MESH':
			for mod in obj.modifiers:
				if mod.type == 'ARMATURE' and mod.object is not None:
					mesh_count += 1

	# For collections, we need to know what each action animates
	for obj in active_collection.all_objects:
		if obj.type == 'ARMATURE':
			ad = obj.animation_data
			if ad:
				if ad.action:
					exporter.b_armature_actions[ad.action] = obj
				# If there is only one mesh, we can assume it uses all actions except those marked null
				if mesh_count == 1:
					for action in bpy.data.actions:
						# Disallow null actions
						if action in exporter.b_armature_actions and exporter.b_armature_actions[action].name.lower().startswith("null"):
							continue
						exporter.b_armature_actions[action] = obj
				# If there are multiple meshes, we need to check the NLA tracks
				else:
					for t in ad.nla_tracks:
						for s in t.strips:
							exporter.b_armature_actions[s.action] = obj
		
		if obj.type == 'MESH':
			# Do not export hidden meshes
			if obj.hide_get(): 
				continue
			elif obj.data.shape_keys and obj.data.shape_keys.animation_data:
				ad = obj.data.shape_keys.animation_data
				if ad.action:
					exporter.b_shape_keys_actions[ad.action] = obj
				# One mesh, pull actions
				if mesh_count == 1:
					for action in bpy.data.actions:
						# Disallow null actions
						if action in exporter.b_shape_keys_actions and exporter.b_shape_keys_actions[action].name.lower().startswith("null"):
							continue
						exporter.b_shape_keys_actions[action] = obj
				# Multiple meshes, check the NLA tracks
				else:
					for t in ad.nla_tracks:
						for s in t.strips:
							exporter.b_shape_keys_actions[s.action] = obj
			split_object(obj)

	# First process and export the skeleton (if any)
	for obj in active_collection.all_objects:
		if obj.type == 'ARMATURE':
			exporter.export_armature_object(obj)

	for obj in active_collection.all_objects:
		if obj.type == 'MESH':
			# Do not export hidden meshes
			if not obj.hide_get():
				exporter.export_mesh_object(obj)

	exporter.export_bbox()
	exporter.export_kdtree()
	exporter.export_actions(use_morphs = not export_as_lod1)
	exporter.render_ware.write(file_io.FileWriter(file))

	# Export symmetric variant of this model and these actions
	if export_symmetric:
		export_rw4_symmetric(file, active_collection, exporter.b_armature_actions, exporter.b_shape_keys_actions, export_as_lod1)

	# Reset frame
	bpy.context.scene.frame_set(current_keyframe)
	# Fix split meshes
	remerge_objects()

	if exporter.warnings:
		show_multi_message_box(exporter.warnings, title=f"Exported with {len(exporter.warnings)} warnings", icon="ERROR")

	return {'FINISHED'}




def export_rw4_symmetric(file, active_collection, armature_actions, shape_keys_actions, export_as_lod1):
	# Mirrors the active collection's meshes and armatures across X axis,
	# flips face normals, and mirrors armature action bone keyframes

	# Store the current selection for later restoration
	current_selection = bpy.context.active_object

	# Create and return a temporary mesh object
	def mirror_mesh_object(obj):
		mirrored_obj = obj.copy()
		mirrored_obj.data = obj.data.copy()
		mirrored_obj.name = obj.name + "_Sym"
		mirrored_obj.parent = None

		# Scale x by -1 and apply transforms
		mirrored_obj.scale.x *= -1
		bpy.context.scene.collection.objects.link(mirrored_obj)
		bpy.context.view_layer.update()
		# Select and apply transform only after linking
		bpy.ops.object.select_all(action='DESELECT')
		mirrored_obj.select_set(True)
		bpy.context.scene.view_layers[0].objects.active = mirrored_obj
		bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
		# Flip normals
		bpy.context.view_layer.objects.active = mirrored_obj
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.select_all(action='SELECT')
		bpy.ops.mesh.flip_normals()
		bpy.ops.object.mode_set(mode='OBJECT')

		return mirrored_obj


	def mirror_armature_object(obj):
		mirrored_obj = obj.copy()
		mirrored_obj.data = obj.data.copy()
		mirrored_obj.name = obj.name + "_Sym"

		# Scale x by -1 and apply transforms
		mirrored_obj.scale.x *= -1
		bpy.context.scene.collection.objects.link(mirrored_obj)
		#bpy.context.view_layer.update()
		bpy.ops.object.select_all(action='DESELECT')
		mirrored_obj.select_set(True)
		bpy.context.scene.view_layers[0].objects.active = mirrored_obj
		bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
		return mirrored_obj


	def mirror_action(action, armature_obj):
		# Mirrors keyframes in the armature action, and only for the bones that have keyframes.
		# Uses Blender's built-in pose flipping for accuracy.

		# Work on a copy of the action (action.001)
		mirrored_action = action.copy()
		mirrored_action.name = action.name + ".001"

		# Assign the new action to the armature
		if not armature_obj.animation_data:
			armature_obj.animation_data_create()
		armature_obj.animation_data.action = mirrored_action

		# Pose mode
		armature_obj.select_set(True)
		bpy.context.view_layer.objects.active = armature_obj
		bpy.ops.object.mode_set(mode='POSE')

		# Collect all keyed bones and their keyed frames
		bone_keyframes = {}
		for fcurve in mirrored_action.fcurves:
			if fcurve.data_path.startswith('pose.bones'):
				bone_name = fcurve.data_path.split('"')[1]
				if bone_name not in bone_keyframes:
					bone_keyframes[bone_name] = set()
				for kf in fcurve.keyframe_points:
					bone_keyframes[bone_name].add(int(kf.co[0]))

		all_keyed_frames = set()
		for frames in bone_keyframes.values():
			all_keyed_frames.update(frames)
		all_keyed_frames = sorted(all_keyed_frames)

		for frame in all_keyed_frames:
			bpy.context.scene.frame_set(frame)
			bpy.ops.pose.select_all(action='DESELECT')
			# Only select bones that have a keyframe at this frame
			for bone_name, frames in bone_keyframes.items():
				if frame in frames:
					pb = armature_obj.pose.bones.get(bone_name)
					if pb:
						pb.bone.select = True
			if any(pb.bone.select for pb in armature_obj.pose.bones):
				bpy.ops.pose.copy()
				bpy.ops.pose.paste(flipped=True)
				for pb in armature_obj.pose.bones:
					if pb.bone.select:
						pb.keyframe_insert(data_path="location")
						pb.keyframe_insert(data_path="rotation_quaternion")
						pb.keyframe_insert(data_path="rotation_euler")
						pb.keyframe_insert(data_path="scale")
			bpy.ops.pose.select_all(action='DESELECT')

		# Remove the mirrored action from the armature
		armature_obj.animation_data.action = action

		return mirrored_action


	# Duplicate and mirror objects
	mirrored_objs = []
	mirrored_armatures = []
	mirrored_actions = {}
	mirrored_shape_actions = {}

	# Mirror meshes in collection
	for obj in active_collection.all_objects:
		if obj.type == 'MESH':
			mirrored_mesh = mirror_mesh_object(obj)
			mirrored_objs.append(mirrored_mesh)
			# Pull keys
			if obj.data.shape_keys and obj.data.shape_keys.animation_data:
				for item in shape_keys_actions:
					if shape_keys_actions[item] == obj:
						mirrored_shape_actions[item] = mirrored_mesh # no need to mirror since mesh is mirrored

	# Mirror armatures in collection
	for obj in active_collection.all_objects:
		if obj.type == 'ARMATURE':
			mirrored_arm = mirror_armature_object(obj)
			mirrored_armatures.append(mirrored_arm)
			# Mirror armature actions
			if obj.animation_data:
				for item in armature_actions:
					if armature_actions[item] == obj:
						act = mirror_action(item, mirrored_arm)
						mirrored_actions[act] = mirrored_arm

	# Start exporting
	exporter_sym = RW4Exporter()
	exporter_sym.b_armature_actions = mirrored_actions
	exporter_sym.b_shape_keys_actions = mirrored_shape_actions

	for arm in mirrored_armatures:
		exporter_sym.export_armature_object(arm)
	for mesh in mirrored_objs:
		exporter_sym.export_mesh_object(mesh)
	exporter_sym.export_bbox()
	exporter_sym.export_kdtree()
	exporter_sym.export_actions(use_morphs = not export_as_lod1)

	# Write symmetric model to file (append -symmetric)
	sym_file_path = None
	if hasattr(file, 'name'):
		import os
		base, ext = os.path.splitext(file.name)
		sym_file_path = base + "-symmetric" + ext

	with open(sym_file_path, 'wb') as sym_file:
		exporter_sym.render_ware.write(file_io.FileWriter(sym_file))

	# Restore the original selection
	if current_selection and current_selection.name in bpy.data.objects:
		bpy.context.view_layer.objects.active = bpy.data.objects[current_selection.name]
	else:
		bpy.context.view_layer.objects.active = None

	# Remove the duplicate symmetric data
	for obj in mirrored_objs + mirrored_armatures:
		bpy.data.objects.remove(obj, do_unlink=True)
	
	for action in mirrored_actions:
		# Unlink from all objects
		for obj in bpy.data.objects:
			if obj.animation_data and obj.animation_data.action == action:
				obj.animation_data.action = None
		# Unlink from NLA tracks
		for obj in bpy.data.objects:
			if obj.animation_data and obj.animation_data.nla_tracks:
				for track in obj.animation_data.nla_tracks:
					for strip in track.strips:
						if strip.action == action:
							strip.action = None
		bpy.data.actions.remove(action, do_unlink=True)
