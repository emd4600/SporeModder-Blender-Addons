import bpy
import mathutils
from . import anim_bone_config, mod_paths
from .message_box import show_message_box

def requirements_to_string(item):
	text = ''
	if item.has_upright_spine != 'ignore':
		text += f" uprightSpine {item.has_upright_spine}"
	if item.has_graspers != 'ignore':
		text += f" hasGraspers {item.has_graspers}"
	if item.has_feet != 'ignore':
		text += f" hasFeet {item.has_feet}"
	return text


def event_source_to_string(source):
	s = source.type

	s += context_query_to_string(source, "query", False)

	# (variable_name, text, default)
	attributes = (
		("prefilter_2D4", "require2D4", 'none'),
		("prefilter_2D5", "require2D5", 'none'),
		("prefilter_2D6", "require2D6", 'none'),
		("filter", "filter", 'any'),
		("scale", "scale", 'noScale'),
		("position", "position", 'default'),
		("addposition", "addPosition", 'none'),
		("rotation", "rotation", 'default'),
		("handedness", "handedness", 'none'),
	)

	for attr in attributes:
		data = getattr(source, attr[0])
		if data != attr[2]:
			s += f" -{attr[1]} {data}"

	return s


def context_query_to_string(item, prefix, is_secondary):
	attributes = (
		("_selectX", "selectX", 'all'),
		("_selectY", "selectY", 'all'),
		("_selectZ", "selectZ", 'all'),
		("_extent", "extent", 'none'),
		("_limb", "limb", 'none'),
	)
	s = ""

	write_capability = True
	if is_secondary:
		if item.secondary_type == "ExternalTarget":
			s += f" {item.secondary_target_index}"
			write_capability = False
			
	if write_capability:
		data = getattr(item, prefix + "_capability")
		if data != 'all':
			s += f" {data}"

	for attr in attributes:
		data = getattr(item, prefix + attr[0])
		if data != attr[2]:
			s += f" -{attr[1]} {data}"

	return s


def event_to_string(internal_name, event):
	text = f"event {internal_name} {event.name} -type {event.type}"

	if event.requirements:
		text += f" -predicate {requirements_to_string(event)}"

	if event.type == 'unk20000':
		text += f" -param0 int {event.unk20000_parameter0} -param1 float {event.unk20000_parameter1}"
	elif event.type == 'message':
		text += f" -param0 int {event.message_parameter0} -param1 float {event.message_parameter1}"
	else:
		if event.chance != 1.0:
			text += f" -chance {event.chance}"

		if event.type == 'unk3':
			text += f" -param0 float {event.unk3_parameter}"
		elif event.type == 'sound2':
			text += f" -param0 float {event.sound2_parameter}"
		elif event.type == 'footstep':
			text += f" -param0 float {event.footstep_parameter}"
		elif event.type == 'effect':
			text += f" -param0 float {event.effect_parameter}"

	if event.archetype != 'none':
		text += f" -archetype {event.archetype}"

	if event.event_group != 0:
		text += f" -eventGroup {event.event_group}"
	if event.max_dist != 0.0:
		text += f" -maxSqrDist {event.max_dist**2}"
	event_flags = event.flags
	if event.type == 'effect' and event.effect_use_local_reference:
		event_flags |= 0x40
		
	if event_flags != 0:
		text += f" -flags 0x{event_flags:x}"

	if event.effect_update_position:
		text += " -updatePosition"
	if event.effect_update_rotation:
		text += " -updateRotation"
	if event.effect_update_scale:
		text += " -updateScale"
	if event.effect_update_particle_size:
		text += " -updateParticleScale"
	if event.effect_update_attractor:
		text += " -updateAttractor"
	if event.effect_apply_scale:
		text += " -applyScale"
	if event.effect_identity_color:
		text += " -identityColor"
	if event.stopeffect_hardstop:
		text += " -hardStop"

	text += "\n"

	first_source = event_source_to_string(event.position_source)
	if first_source != 'default':
		text += f"\tpositionSource {first_source}\n"

	if not event.rotation_source.not_copy_from_position:
		text += f"\trotationSource {first_source}\n"
	else:
		source = event_source_to_string(event.rotation_source)
		if source != 'default':
			text += f"\trotationSource {source}\n"

	if not event.scale_source.not_copy_from_position:
		text += f"\tscaleSource {first_source}\n"
	else:
		source = event_source_to_string(event.scale_source)
		if source != 'default':
			text += f"\tscaleSource {source}\n"

	if event.unk_source.enabled:
		text += f"\tsource4 {event_source_to_string(event.unk_source)}\n"

	return text + "end\n"


