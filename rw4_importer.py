__author__ = 'Eric'

from . import rw4_base, rw4_enums, rw4_material_config
from .materials import rw_material_builder
from .file_io import FileReader, ArrayFileReader, get_name
from mathutils import Matrix, Quaternion, Vector
import math
import bpy
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


class RW4ImporterSettings:
    def __init__(self):
        self.import_materials = True
        self.import_skeleton = True
        self.import_animations = True


class PoseBone:
    """Contains the basic information of a bone (rotation, position, scale) using 'mathutils' objects."""
    def __init__(self, r: Quaternion = Quaternion(), t: Vector = Vector.Fill(3), s: Vector = Vector.Fill(3, 1.0)):
        self.r = r
        self.t = t
        self.s = s


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

    def import_meshes(self):
        mesh_links = self.render_ware.get_objects(rw4_base.MeshCompiledStateLink.type_code)

        material_index = 0

        for mesh_link in mesh_links:
            vbuffer = mesh_link.mesh.vertex_buffers[0]
            b_object = self.meshes_dict.get(vbuffer)

            if b_object is not None:
                b_mesh = b_object.data
            else:
                name = "Model-%d" % (self.render_ware.get_index(vbuffer))
                b_mesh = bpy.data.meshes.new(name)
                b_object = bpy.data.objects.new(name, b_mesh)

                bpy.context.scene.collection.objects.link(b_object)
                bpy.context.view_layer.objects.active = b_object

                self.b_meshes.append(b_mesh)
                self.b_mesh_objects.append(b_object)

                self.meshes_dict[vbuffer] = b_object

                # Add all vertices and triangles (only if we haven't added them before)

                ibuffer = mesh_link.mesh.index_buffer
                vertices = vbuffer.process_data(self.file)
                indices = ibuffer.process_data(self.file)

                if ibuffer.primitive_type != rw4_enums.D3DPT_TRIANGLELIST:
                    raise NameError(f"Unsupported primitive type: {ibuffer.primitive_type}")

                b_mesh.vertices.add(len(vertices))
                for i, v in enumerate(vertices):
                    b_mesh.vertices[i].co = v.position

                tri_count = len(indices) // 3
                b_mesh.loops.add(len(indices))
                b_mesh.polygons.add(tri_count)

                b_mesh.loops.foreach_set("vertex_index", tuple(indices))
                b_mesh.polygons.foreach_set("loop_start", [i * 3 for i in range(tri_count)])
                b_mesh.polygons.foreach_set("loop_total", [3] * tri_count)
                b_mesh.polygons.foreach_set("use_smooth", [True] * tri_count)

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

        bones = self.skins_ink.skeleton.bones
        pose_r = []
        pose_t = []
        for i, bone in enumerate(bones):
            skin = self.skins_ink.animation_skin.data[i]
            m = Matrix(skin.matrix.data)
            t = Vector(skin.translation)
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

        for i, (bone, rotation, translation) in enumerate(zip(bones, pose_r, pose_t)):
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

    def set_bone_info(self):
        """Calculates the base PoseBone objects for the RW4 skeleton."""

        if self.skins_ink is not None and self.skins_ink.animation_skin is not None:
            self.bones = self.skins_ink.skeleton.bones
            for i, bone in enumerate(self.bones):
                skin = self.skins_ink.animation_skin.data[i]
                bone.matrix = Matrix(skin.matrix.data)
                bone.translation = Vector(skin.translation)

            branches = []  # used as an stack
            previous = (Matrix.Identity(3), Vector())

            # This is the same algorithm Spore uses
            for bone in self.bones:
                p = previous[0]
                m = bone.matrix
                # m = bone.matrix.transposed()
                t = bone.translation

                # Same as (-(m @ t) @ p) + previous[1]
                # So same as -(t @ m.transposed()) @ p + previous[1]
                new_t = p.transposed() @ -(m @ t) + previous[1]
                new_r = (m.transposed() @ p).to_quaternion()
                # new_t = p @ -(t @ m) + previous[1]
                # new_r = (m @ p.transposed()).to_quaternion()
                print(new_r)
                print(new_t)
                print()
                self.base_bones.append(PoseBone(new_r, new_t, Vector([1.0, 1.0, 1.0])))

                if bone.flags == rw4_base.SkeletonBone.TYPE_ROOT:
                    previous = (m, t)

                elif bone.flags == rw4_base.SkeletonBone.TYPE_LEAF:
                    if branches:
                        previous = branches.pop()

                elif bone.flags == rw4_base.SkeletonBone.TYPE_BRANCH:
                    branches.append(previous)
                    previous = (m, t)

    def matrix_world(self, bone_name):
        local = self.b_armature_object.data.bones[bone_name].matrix_local
        basis = self.b_armature_object.pose.bones[bone_name].matrix_basis

        parent = self.b_armature_object.pose.bones[bone_name].parent
        if parent is None:
            return local @ basis
        else:
            parent_local = self.b_armature_object.data.bones[parent.name].matrix_local
            return self.matrix_world(parent.name) @ (parent_local.inverted() @ local) @ basis

    def import_animation_channel(self, b_pose_bone, b_action, b_action_group, channel, index, channel_keyframes):
        print()
        print(f"## CHANNEL {b_pose_bone.name}")
        print()

        import_locrot = channel.keyframe_class in (rw4_base.LocRotScaleKeyframe, rw4_base.LocRotKeyframe)
        import_scale = channel.keyframe_class == rw4_base.LocRotScaleKeyframe

        fcurves_qr = []
        fcurves_vt = []
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

        for k, kf in enumerate(channel.keyframes):
            time = kf.time * rw4_base.KeyframeAnim.frames_per_second
            bpy.context.scene.frame_set(time)  # So that parent.matrix works

            if import_locrot:
                qr = channel_keyframes[index][k].r
                vt = channel_keyframes[index][k].t

                transform = Matrix.Translation(vt) @ qr.to_matrix().to_4x4()

                # Rotation is in model space
                if b_pose_bone.parent is not None:
                    qr = qr @ b_pose_bone.parent.matrix.inverted().to_quaternion()

                for i in range(4):
                    fcurves_qr[i].keyframe_points.insert(time, qr[i])

                print(b_pose_bone.matrix)

                # Translation in model space; in Blender it's bone pose local space, but before applying rotation
                print(vt)
                # vt = vt  + b_pose_bone.bone.head_local
                # vt = self.b_armature_object.convert_space(pose_bone=b_pose_bone, matrix=Matrix.Translation(vt),
                #                                           from_space='WORLD', to_space='LOCAL').to_translation()

                if b_pose_bone.parent is not None:
                    print("PARENT")
                    print(b_pose_bone.parent.matrix)
                    matrix = b_pose_bone.parent.matrix @ qr.to_matrix().to_4x4()
                else:
                    matrix = b_pose_bone.bone.matrix_local @ qr.to_matrix().to_4x4()

                # b_pose_bone.matrix is not available here yet, so we have to calculate it by hand

                if b_pose_bone.parent is not None:
                    parent_transform = (b_pose_bone.parent.matrix @ b_pose_bone.parent.bone.matrix_local.inverted())
                else:
                    parent_transform = Matrix.Identity(4)

                matrix = Matrix.Translation(parent_transform @ b_pose_bone.bone.head_local) @ matrix.to_3x3().to_4x4()
                parent_matrix = b_pose_bone.parent.matrix if b_pose_bone.parent is not None else Matrix.Identity(4)

                # The position, in world coordinates relative to origin
                world_pos = transform @ b_pose_bone.bone.head_local

                #### THIS THING CONVERTS FROM WORLD TO LOCAL COORDINATES CORRECTLY ####
                print(f"world_pos: {world_pos}")
                # The position, in world coordinates relative to posed position
                world_pos_relative = world_pos - matrix.to_translation()
                # Maybe try with pb.bone.matrix_local.to_3x3().inverted() instead
                local_pos_relative = parent_matrix.to_3x3().inverted() @ world_pos_relative
                vt = local_pos_relative

                # vt = vt + b_pose_bone.bone.head_local
                # if b_pose_bone.parent is not None:
                #     print(self.matrix_world(b_pose_bone.parent.name))
                #     print(b_pose_bone.matrix_basis)
                #     print(b_pose_bone.rotation_quaternion)
                # print(self.matrix_world(b_pose_bone.name))
                # print(self.matrix_world(b_pose_bone.name) @ b_pose_bone.matrix_basis.inverted())
                # vt = (self.matrix_world(b_pose_bone.name) @ b_pose_bone.matrix_basis.inverted()).inverted() @ vt
                # vt = vt + b_pose_bone.location

                print(vt)
                print()
                # if b_pose_bone.parent is not None:
                #     base_m = b_pose_bone.parent.matrix
                #     print(b_pose_bone.parent.matrix)
                #     print(b_pose_bone.matrix)
                #     print(b_pose_bone.matrix_basis)
                #     print(vt)
                #     # vt = b_pose_bone.matrix.to_3x3().inverted() @ vt
                #     #vt = vt @ base_m.to_3x3().inverted()
                #     print(vt)
                #     print()

                for i in range(3):
                    fcurves_vt[i].keyframe_points.insert(time, vt[i])

    def get_bone_index(self, name):
        if self.skins_ink is not None and self.skins_ink.skeleton is not None:
            for i in range(len(self.skins_ink.skeleton.bones)):
                if self.skins_ink.skeleton.bones[i].name == name:
                    return i
        return -1

    @staticmethod
    def interpolate_pose(animation, time, channel_index, keyframe_poses) -> PoseBone:
        """Returns the interpolated pose at 'time' for the given channel."""
        # 1. Get the floor keyframe
        floor_kf = None  # (time, pose)
        for kf_time, pose_bones in keyframe_poses:
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
        for kf_time, pose_bones in keyframe_poses:
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
        r = floor_kf[1].r.slerp(ceil_factor[1].r, lerp_factor)
        t = floor_kf[1].t.lerp(ceil_factor[1].t, lerp_factor)
        s = floor_kf[1].s.lerp(ceil_factor[1].s, lerp_factor)
        return PoseBone(r=r, t=t, s=s)

    def process_animation(self, animation):
        """
        Process all the keyframes of the animation, computing the final transformation matrices used in the shader.
        The matrices are the model space transformation from the base pose to the animated pose.
        Returns a list of channels, where every channel is a list of PoseBone keyframes with the transformation.
        :param animation:
        :return: [[channel0_keyframe0, channel0_keyframe1,...], [channel1_keyframe0,...],...]
        """
        # 1. Classify all keyframes by their time
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
            branches = []  # Used as an stack
            previous_rot = Matrix.Identity(3)
            previous_loc = Vector((0, 0, 0))
            previous_scale = Vector((1.0, 1.0, 1.0))  # inverse scale

            print(f"## TIME {time}")
            for c, (pose_bone, bone) in enumerate(zip(pose_bones, self.bones)):
                skip_bone = pose_bone is None
                if skip_bone:
                    pose_bone = RW4Importer.interpolate_pose(time, c, keyframe_poses)

                # Apply the scale
                scale_matrix = Matrix.Diagonal((1.0 / previous_scale.x, 1.0 / previous_scale.y, 1.0 / previous_scale.z))
                m = scale_matrix @ Matrix.Diagonal(pose_bone.s)
                m = previous_rot @ (scale_matrix @ pose_bone.r.to_matrix())
                # Apply the rotation
                # m = (pose_bone.r.to_matrix().transposed() @ m) @ previous_rot

                t = pose_bone.t @ previous_rot.transposed() + previous_loc

                if not skip_bone:
                    dst_r = m @ bone.matrix.inverted()
                    # dst_t = t + (bone.translation @ m.transposed())
                    dst_t = t + (m @ bone.translation)
                    for i in range(3):
                        print(f"skin_bones_data += struct.pack('ffff', {dst_r[i][0]}, {dst_r[i][1]}, {dst_r[i][2]}, {dst_t[i]})")
                    channel_keyframes[c].append(PoseBone(dst_r.to_quaternion(), dst_t, dst_r.to_scale()))

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
            print()

        return channel_keyframes

    def import_animation(self, animation, b_action):

        print()
        print("##########################3")
        print(b_action.name)
        print()

        bpy.ops.object.mode_set(mode='POSE')

        self.b_armature_object.animation_data_create()
        self.b_armature_object.animation_data.action = b_action

        bpy.ops.object.mode_set(mode='POSE')
        bpy.context.scene.frame_set(0)
        for bone in self.b_armature.bones:
            bone.select = True
        bpy.ops.pose.transforms_clear()

        channel_keyframes = self.process_animation(animation)

        # if b_action.name == 'Point':
        #     bpy.context.scene.frame_set(0)
        #     for pose_bone in self.b_armature_object.pose.bones:
        #         self.b_armature_object.animation_data.action = b_action
        #         print(pose_bone.matrix_basis)
        #         self.b_armature_object.animation_data.action = self.b_animation_actions[0]
        #         print(pose_bone.matrix_basis)
        #         print()
        #
        #     return

        for c, channel in enumerate(animation.channels):
            bone_index = self.get_bone_index(channel.channel_id)
            b_pose_bone = self.b_armature_object.pose.bones[bone_index]

            b_action_group = b_action.groups.new(b_pose_bone.name)

            self.import_animation_channel(
                b_pose_bone,
                b_action,
                b_action_group,
                channel,
                bone_index,
                channel_keyframes)

        bpy.ops.object.mode_set(mode='OBJECT')

        return b_action

    def import_animations(self):
        if self.b_armature_object is None:
            return

        self.set_bone_info()

        anim_objects = self.render_ware.get_objects(rw4_base.Animations.type_code)
        handle_objects = self.render_ware.get_objects(rw4_base.MorphHandle.type_code)

        # First create all actions
        if not anim_objects and not handle_objects:
            return

        bpy.context.view_layer.objects.active = self.b_armature_object
        self.b_armature_object.animation_data_create()
        animations = anim_objects[0].animations

        for anim_id in animations.keys():
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

        for i, anim in enumerate(animations.values()):
            self.import_animation(anim, self.b_animation_actions[i])

        for i, handle in enumerate(handle_objects):
            self.import_animation(handle.anim, self.b_animation_actions[i + len(animations)])

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
