__author__ = 'Allison'

import bpy
import os
import re
from mathutils import Matrix, Vector


def show_message_box(message, title="Import Error", icon='ERROR'):
	def draw(self, context):
		self.layout.label(text=message)
	bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def import_muscle_group(filepath, curve_name, filepath_max=None):
	"""
	Muscle groups are imported as polygon paths (curves).
	If filepath_max is provided, creates a shape key "max" that moves/scales the points to match max data.
	"""

	from .prop_base import PropFile
	propfile : PropFile = PropFile(filepath)
	offsets = propfile.get_value("muscleOffsets")
	percentages = propfile.get_value("musclePercentages")
	radii = propfile.get_value("muscleRadii")

	n = len(offsets)
	if n != len(percentages) or n != len(radii):
		show_message_box("muscleOffsets, musclePercentages, and muscleRadii must have the same length.", "Import Error")
		return {'CANCELLED'}

	# Remove suffixes from curve name if max file provided
	if filepath_max is not None:
		# Match last _<number> at end
		match = re.search(r'_(\d+)$', curve_name)
		suffix = ''
		base_name = curve_name
		if match:
			suffix = match.group(0)  # e.g. '_12'
			base_name = curve_name[:match.start()]
		# Check for hardcoded suffixes and remove them
		if base_name.endswith('Min'):
			base_name = base_name[:-3]
		else:
			# Check for number+'a' at end (e.g. '12a')
			num_a_match = re.search(r'(\d+)a$', base_name)
			if num_a_match:
				base_name = base_name[:num_a_match.start()]
		curve_name = base_name + suffix

	curve_data = bpy.data.curves.new(curve_name, type='CURVE')
	curve_data.dimensions = '3D'
	curve_data.fill_mode = 'FULL'
	curve_data.use_fill_caps = True

	curve_data.bevel_mode = 'ROUND'
	curve_data.bevel_depth = 1.0
	curve_data.bevel_resolution = 2
	curve_data.resolution_u = 6

	spline = curve_data.splines.new(type='POLY')
	spline.points.add(n-1)
	for i in range(n):
		# place points along -Y axis, offset by muscleOffsets
		pos = Vector((offsets[i][0], -percentages[i], offsets[i][2]))
		spline.points[i].co = (pos.x, pos.y, -pos.z, 1)
		spline.points[i].radius = radii[i]

	# create curve from data
	curve_obj = bpy.data.objects.new(curve_name, curve_data)
	bpy.context.scene.collection.objects.link(curve_obj)
	bpy.context.view_layer.objects.active = curve_obj

	# If max file provided, create shape key "max"
	if filepath_max is not None:
		propfile_max : PropFile = PropFile(filepath_max)
		offsets_max = propfile_max.get_value("muscleOffsets")
		percentages_max = propfile_max.get_value("musclePercentages")
		radii_max = propfile_max.get_value("muscleRadii")
		
		if len(offsets_max) != n or len(percentages_max) != n or len(radii_max) != n:
			show_message_box("Max muscle group does not match base group length, continuing without morphs.", "Import Error")
			return {'FINISHED'}

		# Add basis shape key if not present
		if not curve_obj.data.shape_keys:
			curve_obj.shape_key_add(name="Basis")
		# Add max shape key
		max_key = curve_obj.shape_key_add(name="max")
		# Move points in shape key
		for i in range(n):
			pos_max = Vector((offsets_max[i][0], -percentages_max[i], offsets_max[i][2]))
			max_key.data[i].co = (pos_max.x, pos_max.y, pos_max.z)
			max_key.data[i].radius = radii_max[i]

	return {'FINISHED'}


#----------------------------------------------------------------------------------------------


# Muscle = collection of muscle group prop files
def parse_muscle_file(filepath):
	"""
	Parse a Muscle file and return a list of muscle group file paths.
	"""
	mode = None
	muscle_groups = []
	base_dir = os.path.dirname(filepath)
	with open(filepath, 'r') as file:
		for line in file:
			line = line.strip()
			if line.lower().startswith('keys musclegroups'):
				mode = 'groups'
				continue
			elif line.lower() == 'end':
				mode = None
				continue
		
			# Pull in muscle group file paths
			if mode == 'groups' and line:
				# Create full path to muscle group file
				fname = line.split('!')[1].split('.')[0]  # filename without extension
				#folder = line.split('!')[0]
				#parent_dir = os.path.dirname(base_dir)
				#group_path = os.path.join(parent_dir, folder, fname + '.prop.prop_t')
				group_path = os.path.join(base_dir, fname + '.prop.prop_t')
				muscle_groups.append(group_path)
	return muscle_groups


