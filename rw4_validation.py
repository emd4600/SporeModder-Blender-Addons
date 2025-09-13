import bpy
from mathutils import Vector


def error_no_material(obj):
	return f"Mesh {obj.name} has no material."


def error_vertex_bone_limit(obj):
	return f"There are vertices with more than 4 bones assigned in mesh {obj.name}."


def error_too_many_bones(obj):
	return f"Armature {obj.name} has more than 86 bones, which is the maximum a mesh can have."


def error_not_normalized(obj):
	return f"Mesh {obj.name} weights are not normalized."


def error_bone_weight_limit(mesh, bone_name):
	return f"Mesh {mesh.name} has some vertices assigned to bone {bone_name} with a weight greater than 1.0"


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
	return f"Error reading texture '{path}'. Ensure it is a DDS texture."


def error_texture_not_dds(path):
	return f"Only DDS textures are supported, '{path}' does not have a .dds extension."

def error_texture_missing():
	return f"One or more textures are unspecified."


def error_modifiers(obj):
	return f"Object {obj.name} has modifiers, please apply them if you want the changes exported."


def error_action_but_no_armature(action):
	return f"Armature action {action.name} is not assigned to any armature and will not be exported."


def error_action_but_no_object(action):
	return f"Shape key action {action.name} is not assigned to any object and will not be exported."


def error_no_bone_for_vertex_group(v_group):
	return f"There is a vertex group called {v_group.name}, but no bone exists with that name."


def error_action_with_missing_shapes(action, shape_name):
	return f"Action {action.name} uses shape key {shape_name}, but no shape key exists with that name."




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
