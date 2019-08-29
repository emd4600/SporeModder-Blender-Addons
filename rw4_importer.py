__author__ = 'Eric'

from . import rw4_base, rw4_enums, rw4_material_config
from .materials import rw_material_builder
from .file_io import FileReader, ArrayFileReader, get_name
from mathutils import Matrix, Quaternion, Vector
import math
import bpy
import bmesh
from collections import OrderedDict


def show_message_box(message: str, title: str, icon='ERROR'):
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def vec_roll_to_mat3(vec, roll):
    target = Vector((0, 0.1, 0))
    nor = vec.normalized()
    axis = target.cross(nor)
    if axis.dot(axis) > 0.0000000001:  # this seems to be the problem for some bones, no idea how to fix
        axis.normalize()
        theta = target.angle(nor)
        bmatrix = Matrix.Rotation(theta, 3, axis)
    else:
        updown = 1 if target.dot(nor) > 0 else -1
        bmatrix = Matrix.Scale(updown, 3)

        # C code:
        # bMatrix[0][0]=updown; bMatrix[1][0]=0.0;    bMatrix[2][0]=0.0;
        # bMatrix[0][1]=0.0;    bMatrix[1][1]=updown; bMatrix[2][1]=0.0;
        # bMatrix[0][2]=0.0;    bMatrix[1][2]=0.0;    bMatrix[2][2]=1.0;
        bmatrix[2][2] = 1.0

    rmatrix = Matrix.Rotation(roll, 3, nor)
    mat = rmatrix @ bmatrix
    return mat


def mat3_to_vec_roll(mat):
    vec = mat.col[1]
    vecmat = vec_roll_to_mat3(mat.col[1], 0)
    vecmatinv = vecmat.inverted()
    rollmat = vecmatinv @ mat
    roll = math.atan2(rollmat[0][2], rollmat[2][2])
    return vec, roll


class PoseBone:
    """Contains the basic information of a bone (rotation, position, scale) using 'mathutils' objects."""
    def __init__(self, r: Quaternion = Quaternion(), t: Vector = Vector.Fill(3), s: Vector = Vector.Fill(3, 1.0)):
        self.r = r
        self.t = t
        self.s = s


def interpolate_pose(animation, time, channel_index, keyframe_poses) -> PoseBone:
    """Returns the interpolated pose at 'time' for the given channel."""
    # 1. Get the floor keyframe
    floor_kf = None  # (time, pose)
    for kf_time, pose_bones in keyframe_poses.items():
        if kf_time < time:
            floor_kf = (kf_time, pose_bones[channel_index])
        else:
            break
    # No floor time? Malformed animation
    if floor_kf is None:
        raise rw4_base.ModelError(
            f"Malformed animation: channel {channel_index} is missing floor keyframe for time {time}", animation)

    # 2. Get the ceil keyframe
    ceil_kf = None  # (time, pose)
    for kf_time, pose_bones in keyframe_poses.items():
        if kf_time > time:
            ceil_kf = (kf_time, pose_bones[channel_index])
            break

    # No ceil time? Malformed animation
    if ceil_kf is None:
        raise rw4_base.ModelError(
            f"Malformed animation: channel {channel_index} is missing ceil keyframe for time {time}", animation)

    # Convert times to 0-1 range
    floor_factor = floor_kf[0] / animation.length
    ceil_factor = ceil_kf[0] / animation.length
    factor = time / animation.length
    lerp_factor = (factor - floor_factor) / (ceil_factor - floor_factor)
    r = floor_kf[1].r.slerp(ceil_kf[1].r, lerp_factor)
    t = floor_kf[1].t.lerp(ceil_kf[1].t, lerp_factor)
    s = floor_kf[1].s.lerp(ceil_kf[1].s, lerp_factor)
    return PoseBone(r=r, t=t, s=s)


class RW4ImporterSettings:
    def __init__(self):
        self.import_materials = True
        self.import_skeleton = True
        self.import_animations = True


