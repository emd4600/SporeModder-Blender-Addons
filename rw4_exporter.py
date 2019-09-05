__author__ = 'Eric'

import bpy
from . import rw4_base, rw4_enums, file_io
from . import rw4_material_config
from mathutils import Matrix, Quaternion, Vector
from random import choice


def show_message_box(message: str, title: str, icon='ERROR'):
    def draw(self, context):
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


def create_skin_matrix_buffer():
    matrix = rw4_base.RWMatrix(3, 4)

    for i in range(3):
        for j in range(4):
            matrix[i][j] = 0.0
        matrix[i][i] = 1.0

    return matrix


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


class RW4Exporter:
    class BaseBone:
        def __init__(self, absBindPose, invPoseTranslation):
            self.abs_bind_pose = absBindPose
            self.inv_pose_translation = invPoseTranslation

    def __init__(self):
        self.render_ware = rw4_base.RenderWare4()
        self.added_textures = {}

        self.b_armature_object = None
        self.b_mesh_objects = []

        self.bone_bases = {}

        self.skin_matrix_buffer = None

        self.render_ware.header.rw_type_code = rw4_enums.RW_MODEL

        self.bound_box = None

        # for TriangleKDTreeProcedural
        self.triangles = []
        self.vertices = []
        self.triangle_unknowns = []

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

    def add_texture(self, path):
        """
        Adds a texture to be exported in the RenderWare4. Only DXT5 DDS textures are supported.
        If the path has already been exported, no new object is created.

        :param path: File path to the .dds texture.
        :return: The Raster object created for this texture.
        """

        if path in self.added_textures:
            return self.added_textures[path]

        raster = rw4_base.Raster(self.render_ware)
        data_buffer = rw4_base.BaseResource(self.render_ware)

        if path is None or not path:
            # Just create an empty texture
            raster.width = 64
            raster.height = 64
            raster.mipmap_levels = 7
            raster.texture_format = rw4_enums.D3DFMT_DXT5

            data_buffer.data = bytearray(5488)  # ?

        else:
            try:
                with open(bpy.path.abspath(path), 'rb') as file:
                    dds_texture = rw4_base.DDSTexture()
                    dds_texture.read(file_io.FileReader(file))

                    raster.from_dds(dds_texture)
                    data_buffer.data = dds_texture.data
            except OSError as e:
                #TODO convert to warning
                show_message_box(str(e), "Texture Error")

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

    def process_vertex_bones(self, obj, b_vertex, vertex_dict):
        """
        Adds the bone indices and weights of the given vertex into the vertex attributes.

        :param obj: The Blender mesh object.
        :param b_vertex: The Blender vertex.
        :param vertex_dict: A dictionary of vertex attributes lists.
        """
        indices = []
        weights = []
        size = 0
        for gr in b_vertex.groups:
            for index, b_bone in enumerate(self.b_armature_object.data.bones):
                if b_bone.name == obj.vertex_groups[gr.group].name:
                    indices.append(index * 3)
                    weights.append(round(gr.weight * 255))

                    size += 1
                    if size == 4:
                        break

        for i in range(size, 4):
            indices.append(0)
            weights.append(0)

        # Special case: if there are no bone weights, we must do this or the model will be invisible
        if size == 0:
            weights[0] = 255

        vertex_dict['blendIndices'].append(indices)
        vertex_dict['blendWeights'].append(weights)

    def process_mesh(self, obj, mesh, use_texcoord, use_bones):
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
        :returns: A tuple of (vertices, triangles, indices_map)
        """
        # The result; triangles are (i, j, k, material_index)
        triangles = [None] * len(mesh.polygons)
        positions = []
        normals = []
        texcoords = []
        indices_map = []
        vertices = {'position': positions, 'normal': normals}

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
                    self.process_vertex_bones(obj, b_vertex, vertices)

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
                        if uv[0] == uv_data[i].uv[0] and uv[1] == uv_data[i].uv[1]:
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
                            self.process_vertex_bones(obj, b_vertex, vertices)

                        indices_map.append(index)
                        triangles[t][i - face.loop_start] = current_processed_index
                        new_vertex_indices[index].append(current_processed_index)
                        current_processed_index += 1

            vertices['texcoord0'] = texcoords
            calculate_tangents(vertices, triangles)

        # blendIndices and blendWeights are already added by process_vertex_bones()

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
        Exports a lsit of vertices as a vertex buffer. This will add to the RW4
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
        blend_shape = rw4_base.BlendShape(
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
                    data.pack('<fff', *v)
                    data.write_int(0)

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
            blend_shape_buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_BLENDINDICES] = data.tell()
            for v in vertices['blendIndices']:
                data.pack('<HHHH', *v)

        if 'blendWeights' in vertices:
            blend_shape_buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_BLENDWEIGHTS] = data.tell()
            for v in vertices['blendWeights']:
                data.pack('<ffff', *v)

        blend_shape_buffer.data = data.buffer
        self.render_ware.add_object(blend_shape)
        self.render_ware.add_object(blend_shape_buffer)

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

        use_shape_keys = obj.data.shape_keys is not None and len(obj.data.shape_keys.key_blocks) > 1
        #TODO throw warning if use_shape_keys and self.b_mesh_objects

        blender_mesh = obj.to_mesh()
        mesh_triangulate(blender_mesh)
        self.b_mesh_objects.append(obj)

        use_texcoord = blender_mesh.uv_layers.active is not None
        use_bones = self.b_armature_object is not None

        # For each object, create a vertex and index buffer

        # When there is BlendShape, Spore does not add the bone indices to the vertex format, I don't know why
        #TODO and in the material?
        vertex_desc = self.create_vertex_description(use_texcoord, use_bones and not use_shape_keys)

        vertices, triangles, indices_map = self.process_mesh(obj, blender_mesh, use_texcoord, use_bones)

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
        pose.abs_bind_pose = b_bone.matrix_local.to_3x3()
        pose.inv_pose_translation = b_bone.matrix_local.inverted().to_translation()

        base = RW4Exporter.BaseBone(pose.abs_bind_pose, pose.inv_pose_translation)
        self.bone_bases[b_bone.name] = base

        return pose

    def export_armature_object(self, obj):
        if self.b_armature_object is not None:
            raise NameError("Only one skeleton supported.")

        self.b_armature_object = obj
        b_armature = self.b_armature_object.data

        render_ware = self.render_ware

        self.skin_matrix_buffer = rw4_base.SkinMatrixBuffer(
            render_ware
        )

        skeleton = rw4_base.Skeleton(
            render_ware,
            skeleton_id=file_io.get_hash(self.b_armature_object.name)
        )

        animation_skin = rw4_base.AnimationSkin(
            render_ware
        )

        skins_ink = rw4_base.SkinsInK(
            render_ware,
            skin_matrix_buffer=self.skin_matrix_buffer,
            skeleton=skeleton,
            animation_skin=animation_skin,
        )

        # blender bone -> Spore bone
        bbone_to_bone = {}

        for bbone in b_armature.bones:
            bone = rw4_base.SkeletonBone(0, 0, None)
            bone.name = file_io.get_hash(bbone.name)

            if bbone.parent is not None:
                bone.parent = bbone_to_bone[bbone.parent]

            # calculate flags
            if bbone.parent is not None:
                # if no children
                if len(bbone.children) == 0:
                    # if it's not the only children
                    if len(bbone.parent.children) > 1:
                        bone.flags = 3
                    else:
                        bone.flags = 1

                elif len(bbone.children) == 1:
                    bone.flags = 2

            else:
                bone.flags = 0

            self.skin_matrix_buffer.data.append(create_skin_matrix_buffer())
            animation_skin.data.append(self.create_animation_skin(bbone))

            bbone_to_bone[bbone] = bone

            skeleton.bones.append(bone)

        render_ware.add_object(self.skin_matrix_buffer)
        render_ware.add_object(skeleton)
        render_ware.add_object(animation_skin)
        render_ware.add_object(skins_ink)

        render_ware.add_sub_reference(self.skin_matrix_buffer, 16)

    def get_total_translation(self, pose_bone):
        if pose_bone.parent is None:
            return self.get_bone_translation(pose_bone)
        else:
            return self.get_bone_translation(pose_bone) + self.get_total_translation(pose_bone.parent)

    def get_bone_translation(self, pose_bone):
        # before: using matrix_basis
        # that didn't translate child bones when moving a root in a chain, however
        #         if pose_bone.parent is None:
        #             return pose_bone.matrix_basis.to_translation() - self.bone_bases[pose_bone.name].inv_pose_translation
        #         else:
        #             return pose_bone.matrix_basis.to_translation() - (self.bone_bases[pose_bone.name].inv_pose_translation + self.get_total_translation(pose_bone.parent))
        #         if pose_bone.parent is None:
        #             return pose_bone.matrix_basis.to_translation() - self.bone_bases[pose_bone.name].inv_pose_translation
        #         else:
        #             return -(self.bone_bases[pose_bone.name].inv_pose_translation + self.get_total_translation(pose_bone.parent)) - pose_bone.matrix_channel.to_translation()

        if pose_bone.parent is None:
            return pose_bone.matrix_basis.to_translation() - self.bone_bases[pose_bone.name].inv_pose_translation
        else:
            return pose_bone.parent.matrix.inverted() @ pose_bone.matrix.to_translation()

    def get_total_rotation(self, pose_bone):
        if pose_bone.parent is None:
            return self.get_bone_rotation(pose_bone)
        else:
            # return self.get_bone_rotation(pose_bone) * self.get_total_rotation(pose_bone.parent)
            return self.get_total_rotation(pose_bone.parent) @ self.get_bone_rotation(pose_bone)

    def get_bone_rotation(self, pose_bone):
        if pose_bone.parent is None:
            return pose_bone.matrix.to_quaternion()
        else:
            # rotation = pose_bone.rotation_quaternion * self.bone_bases[pose_bone.parent.name].abs_bind_pose.to_quaternion().inverted()
            # rotation = pose_bone.matrix.to_quaternion() * self.bone_bases[pose_bone.parent.name].abs_bind_pose.to_quaternion().inverted() * pose_bone.parent.rotation_quaternion
            return self.get_total_rotation(pose_bone.parent).inverted() @ pose_bone.matrix.to_quaternion()

    def export_actions(self):
        if self.b_armature_object is None:
            return

        render_ware = self.render_ware

        animations_list = rw4_base.Animations(render_ware)

        current_keyframe = bpy.context.scene.frame_current

        for b_action in bpy.data.actions:
            if len(b_action.fcurves) == 0:
                continue

            self.b_armature_object.animation_data.action = b_action

            keyframe_anim = rw4_base.KeyframeAnim(render_ware)
            keyframe_anim.skeleton_id = file_io.get_hash(self.b_armature_object.name)
            keyframe_anim.length = b_action.frame_range[1] / rw4_base.KeyframeAnim.frames_per_second
            keyframe_anim.flags = 3

            # Now, either add to animations list or to handles
            if b_action.rw4 is not None and b_action.rw4.is_morph_handle:
                handle = rw4_base.MorphHandle(render_ware)
                handle.handle_id = file_io.get_hash(b_action.name)
                handle.start_pos = b_action.rw4.initial_pos
                handle.end_pos = b_action.rw4.final_pos
                handle.default_time = b_action.rw4.default_frame / b_action.frame_range[1]
                handle.animation = keyframe_anim

                render_ware.add_object(handle)

            else:
                animations_list.add(file_io.get_hash(b_action.name), keyframe_anim)

            render_ware.add_object(keyframe_anim)
            # render_ware.objects.insert(0, keyframe_anim)

            for group in b_action.groups:
                pose_bone = None
                for b in self.b_armature_object.pose.bones:
                    if b.name == group.name:
                        pose_bone = b

                if pose_bone is None:
                    show_message_box(f"Animation '{b_action.name}' has keyframes for unknown bone '{group.name}'",
                                     "Animation Error")
                    return

                base_bone = self.bone_bases[group.name]

                channel = rw4_base.AnimationChannel(rw4_base.LocRotScaleKeyframe)  # TODO
                channel.channel_id = file_io.get_hash(group.name)
                keyframe_anim.channels.append(channel)

                bpy.context.scene.frame_set(0)

                for kf in group.channels[0].keyframe_points:
                    bpy.context.scene.frame_set(int(kf.co[0]))

                    keyframe = channel.new_keyframe(kf.co[0] / rw4_base.KeyframeAnim.frames_per_second)

                    # baseTransform * keyframeTransform = finalTransform
                    # blenderKeyframe = finalTranform ?

                    # translation = pose_bone.matrix.to_translation()

                    translation = self.get_bone_translation(pose_bone)

                    scale = pose_bone.matrix.to_scale()

                    rotation = self.get_bone_rotation(pose_bone)

                    #                     if pose_bone.parent is None:
                    #                         rotation = pose_bone.matrix.to_quaternion()
                    #                     else:
                    #                         # rotation = pose_bone.rotation_quaternion * self.bone_bases[pose_bone.parent.name].abs_bind_pose.to_quaternion().inverted()
                    #                         rotation = pose_bone.matrix.to_quaternion() * self.bone_bases[pose_bone.parent.name].abs_bind_pose.to_quaternion().inverted() * pose_bone.parent.rotation_quaternion

                    keyframe.set_translation(translation)
                    keyframe.set_scale(scale)

                    # keyframe.setRotation(baseBone.abs_bind_pose.to_quaternion().inverted() * pose_bone.matrix.to_quaternion())
                    keyframe.set_rotation(rotation)

        if len(animations_list.animations) > 0:
            render_ware.add_object(animations_list)
            render_ware.add_sub_reference(animations_list, 8)

        bpy.context.scene.frame_set(current_keyframe)

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


def export_rw4(file):
    # NOTE: We might not use Spore's conventional ordering of RW objects, since it's a lot easier to do it this way.
    # Theoretically, this has no effect on the game so it should work fine.

    exporter = RW4Exporter()

    # First process and export the skeleton (if any)
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            exporter.export_armature_object(obj)

    exporter.export_actions()

    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            exporter.export_mesh_object(obj)

    exporter.export_bbox()
    exporter.export_kdtree()

    exporter.render_ware.write(file_io.FileWriter(file))

    return {'FINISHED'}
