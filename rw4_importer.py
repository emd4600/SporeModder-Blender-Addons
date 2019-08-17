__author__ = 'Eric'

from . import rw4_base, rw4_enums, rw4_material_config
from .materials import rw_material_builder
from .file_io import FileReader, ArrayFileReader, get_name
from mathutils import Matrix, Quaternion, Vector
import math
import bpy


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
        self.import_movements = True


class RW4Importer:
    class BoneInfo:
        def __init__(self):
            self.abs_bind_pose = None
            self.inv_pose_translation = None
            self.inv_bind_pose = None
            self.pose_translation = None

    def __init__(self, render_ware: rw4_base.RenderWare4, file: FileReader, settings: RW4ImporterSettings):
        # for blender objects, we use the prefix b
        self.render_ware = render_ware
        self.file = file
        self.settings = settings

        self.meshes_dict = {}  # vertexBuffer -> b_object
        self.b_mesh_objects = []
        self.b_meshes = []

        self.b_armature = None
        self.b_armature_object = None
        self.skins_ink = None

        self.b_animation_actions = []
        self.bones_info = []

    def process(self):
        self.process_skeleton()
        self.process_meshes()
        self.process_animations()

    def process_meshes(self):
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

    def process_skeleton(self):
        if not self.settings.import_skeleton:
            return

        skins_inks = self.render_ware.get_objects(rw4_base.SkinsInK.type_code)
        if not skins_inks:
            return

        self.skins_ink = skins_inks[0]

        self.b_armature = bpy.data.armatures.new(get_name(self.skins_ink.skeleton.skeleton_id))
        self.b_armature_object = bpy.data.objects.new(self.b_armature.name, self.b_armature)

        bpy.context.scene.collection.objects.link(self.b_armature_object)
        bpy.context.view_layer.objects.active = self.b_armature_object

        bones = self.skins_ink.skeleton.bones
        for i, bone in enumerate(bones):
            skin = self.skins_ink.animation_skin.data[i]
            bone.matrix = Matrix(skin.matrix.data)
            bone.translation = Vector(skin.translation)

        branches = []  # used as an stack
        previous = (Matrix.Identity(3), Vector())

        pose_r = []
        pose_t = []

        # # This is the same algorithm Spore uses
        # for bone in bones:
        #     p = previous[0]
        #     m = bone.matrix
        #     t = bone.translation
        #
        #     pose_t.append(p.transposed() @ -(m @ t) + previous[1])
        #     pose_r.append((m.transposed() @ p).to_quaternion())
        #
        #     if bone.flags == rw4_base.SkeletonBone.TYPE_ROOT:
        #         previous = (m, t)
        #
        #     elif bone.flags == rw4_base.SkeletonBone.TYPE_LEAF:
        #         if branches:
        #             previous = branches.pop()
        #
        #     elif bone.flags == rw4_base.SkeletonBone.TYPE_BRANCH:
        #         branches.append(previous)
        #         previous = (m, t)

        for bone in bones:
            m = bone.matrix
            t = bone.translation
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

            b_bone.head = translation
            b_bone.tail = axis * bone_length + b_bone.head
            b_bone.roll = roll

            if bone.parent is not None:
                b_bone.parent = self.b_armature.edit_bones[self.skins_ink.skeleton.bones.index(bone.parent)]

        bpy.ops.object.mode_set(mode='OBJECT')

    def set_bone_info(self):
        if self.skins_ink is not None and self.skins_ink.animation_skin is not None:
            base_rot = Matrix.Identity(3)

            for i, bone_pose in enumerate(self.skins_ink.animation_skin.data):

                bone_info = RW4Importer.BoneInfo()

                bone_info.abs_bind_pose = Matrix(bone_pose.abs_bind_pose.data)
                bone_info.inv_bind_pose = (bone_info.abs_bind_pose.inverted() @ base_rot).to_quaternion()

                bone_info.inv_pose_translation = Vector(bone_pose.inv_pose_translation)

                self.bones_info.append(bone_info)

                if self.skins_ink.skeleton.bones[i].flags == 0:
                    base_rot = bone_info.abs_bind_pose

    def import_animation_rotation(self, b_pose_bone, b_action, b_action_group, channel, index):
        data_path = b_pose_bone.path_from_id('rotation_quaternion')
        qr_w = b_action.fcurves.new(data_path, index=0)
        qr_x = b_action.fcurves.new(data_path, index=1)
        qr_y = b_action.fcurves.new(data_path, index=2)
        qr_z = b_action.fcurves.new(data_path, index=3)

        qr_w.group = b_action_group
        qr_x.group = b_action_group
        qr_y.group = b_action_group
        qr_z.group = b_action_group

        for kf in channel.keyframes:
            qr = Quaternion((kf.rot[3], kf.rot[0], kf.rot[1], kf.rot[2])) @ self.bones_info[index].inv_bind_pose

            if b_pose_bone.parent is not None:
                parent_qr = b_pose_bone.parent.rotation_quaternion
                qr = qr @ parent_qr.inverted()

            qr_w.keyframe_points.insert(kf.time*rw4_base.KeyframeAnim.frames_per_second, qr[0])
            qr_x.keyframe_points.insert(kf.time*rw4_base.KeyframeAnim.frames_per_second, qr[1])
            qr_y.keyframe_points.insert(kf.time*rw4_base.KeyframeAnim.frames_per_second, qr[2])
            qr_z.keyframe_points.insert(kf.time*rw4_base.KeyframeAnim.frames_per_second, qr[3])

    def import_animation_location(self, b_pose_bone, b_action, b_action_group, channel, index):
        data_path = b_pose_bone.path_from_id('location')
        vt_x = b_action.fcurves.new(data_path, index=0)
        vt_y = b_action.fcurves.new(data_path, index=1)
        vt_z = b_action.fcurves.new(data_path, index=2)

        vt_x.group = b_action_group
        vt_y.group = b_action_group
        vt_z.group = b_action_group

        for kf in channel.keyframes:
            vt = Vector((vt_x, vt_y, vt_z))

            if b_pose_bone.parent is not None:
                vt = vt + self.bones_info[index].inv_pose_translation

            vt_x.keyframe_points.insert(kf.time*rw4_base.KeyframeAnim.frames_per_second, vt[0])
            vt_y.keyframe_points.insert(kf.time*rw4_base.KeyframeAnim.frames_per_second, vt[1])
            vt_z.keyframe_points.insert(kf.time*rw4_base.KeyframeAnim.frames_per_second, vt[2])

    def get_bone_index(self, name):
        if self.skins_ink is not None and self.skins_ink.skeleton is not None:
            for i in range(len(self.skins_ink.skeleton.bones)):
                if self.skins_ink.skeleton.bones[i].name == name:
                    return i
        return -1

    def process_animation(self, animation, anim_id):
        """ Imports an animation and returns the Blender Action"""

        b_action = bpy.data.actions.new(get_name(anim_id))
        self.b_animation_actions.append(b_action)

        self.b_armature_object.animation_data.action = b_action

        for c, channel in enumerate(animation.channels):
            bone_index = self.get_bone_index(channel.channel_id)

            b_pose_bone = self.b_armature_object.pose.bones[bone_index]

            b_action_group = b_action.groups.new(b_pose_bone.name)

            if channel.keyframe_class == rw4_base.LocRotScaleKeyframe or \
                    channel.keyframe_class == rw4_base.LocRotKeyframe:
                self.import_animation_rotation(
                    b_pose_bone=b_pose_bone,
                    b_action=b_action,
                    b_action_group=b_action_group,
                    channel=channel,
                    index=bone_index
                    )

        return b_action

    def process_animations(self):
        if not self.settings.import_movements:
            return
        if self.b_armature_object is None:
            return

        anim_objects = self.render_ware.get_objects(rw4_base.Animations.type_code)

        # Animations
        if anim_objects:

            bpy.context.view_layer.objects.active = self.b_armature_object

            self.set_bone_info()

            animations = anim_objects[0].animations

            bpy.ops.object.mode_set(mode='POSE')
            self.b_armature_object.animation_data_create()

            for anim_id in animations.keys():

                animation = animations[anim_id]

                self.process_animation(animation, anim_id)

            bpy.ops.object.mode_set(mode='OBJECT')

        # Morph handles
        handle_objects = self.render_ware.get_objects(rw4_base.MorphHandle.type_code)

        if handle_objects:
            bpy.ops.object.mode_set(mode='POSE')

            # Check if we have created the animation data yet
            if len(anim_objects) == 0:
                self.b_armature_object.animation_data_create()
                self.set_bone_info()

            for handle in handle_objects:
                b_action = self.process_animation(handle.animation, handle.handle_id)

                b_action.rw4.is_morph_handle = True
                b_action.rw4.initial_pos = handle.start_pos
                b_action.rw4.final_pos = handle.end_pos
                b_action.rw4.default_frame = int(handle.default_time * 24)

            bpy.ops.object.mode_set(mode='OBJECT')


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