class RW4Importer:
    def __init__(self, render_ware: rw4_base.RenderWare4, file: FileReader, settings: RW4ImporterSettings):
        # For blender objects, we use the prefix b
        self.render_ware = render_ware
        self.file = file
        self.settings = settings

        self.meshes_dict = {}  # vertexBuffer -> b_object
        self.b_mesh_objects = []
        self.b_meshes = []

        self.b_armature = None
        self.b_armature_object = None
        self.skins_ink = None
        self.bones = []  # type: List[rw4_base.SkeletonBone]
        self.b_animation_actions = []
        self.base_bones = []
        self.animation_bones = {}  # maps ID to list of channels, which are lists of PoseBone keyframes

    def process(self):
        if self.settings.import_skeleton:
            self.import_skeleton()
        self.import_meshes()
        if self.settings.import_animations:
            self.import_animations()

    def process_index_buffer(self, ibuffer, b_mesh):
        """Adds the triangles defined by the given IndexBuffer to the mesh."""
        indices = ibuffer.process_data(self.file)

        if ibuffer.primitive_type != rw4_enums.D3DPT_TRIANGLELIST:
            raise NameError(f"Unsupported primitive type: {ibuffer.primitive_type}")

        tri_count = len(indices) // 3
        b_mesh.loops.add(len(indices))
        b_mesh.polygons.add(tri_count)

        b_mesh.loops.foreach_set("vertex_index", tuple(indices))
        b_mesh.polygons.foreach_set("loop_start", [i * 3 for i in range(tri_count)])
        b_mesh.polygons.foreach_set("loop_total", [3] * tri_count)
        b_mesh.polygons.foreach_set("use_smooth", [True] * tri_count)

    def import_blend_shape_mesh(self, mesh_link):
        buffers = self.render_ware.get_objects(rw4_base.BlendShapeBuffer.type_code)
        if len(buffers) != 1:
            raise rw4_base.ModelError("Malformed model: missing BlendShapeBuffer")
        buffer = buffers[0]

        blend_shapes = self.render_ware.get_objects(rw4_base.BlendShape.type_code)
        if len(blend_shapes) != 1:
            raise rw4_base.ModelError("Malformed model: missing BlendShape")

        if buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_POSITION] == -1:
            raise rw4_base.ModelError("Malformed model: BlendShapeBuffer does not have POSITION")

        name = get_name(blend_shapes[0].id)
        b_mesh = bpy.data.meshes.new(name)
        b_object = bpy.data.objects.new(name, b_mesh)

        bpy.context.scene.collection.objects.link(b_object)
        bpy.context.view_layer.objects.active = b_object

        self.b_meshes.append(b_mesh)
        self.b_mesh_objects.append(b_object)

        self.meshes_dict[None] = b_object  # For no vertex buffer

        stream = ArrayFileReader(buffer.data)
        vertex_count = buffer.vertex_count

        stream.seek(buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_POSITION])
        b_mesh.vertices.add(vertex_count)
        for i in range(vertex_count):
            b_mesh.vertices[i].co = stream.unpack('<fff')
            stream.skip_bytes(4)

        self.process_index_buffer(mesh_link.mesh.index_buffer, b_mesh)
        b_mesh.update(calc_edges=True)

        for i, shape_id in enumerate(blend_shapes[0].shape_ids):
            shape_key = b_object.shape_key_add(name='Basis' if shape_id == 0 else get_name(shape_id))
            shape_key.interpolation = 'KEY_LINEAR'

            stream.seek(buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_POSITION] + 16*i*vertex_count)
            for v in range(vertex_count):
                shape_key.data[v].co = Vector(stream.unpack('<fff')) + b_mesh.vertices[v].co
                stream.skip_bytes(4)

        b_mesh.shape_keys.use_relative = True

        if buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_TEXCOORD] != -1:
            stream.seek(buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_TEXCOORD])
            texcoords = [None] * vertex_count
            for i in range(vertex_count):
                texcoords[i] = stream.unpack('<ff')
                stream.skip_bytes(8)

            uv_layer = b_mesh.uv_layers.new()
            for loop in b_mesh.loops:
                uv = texcoords[loop.vertex_index]
                uv_layer.data[loop.index].uv = (uv[0], -uv[1])

        # Configure skeleton if any
        if self.b_armature is not None and buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_BLENDINDICES] != -1:
            blend_indices = [-1] * vertex_count
            blend_weights = [0.0] * vertex_count
            stream.seek(buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_BLENDINDICES])
            for i in range(vertex_count):
                blend_indices[i] = stream.unpack('<HHHH')

            stream.seek(buffer.offsets[rw4_base.BlendShapeBuffer.INDEX_BLENDWEIGHTS])
            for i in range(vertex_count):
                blend_weights[i] = stream.unpack('<ffff')

            for bbone in self.b_armature.bones:
                b_object.vertex_groups.new(name=bbone.name)

            for v, (blend_index, blend_weight) in enumerate(zip(blend_indices, blend_weights)):
                for i in range(4):
                    if blend_weight[i] != 0:
                        b_object.vertex_groups[blend_index[i] // 3].add(
                            [v], blend_weight[i] / 255.0, 'REPLACE')

            b_modifier = b_object.modifiers.new(f"Skeleton: {self.b_armature.name}", 'ARMATURE')
            b_modifier.object = self.b_armature_object
            b_modifier.use_vertex_groups = True

        return b_mesh

    def import_vertex_buffer_mesh(self, mesh_link):
        vbuffer = mesh_link.mesh.vertex_buffers[0]
        name = "Model-%d" % (self.render_ware.get_index(vbuffer))
        b_mesh = bpy.data.meshes.new(name)
        b_object = bpy.data.objects.new(name, b_mesh)

        bpy.context.scene.collection.objects.link(b_object)
        bpy.context.view_layer.objects.active = b_object

        self.b_meshes.append(b_mesh)
        self.b_mesh_objects.append(b_object)

        self.meshes_dict[vbuffer] = b_object

        # Add all vertices and triangles
        vertices = vbuffer.process_data(self.file)
        b_mesh.vertices.add(len(vertices))
        for i, v in enumerate(vertices):
            b_mesh.vertices[i].co = v.position

        self.process_index_buffer(mesh_link.mesh.index_buffer, b_mesh)

        if vbuffer.has_element(rw4_enums.RWDECL_TEXCOORD0):
            uv_layer = b_mesh.uv_layers.new()
            for loop in b_mesh.loops:
                uv = vertices[loop.vertex_index].texcoord0
                uv_layer.data[loop.index].uv = (uv[0], -uv[1])

        # TODO: vertex colors?

        b_mesh.update(calc_edges=True)

        # Apply the normals after updating
        if vbuffer.has_element(rw4_enums.RWDECL_NORMAL):
            for i, v in enumerate(vertices):
                b_mesh.vertices[i].normal = rw4_enums.unpack_normals(v.normal)

        # Configure skeleton if any
        if self.b_armature is not None:
            for bbone in self.b_armature.bones:
                b_object.vertex_groups.new(name=bbone.name)

            for v, vertex in enumerate(vertices):
                for i in range(4):
                    if vertex.blendWeights[i] != 0:
                        b_object.vertex_groups[vertex.blendIndices[i] // 3].add(
                            [v], vertex.blendWeights[i] / 255.0, 'REPLACE')

            b_modifier = b_object.modifiers.new(f"Skeleton: {self.b_armature.name}", 'ARMATURE')
            b_modifier.object = self.b_armature_object
            b_modifier.use_vertex_groups = True

        return b_mesh

    def import_meshes(self):
        mesh_links = self.render_ware.get_objects(rw4_base.MeshCompiledStateLink.type_code)

        material_index = 0

        for mesh_link in mesh_links:
            vbuffer = mesh_link.mesh.vertex_buffers[0]
            b_object = self.meshes_dict.get(vbuffer)

            if b_object is not None:
                b_mesh = b_object.data
            elif vbuffer is None:
                b_mesh = self.import_blend_shape_mesh(mesh_link)
            else:
                b_mesh = self.import_vertex_buffer_mesh(mesh_link)

            # Configure material for the mesh
            b_material = bpy.data.materials.new(f"Mesh-{self.render_ware.get_index(mesh_link)}")
            b_mesh.materials.append(b_material)

            if self.settings.import_materials and len(mesh_link.compiled_states) > 0:
                material_builder = rw_material_builder.RWMaterialBuilder()
                material_builder.from_compiled_state(ArrayFileReader(mesh_link.compiled_states[0].data))

                rw4_material_config.parse_material_builder(material_builder, b_material.rw4)

            first_tri = mesh_link.mesh.first_index // 3
            for i in range(first_tri, first_tri + mesh_link.mesh.triangle_count):
                b_mesh.polygons[i].material_index = material_index

            material_index += 1

        for b_mesh in self.b_meshes:
            b_mesh.validate()

    def get_bound_radius(self):
        bound_box = self.render_ware.get_objects(rw4_base.BoundingBox.type_code)
        if bound_box:
            bbox = bound_box[0].bound_box
            return (Vector(bbox[1]) - Vector(bbox[0])).length / 2.0

        return 0.0

    def import_skeleton(self):
        skins_inks = self.render_ware.get_objects(rw4_base.SkinsInK.type_code)
        if not skins_inks:
            return

        self.skins_ink = skins_inks[0]

        self.b_armature = bpy.data.armatures.new(get_name(self.skins_ink.skeleton.skeleton_id))
        self.b_armature_object = bpy.data.objects.new(self.b_armature.name, self.b_armature)

        bpy.context.scene.collection.objects.link(self.b_armature_object)
        bpy.context.view_layer.objects.active = self.b_armature_object

        self.bones = self.skins_ink.skeleton.bones
        pose_r = []
        pose_t = []
        for i, bone in enumerate(self.bones):
            skin = self.skins_ink.animation_skin.data[i]
            bone.matrix = m = Matrix(skin.matrix.data)
            bone.translation = t = Vector(skin.translation)
            inv_bind_pose = m.inverted().to_4x4()
            inv_bind_pose[0][3] = t[0]
            inv_bind_pose[1][3] = t[1]
            inv_bind_pose[2][3] = t[2]

            abs_bind_pose = inv_bind_pose.inverted()
            head = abs_bind_pose.to_translation()

            axis, roll = mat3_to_vec_roll(inv_bind_pose.to_3x3())

            # We might not need to use rotations at all, so this is better
            axis = Vector((0, 1, 0))

            pose_t.append(head)
            pose_r.append(axis)

        # Use some arbitrary bone length, but relative to the model size
        bone_length = 0.15 * self.get_bound_radius()

        bpy.ops.object.mode_set(mode='EDIT')

        for i, (bone, rotation, translation) in enumerate(zip(self.bones, pose_r, pose_t)):
            b_bone = self.b_armature.edit_bones.new(get_name(bone.name))
            b_bone.use_local_location = True

            axis = Vector((0, 1, 0))
            roll = 0.0

            # skin = self.skins_ink.animation_skin.data[i]
            # m = Matrix(skin.matrix.data)
            # t = Vector(skin.translation)
            # inv_bind_pose = m.inverted().to_4x4()
            # inv_bind_pose[0][3] = t[0]
            # inv_bind_pose[1][3] = t[1]
            # inv_bind_pose[2][3] = t[2]
            #
            # axis, roll = mat3_to_vec_roll(m.transposed().to_3x3())

            b_bone.head = translation
            b_bone.tail = axis * bone_length + b_bone.head
            b_bone.roll = roll

            if bone.parent is not None:
                b_bone.parent = self.b_armature.edit_bones[self.skins_ink.skeleton.bones.index(bone.parent)]

        bpy.ops.object.mode_set(mode='OBJECT')

    def process_animation(self, animation):
        """
        Process all the keyframes of the animation, computing the final transformation matrices used in the shader.
        The matrices are the model space transformation from the base pose to the animated pose.
        Returns a list of channels, where every channel is a list of Matrix4 keyframes with the transformation.
        :param animation:
        :return: [[channel0_keyframe0, channel0_keyframe1,...], [channel1_keyframe0,...],...]
        """
        # 1. Clssify all keyframes by their time
        # [(time1, pose_bones), (time2, pose_bones), etc], one keyframe per channel per time
        keyframe_poses = OrderedDict()
        for c, channel in enumerate(animation.channels):
            for kf in channel.keyframes:
                if kf.time not in keyframe_poses:
                    keyframe_poses[kf.time] = [None] * len(animation.channels)

                if channel.keyframe_class == rw4_base.LocRotScaleKeyframe or \
                        channel.keyframe_class == rw4_base.LocRotKeyframe:
                    r = Quaternion((kf.rot[3], kf.rot[0], kf.rot[1], kf.rot[2]))
                    t = Vector(kf.loc)
                else:
                    r = Quaternion()
                    t = Vector((0, 0, 0))

                if channel.keyframe_class == rw4_base.LocRotScaleKeyframe:
                    s = Vector(kf.scale)
                else:
                    s = Vector((1.0, 1.0, 1.0))

                keyframe_poses[kf.time][c] = PoseBone(r=r, t=t, s=s)

        # 2. Process the transformation matrix
        # This is the same algorithm used by Spore; the result is what is sent to the DirectX shader
        # These are the transforms in model space from the rest pose to the animated pose
        # This assumes that parents will always be processed before their children
        # List of channels, which are list of PoseBone keyframes containing the transformation
        channel_keyframes = [[] for _ in animation.channels]

        # Process for every channel for every time
        # We must do it even if the channel didn't have a keyframe there, because it might be used by other channels
        for time, pose_bones in keyframe_poses.items():
            print()
            print(f"# TIME {time}")
            print()

            branches = []  # Used as an stack
            previous_rot = Matrix.Identity(3)
            previous_loc = Vector((0, 0, 0))
            previous_scale = Vector((1.0, 1.0, 1.0))  # inverse scale

            for c, (pose_bone, bone) in enumerate(zip(pose_bones, self.bones)):
                skip_bone = pose_bone is None
                if skip_bone:
                    pose_bone = interpolate_pose(animation, time, c, keyframe_poses)

                # # Apply the scale
                # scale_matrix = Matrix.Diagonal((1.0 / previous_scale.x, 1.0 / previous_scale.y, 1.0 / previous_scale.z))
                # m = scale_matrix @ Matrix.Diagonal(pose_bone.s)
                # # Apply the rotation
                # m = previous_rot @ (m @ pose_bone.r.to_matrix())

                # Apply the scale
                scale_matrix = Matrix.Diagonal(pose_bone.s)
                parent_inv_scale = Matrix.Diagonal((1.0 / previous_scale.x, 1.0 / previous_scale.y, 1.0 / previous_scale.z))
                old_m = parent_inv_scale @ scale_matrix
                # Apply the rotation
                old_m = previous_rot @ (old_m @ pose_bone.r.to_matrix())

                # m = (pose_bone.r.to_matrix() @ scale_matrix).transposed() @ parent_inv_scale
                m = (scale_matrix @ pose_bone.r.to_matrix().transposed()) @ parent_inv_scale
                #print(m)
                m = m @ previous_rot

                # t = pose_bone.t @ previous_rot.transposed() + previous_loc
                t = previous_rot.transposed() @ pose_bone.t + previous_loc
                #print(previous_rot)
                #print(previous_loc)
                #print(t)

                if not skip_bone:
                    #dst_r = m @ bone.matrix.inverted()
                    dst_r = bone.matrix @ m
                    #print(m)
                    dst_t = t + (m.transposed() @ bone.translation)
                    #print(dst_t)
                    for i in range(3):
                        print(f"skin_bones_data += struct.pack('ffff', {dst_r[i][0]}, {dst_r[i][1]}, {dst_r[i][2]}, {dst_t[i]})")
                    channel_keyframes[c].append(Matrix.Translation(dst_t) @ dst_r.to_4x4())

                #print()

                if bone.flags == rw4_base.SkeletonBone.TYPE_ROOT:
                    previous_rot = m
                    previous_loc = t
                    previous_scale = pose_bone.s

                elif bone.flags == rw4_base.SkeletonBone.TYPE_LEAF:
                    if branches:
                        previous_rot, previous_loc, previous_scale = branches.pop()

                elif bone.flags == rw4_base.SkeletonBone.TYPE_BRANCH:
                    branches.append((previous_rot, previous_loc, previous_scale))
                    previous_rot = m
                    previous_loc = t
                    previous_scale = pose_bone.s

        return channel_keyframes

    def import_animation_shape_key(self, animation, b_action):
        for channel in animation.channels:
            #TODO get from animation skeleton id? Theorically there should be a single mesh object
            key = self.b_meshes[0].shape_keys.key_blocks[get_name(channel.channel_id)]
            data_path = key.path_from_id('value')
            fcurve = b_action.fcurves.new(data_path)
            for keyframe in channel.keyframes:
                time = keyframe.time * rw4_base.KeyframeAnim.frames_per_second
                fcurve.keyframe_points.insert(time, keyframe.factor)

    @staticmethod
    def import_animation_channel(
            b_pose_bone, b_action, b_action_group, channel, index, channel_keyframes, compensation_factor):

        import_locrot = channel.keyframe_class in (rw4_base.LocRotScaleKeyframe, rw4_base.LocRotKeyframe)
        import_scale = channel.keyframe_class == rw4_base.LocRotScaleKeyframe

        fcurves_qr = []
        fcurves_vt = []
        fcurves_vs = []

        if import_locrot:
            data_path = b_pose_bone.path_from_id('rotation_quaternion')
            for i in range(4):
                fcurve = b_action.fcurves.new(data_path, index=i)
                fcurve.group = b_action_group
                fcurves_qr.append(fcurve)

            data_path = b_pose_bone.path_from_id('location')
            for i in range(3):
                fcurve = b_action.fcurves.new(data_path, index=i)
                fcurve.group = b_action_group
                fcurves_vt.append(fcurve)

        if import_scale:
            data_path = b_pose_bone.path_from_id('scale')
            for i in range(3):
                fcurve = b_action.fcurves.new(data_path, index=i)
                fcurve.group = b_action_group
                fcurves_vs.append(fcurve)

        for k, kf in enumerate(channel.keyframes):
            time = kf.time * rw4_base.KeyframeAnim.frames_per_second
            bpy.context.scene.frame_set(time)  # So that parent.matrix works

            transform = channel_keyframes[index][k]

            if import_locrot:
                # Rotation is in model space
                qr = transform.to_quaternion()
                if b_pose_bone.parent is not None:
                    qr = b_pose_bone.parent.matrix.inverted().to_quaternion() @ qr

                if compensation_factor != 1.0:
                    qr = Quaternion().slerp(qr, compensation_factor)

                for i in range(4):
                    fcurves_qr[i].keyframe_points.insert(time, qr[i])

                # The position, in world coordinates relative to origin
                vt = transform @ b_pose_bone.bone.head_local

                # Convert from WORLD position into LOCAL position
                # This only works because we import our bones with no rotation; for exporting this will require more
                if b_pose_bone.parent is not None:
                    parent_matrix = b_pose_bone.parent.matrix
                    parent_transform = (parent_matrix @ b_pose_bone.parent.bone.matrix_local.inverted())
                    # The position, in world coordinates relative to posed position
                    world_pos_relative = vt - (parent_transform @ b_pose_bone.bone.head_local)
                    vt = parent_matrix.to_3x3().inverted() @ world_pos_relative

                if compensation_factor != 1.0:
                    vt = Vector((0, 0, 0)).lerp(vt, compensation_factor)

                for i in range(3):
                    fcurves_vt[i].keyframe_points.insert(time, vt[i])

                if import_scale:
                    # It's in the transform coordinate system; in Blender it's in the bone.matrix
                    # Since we use an Identity rotation for the bone matrix, it's the same
                    vs = transform.to_scale()

                    if compensation_factor != 1.0:
                        vs = Vector((1.0, 1.0, 1.0)).lerp(vs, compensation_factor)

                    for i in range(3):
                        fcurves_vs[i].keyframe_points.insert(time, vs[i])

    def import_animation(self, animation, b_action, compensation_factor=1.0):
        """
        Imports a RW4 animation into the given action. A compensation factor can be applied; it will be used as an
        interpolation value to soften morph handle animations.
        :param animation:
        :param b_action:
        :param compensation_factor:
        :return:
        """
        is_shape_key = False
        for channel in animation.channels:
            if channel.keyframe_class == rw4_base.BlendFactorKeyframe:
                is_shape_key = True
                break

        if is_shape_key:
            bpy.context.view_layer.objects.active = self.b_mesh_objects[0]
            self.b_meshes[0].shape_keys.animation_data_create()
            self.b_meshes[0].shape_keys.animation_data.action = b_action

            self.import_animation_shape_key(animation, b_action)

        else:
            bpy.context.view_layer.objects.active = self.b_armature_object
            bpy.ops.object.mode_set(mode='POSE')

            self.b_armature_object.animation_data_create()
            self.b_armature_object.animation_data.action = b_action

            bpy.ops.object.mode_set(mode='POSE')
            bpy.context.scene.frame_set(0)
            for bone in self.b_armature.bones:
                bone.select = True
            bpy.ops.pose.transforms_clear()

            channel_keyframes = self.process_animation(animation)
            for c, channel in enumerate(animation.channels):
                b_pose_bone = self.b_armature_object.pose.bones[c]
                b_action_group = b_action.groups.new(b_pose_bone.name)

                RW4Importer.import_animation_channel(
                    b_pose_bone,
                    b_action,
                    b_action_group,
                    channel,
                    c,
                    channel_keyframes,
                    compensation_factor)

            bpy.ops.object.mode_set(mode='OBJECT')

        return b_action

    def import_animations(self):
        if self.b_armature_object is None:
            return

        anim_objects = self.render_ware.get_objects(rw4_base.Animations.type_code)
        handle_objects = self.render_ware.get_objects(rw4_base.MorphHandle.type_code)
        print(handle_objects)

        # First create all actions
        if not anim_objects and not handle_objects:
            return

        self.b_armature_object.animation_data_create()

        if anim_objects:
            for anim_id in anim_objects[0].animations.keys():
                b_action = bpy.data.actions.new(get_name(anim_id))
                b_action.use_fake_user = True
                self.b_animation_actions.append(b_action)

        for handle in handle_objects:
            b_action = bpy.data.actions.new(get_name(handle.handle_id))
            b_action.use_fake_user = True
            self.b_animation_actions.append(b_action)

            b_action.rw4.is_morph_handle = True
            b_action.rw4.initial_pos = handle.start_pos
            b_action.rw4.final_pos = handle.end_pos
            b_action.rw4.default_frame = int(handle.default_time * 24)

        if anim_objects:
            for i, anim in enumerate(anim_objects[0].animations.values()):
                self.import_animation(anim, self.b_animation_actions[i])

        anim_count = len(anim_objects[0].animations) if anim_objects else 0

        for i, handle in enumerate(handle_objects):
            print()
            print()
            print(f"## --- ANIM {self.b_animation_actions[i + anim_count].name}")
            print()
            # self.import_animation(handle.animation, self.b_animation_actions[i + anim_count], 1.0 / len(handle_objects))
            self.import_animation(handle.animation, self.b_animation_actions[i + anim_count])

        bpy.context.scene.frame_set(0)


def import_rw4(file, settings):
    file_reader = FileReader(file)

    render_ware = rw4_base.RenderWare4()

    render_ware.read(file_reader)

    importer = RW4Importer(render_ware, file_reader, settings)
    try:
        importer.process()
    except rw4_base.ModelError as e:
        show_message_box(str(e), "Import Error")

    return {'FINISHED'}
