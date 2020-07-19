import bpy
import ntpath
import os
from .file_io import FileReader, ResourceKey
from . import rw4_enums


SHADER_DATA_SIZES = {
    0x210: 20,
    0x218: 0
}


class TriangleBuffer:
    def __init__(self):
        self.indices = []
        self.primitive_type = 4
        self.indices_bits = 16  # how many bits used by each index value

    def read(self, file: FileReader):
        self.primitive_type = file.read_int()
        indices_count = file.read_int()
        self.indices_bits = file.read_int()
        file.read_int()  # buffer size

        fmt = '<H' if self.indices_bits == 16 else '<I'

        for i in range(indices_count):
            self.indices.append(file.unpack(fmt)[0])


class VertexFormat:
    def __init__(self):
        self.format_elements = []
        self.vertex_class = None

    def read(self, file: FileReader):
        element_count = file.read_int()
        for i in range(element_count):
            e = rw4_enums.VertexElement()
            e.read(file)
            self.format_elements.append(e)

        self.vertex_class = rw4_enums.create_rw_vertex_class(self.format_elements)

    def read_vertex(self, file: FileReader):
        v = rw4_enums.read_rw_vertex(self.format_elements, self.vertex_class, file)
        return v

    def has_element(self, rw_decl) -> bool:
        for e in self.format_elements:
            if e.rw_decl == rw_decl:
                return True
        return False


class VertexBuffer:
    def __init__(self):
        self.vertex_format = None
        self.vertices = []

    def read(self, file: FileReader, vertex_formats):
        format_index = file.read_int()
        self.vertex_format = vertex_formats[format_index]
        vertex_count = file.read_int()
        file.read_int()  # buffer size

        for i in range(vertex_count):
            self.vertices.append(self.vertex_format.read_vertex(file))


class Mesh:
    def __init__(self):
        self.vertex_buffer = None
        self.triangle_buffer = None
        self.material_id = -1


class SporeGameModel:
    def __init__(self):
        self.version = 9
        self.referenced_files = []
        self.bounding_box = None
        self.bounding_radius = 0

        self.triangle_buffers = []
        self.vertex_buffers = []
        self.meshes = []

    def read_material(self, file: FileReader):
        unk = file.read_uint('>')
        if unk != 0:
            shdata_count = file.read_uint()
            for _ in range(shdata_count):
                shdata_index = file.read_uint()

                if shdata_index == 0x20D:
                    texture_count = file.read_uint()
                    for t in range(texture_count):
                        file.skip_bytes(16)  # first value is sampler index
                        file.skip_bytes(8)  # instance, group IDs
                # Spore theorically supports all shader data, gets their size in runtime
                elif shdata_index in SHADER_DATA_SIZES:
                    file.skip_bytes(SHADER_DATA_SIZES[shdata_index])
                else:
                    raise IOError(f"Unexpected shader data 0x{shdata_index:03x}; file.tell(): {file.tell()}")

    def read(self, file: FileReader, import_skeleton):
        self.version = file.read_int()
        count = file.read_int('>')
        for i in range(count):
            key = ResourceKey()
            key.read(file, '>')
            self.referenced_files.append(key)

        mesh_count = file.read_int()

        self.bounding_box = (file.unpack('<fff'), file.unpack('<fff'))
        self.bounding_radius = file.read_float()

        tri_buffers_count = file.read_int()
        for i in range(tri_buffers_count):
            buffer = TriangleBuffer()
            buffer.read(file)
            self.triangle_buffers.append(buffer)

        vertex_formats = []
        vertex_formats_count = file.read_int()
        for i in range(vertex_formats_count):
            fmt = VertexFormat()
            fmt.read(file)
            vertex_formats.append(fmt)

        vertex_buffers_count = file.read_int()
        for i in range(vertex_buffers_count):
            buf = VertexBuffer()
            buf.read(file, vertex_formats)
            self.vertex_buffers.append(buf)

        for i in range(mesh_count):
            t_index = file.read_int()
            v_index = file.read_int()
            mesh = Mesh()
            mesh.vertex_buffer = self.vertex_buffers[v_index]
            mesh.triangle_buffer = self.triangle_buffers[t_index]
            self.meshes.append(mesh)

        for mesh in self.meshes:
            mesh.material_id = file.read_uint()

        if import_skeleton:
            # A count of something material related, let's hope it's always 0
            if file.read_uint() != 0:
                raise IOError("Wrong material count")

            material_count = file.read_uint()
            for i in range(material_count):
                self.read_material(file)

            print(file.tell())
            count1 = file.read_uint()  # num of skeletons ?
            file.skip_bytes(count1 * 8)  # second is number of bones

            part_count = file.read_uint()
            print(f"Part count: {part_count}")

            for p in range(part_count):
                file.skip_bytes(0x38)  # Transform
                file.skip_bytes(0x38)  # Transform
                field_70 = file.read_uint()  # for root, how many bones
                key = file.unpack('<III')
                var_1444 = file.read_uint()

                print(f"field_70: {field_70}")
                print(f"key: 0x{key[2]:08x}!0x{key[0]:08x}.0x{key[1]:08x}")
                print(f"var_1444: {var_1444}")

                if var_1444 != 0:
                    bone_count = file.read_uint()
                    file.skip_bytes(0xA0 * bone_count)
                    print(f"bone_count: {bone_count}")

                print()

            print(file.tell())


