import bpy

from bpy.props import (BoolProperty,
                       IntProperty,
                       FloatVectorProperty,
                       PointerProperty,
                       FloatProperty
                       )
import bpy
import gpu
import bgl
from mathutils import Vector, Matrix
from gpu_extras.batch import batch_for_shader

DIRECTION_FACTORIES = {
    '+X': lambda bbox: (bbox[1].x - bbox[0].x, 0.0, 0.0),
    '-X': lambda bbox: (-(bbox[1].x - bbox[0].x), 0.0, 0.0),
    '+Z': lambda bbox: (0.0, 0.0, bbox[1].z - bbox[0].z),
    '-Z': lambda bbox: (0.0, 0.0, -(bbox[1].z - bbox[0].z)),
    '+Y': lambda bbox: (0.0, bbox[1].y - bbox[0].y, 0.0),
    '-Y': lambda bbox: (0.0, -(bbox[1].y - bbox[0].y), 0.0),
}

# Receives the center for the keyframe and the mid point, must decide which coordinates are kept
DIRECTION_CENTER_FACTORIES = {
    '+X': lambda center, mid: (center.x, mid.y, mid.z),
    '-X': lambda center, mid: (center.x, mid.y, mid.z),
    '+Y': lambda center, mid: (mid.x, center.y, mid.z),
    '-Y': lambda center, mid: (mid.x, center.y, mid.z),
    '+Z': lambda center, mid: (mid.x, mid.y, center.z),
    '-Z': lambda center, mid: (mid.x, mid.y, center.z),
}


def calc_global_bbox():
    """
    :return: The bounding box that contains all mesh objects.
    """
    mesh_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH']

    if not mesh_objects:
        return [Vector((0, 0, 0)), Vector((0, 0, 0))]

    min_bbox = mesh_objects[0].bound_box[0]
    max_bbox = mesh_objects[0].bound_box[6]
    min_bbox = Vector((min_bbox[0], min_bbox[1], min_bbox[2]))
    max_bbox = Vector((max_bbox[0], max_bbox[1], max_bbox[2]))

    for obj in mesh_objects[1:]:
        min_point = obj.bound_box[0]
        max_point = obj.bound_box[6]

        for i in range(3):
            if min_point[i] < min_bbox[i]:
                min_bbox[i] = min_point[i]

            if max_point[i] < max_bbox[i]:
                max_bbox[i] = max_point[i]

    return [min_bbox, max_bbox]


def get_center(bbox):
    return (bbox[1] + bbox[0]) / 2


def default_deform_axis(bbox1, bbox2, factor, directions):
    bbox = calc_global_bbox()
    center1 = get_center(bbox1)
    center2 = get_center(bbox2)
    mid = (center1 + center2) / 2

    center = Vector(DIRECTION_CENTER_FACTORIES[directions[0]](get_center(bbox), mid))
    for d in directions[1:]:
        center = Vector(DIRECTION_CENTER_FACTORIES[d](center, mid))

    direction = sum((Vector(DIRECTION_FACTORIES[d](bbox)) for d in directions), Vector((0, 0, 0)))
    return center + direction * (factor - 0.5)


def default_deform_radius(bbox1, bbox2, factor, height_factor):
    bbox = calc_global_bbox()
    center1 = get_center(bbox1)
    center2 = get_center(bbox2)
    mid = (center1 + center2) / 2

    center = Vector(DIRECTION_CENTER_FACTORIES['-Y'](get_center(bbox), mid))

    length = Vector((bbox[1].x - bbox[0].x, bbox[1].y - bbox[0].y, 0.0)).length
    height = bbox[1].z - bbox[0].z
    center = center + Vector((0, 0, 1)) * height * (height_factor - 0.5)
    direction = Vector((0, -length, 0))  # move it forward
    return center + direction * (factor - 0.5)


DEFAULT_HANDLE_POSITIONS = {
    'DeformRadius': (default_deform_radius, 0.5),
    'DeformRadiusMiddle': (default_deform_radius, 0.5),
    'DeformRadiusTop': (default_deform_radius, 0.8),
    'DeformRadiusBottom': (default_deform_radius, 0.2),
    'DeformAxisUpLeft': (default_deform_axis, ['+Z', '-X']),
    'DeformAxisUpFront': (default_deform_axis, ['+Z', '-Y']),
    'DeformAxisUpRight': (default_deform_axis, ['+Z', '+X']),  # TODO does this exist?
    'DeformAxisRightFront': (default_deform_axis, ['+X', '-Y']),
    'DeformAxisLeftFront': (default_deform_axis, ['-X', '-Y']),
    # TODO What's the difference between front and forward?
    'DeformAxisFront': (default_deform_axis, ['-Y ']),
    'DeformAxisForward': (default_deform_axis, ['-Y']),
    'DeformAxisBack': (default_deform_axis, ['+Y']),
    'DeformAxisRight': (default_deform_axis, ['+X']),
    'DeformAxisLeft': (default_deform_axis, ['-X']),
    'DeformAxisUp': (default_deform_axis, ['+Z']),
    'DeformBoneBaseJoint': (default_deform_axis, ['-Y ']),
    'DeformBoneEndJoint': (default_deform_axis, ['-Y ']),
    'DeformBoneMiddle': (default_deform_axis, ['-Y ']),
    'BoneLength': (default_deform_axis, ['-Y ']),
    'Nudge': (default_deform_axis, ['+Z ']),
}