def channel_header(channel):
	text = f"channel \"{channel.name}\""

	text += context_query_to_string(channel, "primary", False)

	if channel.ground_relative:
		text += " -groundRelative"
		
	if channel.secondary_directional_only:
		text += " -secondaryDirectionalOnly"
		
	if channel.secondary_lookat:
		text += " -rotRelativeExtTarg"

	text += f" -blendGroup {channel.blend_group}"

	if channel.variant_group != 0:
		text += f" -variantGroup {channel.blend_group}"

	if channel.primary_flags != 0:
		text += f" -selectFlags {channel.primary_flags}"

	if channel.bind_flags != 0:
		text += f" -bindFlags {channel.bind_flags}"

	if channel.movement_flags != 0:
		text += f" -movementFlags {channel.movement_flags}"

	return text


def secondary_command(channel):
	text = f"secondary "
	text += context_query_to_string(channel, "secondary", True)
	return text


def info_keyframe_to_string(t, events, event_names, info_flags):
	text = f"\t\t{t}"

	if info_flags != 0:
		text += f" -flags 0x{info_flags:x}"

	evs = [ev for ev in events if ev.play_frame == t]
	if evs:
		text += " -events"
		text += "".join(f" {event_names[ev]}" for ev in evs)

	text += "\n"
	return text


def get_position(armature_matrix, channel, bone, secondary_reference_bone):
	bone_pos = armature_matrix @ bone.head
	rest_pos = armature_matrix @ bone.bone.head_local
	basis_matrix = mathutils.Matrix.Identity(3)
	
	if secondary_reference_bone is not None:
		# Build a change of basis matrix for the secondary coordinate system
		# X is direction towards secondary, Y is same as secondary Y, Z is perpendicular to both
		secondary_pos = armature_matrix @ secondary_reference_bone.head
		#secondary_bone_matrix = armature_matrix @ secondary_reference_bone.matrix
		secondary_X = secondary_pos - rest_pos
		#secondary_Y = secondary_bone_matrix @ mathutils.Vector((0, 1, 0))
		secondary_Y = secondary_reference_bone.y_axis
		secondary_Z = secondary_X.cross(secondary_Y)
		basis_matrix = mathutils.Matrix([secondary_X, secondary_Y, secondary_Z]).transposed()
		print("Basis matrix")
		print(basis_matrix)
		basis_matrix = basis_matrix.inverted(mathutils.Matrix.Identity(3))
		print("Basis matrix inverted")
		print(basis_matrix)
		
	pos = bone_pos
	if channel.relative_pos:
		pos = bone_pos - rest_pos

		if channel.ground_relative:
			old_range = 0.0 - rest_pos.z
			pos.z = (bone_pos.z - rest_pos.z) / old_range
			
	#TODO what role does relative_pos play in the secondary?

	return basis_matrix @ pos


def get_rotation(armature_matrix, channel, bone):
	bone_matrix = armature_matrix @ bone.matrix
	if channel.relative_rot:
		rest_matrix = armature_matrix @ bone.bone.matrix_local
		bone_matrix = bone_matrix @ rest_matrix.inverted()
	return bone_matrix.to_quaternion()


class AnimChannelOutput:
	def __init__(self, armature_object, channel, bone, events, channel_times, rigblock_names):
		self.armature_object = armature_object
		self.channel = channel
		self.bone = bone
		self.events = events
		self.channel_times = channel_times
		self.channel_info_flags = []
		self.rigblock_names = rigblock_names
		self.position_text = ""
		self.rotation_text = ""
		self.rigblocks_text = {name: "" for name in rigblock_names}
		self.secondary_reference_bone = self.get_secondary_reference_bone()

	def has_time(self, t):
		return t in self.channel_times

	def add_rigblock_keyframe(self):
		for anim_name in self.rigblock_names:
			v = getattr(self.channel, anim_name)
			text = f"\t\t{v[0]}"
			if v[1] != 1.0:
				text += f" {v[1]}"
			self.rigblocks_text[anim_name] += text + "\n"
			
	def get_secondary_reference_bone(self):
		bone_name = self.channel.secondary_reference_bone
		if self.channel.secondary_type != 'none' and bone_name:
			bone_query = [b for b in self.armature_object.pose.bones if b.name == bone_name]
			if not bone_query:
				show_message_box(f"Error in {self.bone.name} secondary reference bone: Bone named '{bone_name}' does not exist", "Error")
				return None
			return bone_query[0]
		return None

	def add_position_keyframe(self):
		pos = get_position(self.armature_object.matrix_world, self.channel, self.bone, self.secondary_reference_bone)
		text = f"\t\t({pos.x}, {pos.y}, {pos.z})"
		if self.channel.position_weight != 1.0:
			text += f" {self.channel.position_weight}"
		self.position_text += text + "\n"

	def add_rotation_keyframe(self):
		rot = get_rotation(self.armature_object.matrix_world, self.channel, self.bone)
		text = f"\t\t({rot.x}, {rot.y}, {rot.z}, {rot.w})"
		if self.channel.rotation_weight != 1.0:
			text += f" {self.channel.rotation_weight}"
		self.rotation_text += text + "\n"