def import_muscle_file(filepath):
	"""
	Import a Muscle file containing multiple muscle groups.

	Supports limited importing of min/max variants.
	TODO: generate a min/max action that slides between basis and max shapes for easy previewing.
	"""

	# Check for possible min/max variant of muscle file
	parent_dir = os.path.dirname(filepath)
	muscle_groups = []
	muscle_groups_max = []
	minmax = find_min_max_variant(parent_dir, os.path.basename(filepath).split('.')[0])

	if len(minmax) == 3:
		muscle_groups= parse_muscle_file(os.path.join(parent_dir, minmax[0] + '.prop.prop_t'))
		muscle_groups_max = parse_muscle_file(os.path.join(parent_dir, minmax[1] + '.prop.prop_t'))
	else:
		muscle_groups = parse_muscle_file(filepath)


	if not muscle_groups:
		show_message_box("No muscleGroups found in file.", "Import Error")
		return {'CANCELLED'}

	# Create new collection for this muscle file
	collection_name = os.path.basename(filepath).split('.')[0]
	if len(minmax) == 3:
		collection_name = minmax[2]
	collection = bpy.data.collections.new(collection_name)
	bpy.context.scene.collection.children.link(collection)

	imported_objs = []
	idx = 0
	for group_path in muscle_groups:
		if not os.path.exists(group_path):
			show_message_box(f"Muscle group file not found:\n{group_path}", "Import Error")
			continue
		# Use group file name for curve name
		curve_name = os.path.basename(group_path).split('.')[0]
		# Import the muscle group with or without a max variant
		if len(minmax) == 3:
			result = import_muscle_group(group_path, curve_name, muscle_groups_max[idx])
		else:
			result = import_muscle_group(group_path, curve_name)
		# Get the last created object (the curve)
		curve_obj = bpy.context.view_layer.objects.active
		if curve_obj is not None:
			# Move to collection
			collection.objects.link(curve_obj)
			bpy.context.scene.collection.objects.unlink(curve_obj)
			imported_objs.append(curve_obj)
		idx += 1

	if not imported_objs:
		show_message_box("No muscle groups imported.", "Import Error")
		return {'CANCELLED'}

	# Set active object to first imported curve
	bpy.context.view_layer.objects.active = imported_objs[0]

	if len(minmax) == 3:
		# Generate MinMax action for all curves in the collection
		generate_minmax_action(collection)

	return {'FINISHED'}

#----------------------------------------------------------------------------------------------

# TODO: automatically detect min and max muscle files,
# and import min as the base and max as a shape key set.
def import_muscle_group_or_file(filepath):
	"""
	Import either a muscle file or a muscle group file.

	Importing a muscle file will create a collection of muscle groups,
	importing a muscle group file will create a single curve object.
	"""
	# If file contains 'keys muscleGroups', import as a muscle file
	with open(filepath, 'r') as file:
		for line in file:
			if line.strip().startswith('keys muscleGroups'):
				return import_muscle_file(filepath)
	# Otherwise, import as singular muscle group
	return import_muscle_group(filepath, os.path.basename(filepath).split('.')[0])


# Insane muscle parsing func
# Takes a muscle directory and filename (no extension) and finds min/max variants
# Maxis uses an insane naming convention for muscle groups so it needs to work with that.
# this asshole fucked me over after 
def find_min_max_variant(directory, filename):
	"""
	Given a filename and its directory, returns [min_name, max_name, base_name] if both min/max exist,
	or [original_name] if only one exists. Names returned sans extension.
	"""
	# Suffix pairs
	pairs = [
		(("-Min", "Min", "a", "", ""), ("-Max", "Max", "b", "E", "_extent"))
	]
	# Determine base name and suffix
	base = filename
	min_suffix = None
	max_suffix = None

	# Check which suffix is present
	for min_s, max_s in zip(pairs[0][0], pairs[0][1]):
		if filename.endswith(min_s) and min_s != "":
			base = filename[:-len(min_s)]
			min_suffix = min_s
			max_suffix = max_s
			break
		elif filename.endswith(max_s):
			base = filename[:-len(max_s)]
			min_suffix = pairs[0][0][pairs[0][1].index(max_s)]
			max_suffix = max_s
			break
	else:
		# No suffix, treat as min with ""
		min_suffix = ""
		# 2 possible Max suffixes from here, check for both.
		max_suffix = "E"

		max_path = os.path.join(directory, base + max_suffix + ".prop.prop_t")
		if not os.path.exists(max_path):
			max_suffix = "_extent" 

	# Compose possible filenames
	min_name = base + min_suffix
	max_name = base + max_suffix

	# Check which files exist
	min_path = os.path.join(directory, min_name + ".prop.prop_t")
	max_path = os.path.join(directory, max_name + ".prop.prop_t")

	min_exists = os.path.exists(min_path)
	max_exists = os.path.exists(max_path)

	if min_exists and max_exists:
		return [min_name, max_name, base]
	elif min_exists:
		return [min_name, base]
	elif max_exists:
		return [max_name, base]
	else:
		# Only original filename exists (maybe with a different suffix)
		orig_path = os.path.join(directory, filename + ".prop.prop_t")
		print(orig_path)
		if os.path.exists(orig_path):
			return [filename]
		return []


def generate_minmax_action(collection):
	"""
	Generates or updates an action named 'MinMax' that animates all curve objects in the collection,
	morphing their 'max' shape key from 0 (frame 0) to 1 (frame 30).
	"""
	action_name = "MinMax"
	action = bpy.data.actions.get(action_name)
	if not action:
		action = bpy.data.actions.new(action_name)
		action.use_fake_user = True

	for obj in collection.objects:
		if obj.type == 'CURVE' and obj.data.shape_keys:
			key_block = obj.data.shape_keys.key_blocks.get("max")
			if key_block:
				# Ensure animation data exists
				if not obj.data.shape_keys.animation_data:
					obj.data.shape_keys.animation_data_create()
				obj.data.shape_keys.animation_data.action = action

				data_path = key_block.path_from_id("value")
				fcurve = action.fcurves.find(data_path)
				if not fcurve:
					fcurve = action.fcurves.new(data_path)
				# Insert keyframes for value 0 at frame 0 and value 1 at frame 30
				fcurve.keyframe_points.insert(0, 0)
				fcurve.keyframe_points.insert(30, 1)