def get_default_handle_position(name):
    if not bpy.data.meshes or name not in DEFAULT_HANDLE_POSITIONS:
        return None
    generator = DEFAULT_HANDLE_POSITIONS[name]

    action = bpy.data.actions[name]
    current_keyframe = bpy.context.scene.frame_current
    current_actions = []
    # Save the actions so they can be restored
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj.animation_data is not None:
            current_actions.append(obj.animation_data.action)
            obj.animation_data.action = None
        elif obj.type == 'MESH' and obj.data.shape_keys is not None and obj.data.shape_keys.animation_data is not None:
            current_actions.append(obj.data.shape_keys.animation_data.action)
            obj.data.shape_keys.animation_data.action = None

    is_shape_key = action.id_root == 'KEY'
    if not is_shape_key:
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE' and obj.animation_data is not None:
                obj.animation_data.action = action
    else:
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.data.shape_keys is not None and \
                    obj.data.shape_keys.animation_data is not None:
                obj.data.shape_keys.animation_data.action = action

    bpy.context.scene.frame_set(int(action.frame_range[0]))
    bbox1 = calc_global_bbox()
    bpy.context.scene.frame_set(int(action.frame_range[1]))
    bbox2 = calc_global_bbox()

    bpy.context.scene.frame_set(int(action.frame_range[0]))
    initial_pos = generator[0](bbox1, bbox2, 1.2, *generator[1:])
    bpy.context.scene.frame_set(int(action.frame_range[1]))
    final_pos = generator[0](bbox1, bbox2, 1.2, *generator[1:])

    if initial_pos == final_pos:
        final_pos = generator[0](bbox1, bbox2, 2.4, *generator[1:])

    # Restore actions
    for obj, act in zip(bpy.data.objects, current_actions):
        if obj.type == 'ARMATURE' and obj.animation_data is not None:
            obj.animation_data.action = act
        elif obj.type == 'MESH' and obj.data.shape_keys is not None and obj.data.shape_keys.animation_data is not None:
            obj.data.shape_keys.animation_data.action = act
    bpy.context.scene.frame_set(current_keyframe)
    return initial_pos, final_pos


def morph_handle_update(self, context):
    if self.is_morph_handle:
        if self.initial_pos == Vector((0.0, 0.0, 0.0)) and self.final_pos == Vector((0.0, 0.0, 0.0)):
            action = bpy.data.actions[context.scene.rw4_list_index]
            result = get_default_handle_position(action.name)
            if result is not None:
                self.initial_pos, self.final_pos = result


class RW4AnimProperties(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.Action.rw4 = PointerProperty(type=RW4AnimProperties)

        cls.is_morph_handle = BoolProperty(
            name="Morph Handle",
            description="Check if you want this action to be a morph handle and not a movement animation",
            default=False,
            update=morph_handle_update
        )
        cls.initial_pos = FloatVectorProperty(
            name="Start Position",
            subtype='XYZ',
            precision=3,
            description="Handle start position"
        )
        cls.final_pos = FloatVectorProperty(
            name="Final Position",
            subtype='XYZ',
            precision=3,
            description="Handle final position"
        )
        cls.default_progress = FloatProperty(
            name="Default Progress",
            default=0,
            min=0.0,
            max=100.0,
            subtype='PERCENTAGE'
        )

    @classmethod
    def unregister(cls):
        del bpy.types.Action.rw4


shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
BOX_COORDS = [
        (-0.5, -0.5, +1), (+0.5, -0.5, +1),
        (+0.5, +0.5, +1), (-0.5, +0.5, +1),
        (-0.5, -0.5, 0), (+0.5, -0.5, 0),
        (+0.5, +0.5, 0), (-0.5, +0.5, 0)]
BOX_INDICES = (
    (0, 1, 2), (2, 3, 0), (1, 5, 6), (6, 2, 1),
    (7, 6, 5), (5, 4, 7), (4, 0, 3), (3, 7, 4),
    (4, 5, 1), (1, 0, 4), (3, 2, 6), (6, 7, 3)
)


def is_anim_panel_showing():
    for area in bpy.context.screen.areas:
        if area.type == 'PROPERTIES':
            for space in area.spaces:
                if space.type == 'PROPERTIES' and space.context == 'SCENE':
                    return True
    return False


def handle_draw_callback():
    if not bpy.data.actions:
        return
    action = bpy.data.actions[bpy.context.scene.rw4_list_index]
    if not action.rw4.is_morph_handle or not is_anim_panel_showing():
        return

    direction = Vector(action.rw4.final_pos) - Vector(action.rw4.initial_pos)
    length = direction.length
    if length == 0.0:
        return

    bbox = calc_global_bbox()
    width = (bbox[1] - bbox[0]).length * 0.02

    scale_matrix = Matrix.Scale(direction.length, 3, Vector((0, 0, 1)))
    scale_matrix = scale_matrix @ Matrix.Scale(width, 3, Vector((0, 1, 0)))
    scale_matrix = scale_matrix @ Matrix.Scale(width, 3, Vector((1, 0, 0)))

    matrix = Vector((0, 0, 1)).rotation_difference(direction).to_matrix()
    matrix = Matrix.Translation(action.rw4.initial_pos) @ (matrix @ scale_matrix).to_4x4()

    bgl.glEnable(bgl.GL_BLEND)
    bgl.glEnable(bgl.GL_LINE_SMOOTH)
    bgl.glEnable(bgl.GL_POLYGON_SMOOTH)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)

    shader.bind()
    shader.uniform_float("color", (109/255.0, 141/255.0, 143/255.0, 0.4))
    batch = batch_for_shader(shader, 'TRIS', {
        "pos": [matrix @ Vector(c) for c in BOX_COORDS]
    }, indices=BOX_INDICES)
    batch.draw(shader)

    # Draw initial handle pos
    handle_width = width * 1.25
    matrix = Matrix.Translation(Vector(action.rw4.initial_pos) - Vector((0, 0, 0.5*handle_width)))  # center it
    matrix = matrix @ Matrix.Diagonal((handle_width, handle_width, handle_width, 1))

    shader.uniform_float("color", (165/255.0, 195/255.0, 196/255.0, 0.4))
    batch = batch_for_shader(shader, 'TRIS', {
        "pos": [matrix @ Vector(c) for c in BOX_COORDS]
    }, indices=BOX_INDICES)
    batch.draw(shader)

    # Draw initial handle pos
    handle_width = width * 1.25
    matrix = Matrix.Translation(Vector(action.rw4.final_pos) - Vector((0, 0, 0.5*handle_width)))  # center it
    matrix = matrix @ Matrix.Diagonal((handle_width, handle_width, handle_width, 1))

    shader.uniform_float("color", (165 / 255.0, 195 / 255.0, 196 / 255.0, 0.4))
    batch = batch_for_shader(shader, 'TRIS', {
        "pos": [matrix @ Vector(c) for c in BOX_COORDS]
    }, indices=BOX_INDICES)
    batch.draw(shader)