def export_anim(file):
	if not bpy.data.armatures:
		show_message_box("Must have an armature to export an animation", "Error")
		return {'CANCELLED'}
	mod_paths.set_mod_folder(file)

	armature = bpy.data.armatures[0]
	armature_object = next(x for x in bpy.data.objects if x.name == armature.name)
	scene = bpy.context.scene
	current_frame = scene.frame_current

	if armature.animation_data is None:
		armature.animation_data_create()
	deforms_action = armature.animation_data.action

	if armature_object.animation_data is None:
		armature_object.animation_data_create()
	bones_action = armature_object.animation_data.action

	keyframe_times = {0}  # Ensure frame 0 is always there
	for action in [bones_action, deforms_action]:
		if action is not None:
			for fcurve in action.fcurves:
				for kf in fcurve.keyframe_points:
					keyframe_times.add(int(kf.co[0]))

	keyframe_times = sorted(keyframe_times)

	# The anim editor in SMFX detects when the file changes, but writing all the text
	# using file.write updates the file multiple times
	# We want to write it all in one call, so we will build the whole string first, and then just call file.write() once

	text = f"length {keyframe_times[-1] + 1}\n"
	if armature.spore_anim.requirements:
		text += f"branchPredicate {requirements_to_string(armature.spore_anim)}\n"
	text += "\n"

	event_names = {ev: f"event{i}" for i, ev in enumerate(armature.spore_anim.events)}

	text += "".join(event_to_string(name, event) for event, name in event_names.items())

	if event_names:
		text += "\n"

	times = list(keyframe_times)
	channels_output = []
	for channel in armature.spore_anim.channels:
		bone_query = [b for b in armature_object.pose.bones if b.name == channel.name]
		if not bone_query:
			show_message_box(f"Bone named '{channel.name}' does not exist", "Error")
			return {'CANCELLED'}

		bone = bone_query[0]
		events = [ev for ev in armature.spore_anim.events if ev.channel_name == channel.name]
		event_times = [ev.play_frame for ev in events]
		channel_times = sorted(set(keyframe_times) | set(event_times))
		times.extend(event_times)

		anim_names = []
		if channel.primary_capability in anim_bone_config.ANIMATION_NAMES:
			anim_names = anim_bone_config.ANIMATION_NAMES[channel.primary_capability]

		channels_output.append(AnimChannelOutput(armature_object, channel, bone, events, channel_times, anim_names))

	times = sorted(set(times))
	for t in times:
		scene.frame_set(t)
		for c in channels_output:
			if c.has_time(t):
				c.add_position_keyframe()
				c.add_rotation_keyframe()
				c.add_rigblock_keyframe()
				c.channel_info_flags.append(c.channel.keyframe_info_flags)

	for channel_output in channels_output:
		text += f"{channel_header(channel_output.channel)}\n"
		
		if channel_output.channel.secondary_type != "none":
			text += f"\t{secondary_command(channel_output.channel)}\n"

		text += "\tinfo\n"
		text += "".join(info_keyframe_to_string(t, channel_output.events, event_names, info_flags)
						for t, info_flags in zip(channel_output.channel_times, channel_output.channel_info_flags))
		text += "\tend\n"

		text += "\tpos"
		if channel_output.channel.relative_pos:
			text += " -relative"
		if channel_output.channel.flag_700:
			text += " -flags 0x700"
		if channel_output.channel.scale_mode != 'none':
			text += f" -scaleMode {channel_output.channel.scale_mode}"

		text += f"\n{channel_output.position_text}\tend\n"

		text += "\trot"
		if channel_output.channel.relative_rot:
			text += " -relative"
		if channel_output.channel.scale_mode != 'none':
			text += f" -scaleMode {channel_output.channel.scale_mode}"

		text += f"\n{channel_output.rotation_text}\tend\n"

		for name in channel_output.rigblock_names:
			text += f"\trigblock {name.split('_')[-1]}\n{channel_output.rigblocks_text[name]}\tend\n"

		text += "end\n"

	scene.frame_set(current_frame)

	file.write(text)

	return {'FINISHED'}
