import bpy
from mathutils import Vector


def error_no_material(obj):
    return f"Mesh {obj.name} has no material."


def error_vertex_bone_limit(obj):
    return f"There are vertices with more than 4 bones assigned in mesh {obj.name}."


def error_not_normalized(obj):
    return f"Mesh {obj.name} weights are not normalized."


def error_vertices_limit(obj):
    return f"Mesh {obj.name} has too many vertices. Reduce the complexity or split into multiple objects."


def error_no_texcoord(obj):
    return f"Mesh {obj.name} does not have a UV map."


def error_root_bone_limit():
    return "The armature has more than one root bone."


def error_root_bone_not_origin():
    return "The armature root bone must be in the origin (0, 0, 0)"


def error_transforms(obj):
    return f"There are transforms not applied to object {obj.name}."


def error_shape_keys_multi_models():
    return "Only one mesh object can be exported when using shape keys. Use materials."


def error_shape_keys_not_relative():
    return 'Shape keys must be in "Relative" mode.'


def error_armature_limit():
    return "Spore only supports 1 armature object per model."


def error_action_no_fake(action):
    return f"Action {action.name} has no fake user. Might not get saved."


def error_action_start_frame(action):
    return f"Action {action.name} does not start at frame 0."


def error_texture_does_not_exist(path):
    return f"Texture at {path} does not exist."


def error_texture_error(path):
    return f"Error reading texture {path}"


def validate_armatures(layout):
    armature = None

    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            if armature is not None:
                layout.label(text=error_armature_limit())
                break
            else:
                armature = obj

    if armature is not None:
        too_many_root_bones = False
        root_bone = None
        for bone in armature.data.bones:
            if bone.parent is not None:
                if root_bone is not None:
                    too_many_root_bones = True
                else:
                    root_bone = bone

        if too_many_root_bones:
            layout.label(text=error_root_bone_limit())

        if root_bone is not None and root_bone.head != Vector((0, 0, 0)):
            layout.label(text=error_root_bone_not_origin())


def validate_models(layout):
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