class SPORE_UL_rw_anims(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        # We could write some code to decide which icon to use here...
        custom_icon = 'OBJECT_DATAMODE'

        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon=custom_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon=custom_icon)

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        new_items = sorted(filter(lambda x: x.fcurves, items), key=lambda x: x.name)
        filter_flags = [self.bitflag_filter_item if item in new_items else 0 for item in items]
        filter_neworder = [new_items.index(item) if item in new_items else 0 for item in items]
        return filter_flags, filter_neworder


class SPORE_OT_auto_handles(bpy.types.Operator):
    bl_idname = "action.auto_rw_handle"
    bl_label = "Automatic Positions"
    bl_description = "Generates automatic initial/final positions based on the shape of the model"

    @classmethod
    def poll(cls, context):
        action = bpy.data.actions[context.scene.rw4_list_index]
        return action.name in DEFAULT_HANDLE_POSITIONS

    def execute(self, context):
        action = bpy.data.actions[context.scene.rw4_list_index]
        result = get_default_handle_position(action.name)
        if result is not None:
            action.rw4.initial_pos, action.rw4.final_pos = result
        return {'FINISHED'}


class SPORE_PT_rw_anims(bpy.types.Panel):
    bl_label = "RenderWare4 Animations"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'

    def draw(self, context):
        self.layout.use_property_split = True

        self.layout.template_list("SPORE_UL_rw_anims", "The_List", bpy.data, "actions", context.scene, "rw4_list_index")

        if bpy.data.actions:
            item = bpy.data.actions[context.scene.rw4_list_index].rw4
            self.layout.prop(item, 'is_morph_handle')

            if item.is_morph_handle:
                self.layout.operator("action.auto_rw_handle", text="Automatic Positions")
                self.layout.prop(item, 'initial_pos')
                self.layout.prop(item, 'final_pos')
                self.layout.prop(item, 'default_progress')
        

def register():
    bpy.utils.register_class(SPORE_OT_auto_handles)
    bpy.utils.register_class(SPORE_UL_rw_anims)
    bpy.utils.register_class(RW4AnimProperties)
    bpy.utils.register_class(SPORE_PT_rw_anims)
    bpy.types.Scene.rw4_list_index = IntProperty(name="Index for rw4_list", default=0)  # , update=update_action_list)

    bpy.types.SpaceView3D.draw_handler_add(handle_draw_callback, (), 'WINDOW', 'POST_VIEW')


def unregister():
    bpy.types.SpaceView3D.draw_handler_remove(handle_draw_callback, 'WINDOW')

    bpy.utils.unregister_class(SPORE_PT_rw_anims)
    bpy.utils.unregister_class(RW4AnimProperties)
    bpy.utils.unregister_class(SPORE_UL_rw_anims)
    bpy.utils.unregister_class(SPORE_OT_auto_handles)

    del bpy.types.Scene.rw4_list_index