def import_textures(b_mesh, filepath):
    diffuse_path = f"{filepath[:filepath.rindex('.')]}__diffuse.tga"
    if os.path.isfile(diffuse_path):
        gmdl_name = os.path.split(filepath)[-1]
        gmdl_name = gmdl_name[:gmdl_name.rindex('.')]

        material = bpy.data.materials.new(gmdl_name)
        material.use_nodes = True
        b_mesh.materials.append(material)

        # Diffuse
        image = bpy.data.images.load(diffuse_path)
        image.alpha_mode = 'NONE'
        texture_node = material.node_tree.nodes.new("ShaderNodeTexImage")
        texture_node.image = image
        texture_node.location = (-524, 256)
        material.node_tree.links.new(material.node_tree.nodes["Principled BSDF"].inputs["Base Color"],
                                     texture_node.outputs["Color"])

        normal_path = f"{filepath[:filepath.rindex('.')]}__normal.tga"
        if os.path.isfile(normal_path):
            image = bpy.data.images.load(normal_path)
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

        specular_path = f"{filepath[:filepath.rindex('.')]}__specular.tga"
        if os.path.isfile(normal_path):
            image = bpy.data.images.load(specular_path)

            texture_node = material.node_tree.nodes.new("ShaderNodeTexImage")
            texture_node.image = image
            texture_node.location = (-524, -322)

            material.node_tree.links.new(material.node_tree.nodes["Principled BSDF"].inputs["Specular"],
                                         texture_node.outputs["Color"])


def import_gmdl(file, import_skeleton, filepath):
    result = {'FINISHED'}

    gmdl = SporeGameModel()
    gmdl.read(FileReader(file), import_skeleton)

    for mesh_index, mesh in enumerate(gmdl.meshes):
        b_scene = bpy.context.scene

        name = ntpath.basename(file.name)
        if len(gmdl.meshes) > 1:
            name += f"-{mesh_index}"
        b_mesh = bpy.data.meshes.new(name)
        b_obj = bpy.data.objects.new(name, b_mesh)

        b_scene.collection.objects.link(b_obj)
        bpy.context.view_layer.objects.active = b_obj

        max_blend_index = 0

        v_buffer = mesh.vertex_buffer

        import_skeleton = v_buffer.vertex_format.has_element(rw4_enums.RWDECL_BLENDINDICES)
        b_mesh.vertices.add(len(v_buffer.vertices))
        for i, v in enumerate(v_buffer.vertices):
            b_mesh.vertices[i].co = v.position

            if import_skeleton:
                for j in range(4):
                    if v.blendIndices[j] > max_blend_index:
                        max_blend_index = v.blendIndices[j]

        t_buffer = mesh.triangle_buffer
        if t_buffer.primitive_type != 4:
            raise BufferError("Only D3DPT_TRIANGLELIST supported")

        tri_count = len(t_buffer.indices) // 3
        b_mesh.loops.add(len(t_buffer.indices))
        b_mesh.polygons.add(tri_count)

        b_mesh.loops.foreach_set("vertex_index", tuple(t_buffer.indices))
        b_mesh.polygons.foreach_set("loop_start", [i*3 for i in range(tri_count)])
        b_mesh.polygons.foreach_set("loop_total", [3] * tri_count)
        b_mesh.polygons.foreach_set("use_smooth", [True] * tri_count)

        if v_buffer.vertex_format.has_element(rw4_enums.RWDECL_TEXCOORD0):
            uv_layer = b_mesh.uv_layers.new()
            for loop in b_mesh.loops:
                uv = v_buffer.vertices[loop.vertex_index].texcoord0
                uv_layer.data[loop.index].uv = (uv[0], -uv[1])

        if import_skeleton:
            for i in range(max_blend_index//3 + 1):
                b_obj.vertex_groups.new(name=f"bone-{i}")

            for v, vertex in enumerate(v_buffer.vertices):
                for i in range(4):
                    if vertex.blendWeights[i] != 0:
                        b_obj.vertex_groups[vertex.blendIndices[i] // 3].add([v], vertex.blendWeights[i], 'REPLACE')

        #TODO: vertex colors?

        b_mesh.update(calc_edges=True)

        # Apply the normals after updating
        if v_buffer.vertex_format.has_element(rw4_enums.RWDECL_NORMAL):
            for i, v in enumerate(v_buffer.vertices):
                b_mesh.vertices[i].normal = rw4_enums.unpack_normals(v.normal)

        b_mesh.validate()

        import_textures(b_mesh, filepath)

    return result
