__author__ = 'Allison'

import bpy
import os
from mathutils import Matrix, Vector
import mathutils.geometry
from .message_box import show_message_box, show_multi_message_box

def get_active_collection_and_curves():
	# Try selected collection
	collection = None
	curves = []
	if bpy.context.view_layer.active_layer_collection:
		collection = bpy.context.view_layer.active_layer_collection.collection
		curves = [obj for obj in collection.objects if obj.type == 'CURVE']
		if curves:
			return collection, curves
	# Try selected object
	obj = bpy.context.active_object
	if obj and obj.type == 'CURVE':
		# Find its collection
		for coll in bpy.data.collections:
			if obj.name in coll.objects:
				curves = [o for o in coll.objects if o.type == 'CURVE']
				if curves:
					return coll, curves
	# Fallback: first collection starting with "Muscle"
	for coll in bpy.data.collections:
		if coll.name.lower().startswith("muscle"):
			curves = [obj for obj in coll.objects if obj.type == 'CURVE']
			if curves:
				return coll, curves
	return None, []

def ensure_muscle_name(name):
	if name.lower().startswith("muscle"):
		return "Muscle" + name[6:]
	return "Muscle_" + name

def write_group_file(filepath, offsets, percentages, radii):
	filename = os.path.basename(filepath).split(".")[0]
	with open(filepath, 'w') as f:
		f.write("key parent editor_muscles~!GroupTemplate.prop\n")
		f.write(f'string16 description "{filename}"\n')
		f.write("vector3s muscleOffsets\n")
		for v in offsets:
			f.write(f"\t({v[0]:.6f},{v[1]:.6f},{v[2]:.6f})\n")
		f.write("end\n")
		f.write("floats musclePercentages\n")
		for p in percentages:
			f.write(f"\t{p:.6f}\n")
		f.write("end\n")
		f.write("floats muscleRadii\n")
		for r in radii:
			f.write(f"\t{r:.6f}\n")
		f.write("end\n")

def get_curve_data(curve_obj, shape_key=None):
	spline = curve_obj.data.splines[0]
	offsets = []
	percentages = []
	radii = []

	key_block = None
	if shape_key is not None and curve_obj.data.shape_keys:
		key_block = curve_obj.data.shape_keys.key_blocks.get(shape_key)

	points = []
	interp_radii = []
	if spline.type == 'POLY':
		points = spline.points
		for i in range(len(points)):
			if key_block:
				co = key_block.data[i].co
				radius = key_block.data[i].radius
			else:
				co = points[i].co
				radius = points[i].radius
			offsets.append((co[0], 0.0, -co[2]))
			percentages.append(-co[1])
			radii.append(radius)
	else:
		# Bezier/NURBS: interpolate points and radii
		if len(spline.bezier_points) >= 2:
			r = spline.resolution_u + 1
			segments = len(spline.bezier_points) - 1  # assume non-cyclic

			def get_radius(idx):
				if key_block:
					return key_block.data[spline.bezier_points[idx].index].radius
				else:
					return spline.bezier_points[idx].radius

			for i in range(segments):
				inext = (i + 1) % len(spline.bezier_points)
				iprev = i - 1 if i > 0 else i

				if key_block:
					knot1 = key_block.data[spline.bezier_points[i].index].co
					handle1 = key_block.data[spline.bezier_points[i].index].handle_right
					handle2 = key_block.data[spline.bezier_points[inext].index].handle_left
					knot2 = key_block.data[spline.bezier_points[inext].index].co
				else:
					knot1 = spline.bezier_points[i].co
					handle1 = spline.bezier_points[i].handle_right
					handle2 = spline.bezier_points[inext].handle_left
					knot2 = spline.bezier_points[inext].co

				rad_prev = get_radius(iprev)
				rad1 = get_radius(i)
				rad2 = get_radius(inext)

				_points = mathutils.geometry.interpolate_bezier(knot1, handle1, handle2, knot2, r)
				points.extend(_points)
				# Interpolate radii for each segment
				for j in range(r):
					t = j / (r - 1) if r > 1 else 0
					# For start/end points, use the actual radius
					if j == 0:
						interp_radius = rad1
					elif j == r - 1:
						interp_radius = rad2
					else:
						# Cubic bezier interpolation for radius
						interp_radius = (
							(1 - t) ** 3 * rad1 +
							3 * (1 - t) ** 2 * t * ((rad1 + rad_prev) / 2) +
							3 * (1 - t) * t ** 2 * ((rad1 + rad2) / 2) +
							t ** 3 * rad2
						)
					interp_radii.append(interp_radius)

		# Add the points and interpolated radii to the data lists
		for i in range(len(points)):
			co = points[i]
			offsets.append((co.x, 0.0, -co.z))
			percentages.append(-co.y)
			radii.append(interp_radii[i] if i < len(interp_radii) else 0.08)

	return offsets, percentages, radii


def write_muscle_file(muscle_filepath, group_filepaths):
	filename = os.path.basename(muscle_filepath).split(".")[0]
	with open(muscle_filepath, 'w') as f:
		f.write(f'string16 description "{filename}"\n')
		f.write("keys muscleGroups\n")
		for group_path in group_filepaths:
			#folder = os.path.basename(os.path.dirname(group_path))
			folder = "editor_muscles~" # Hardcoded to allow for intermediate export folders
			fname = os.path.splitext(os.path.basename(group_path))[0]
			f.write(f"\t{folder}!{fname}\n")
		f.write("end\n")

# General export func
def export_muscle(directory, export_symmetric):
	warnings = set()
	collection, curves = get_active_collection_and_curves()
	if not collection or not curves:
		warnings.add("No muscle collection or curve found for export.")
		return {'CANCELLED'}

	# Warn if any curve has unapplied transformations
	for curve_obj in curves:
		if curve_obj.matrix_world != Matrix.Identity(4):
			warnings.add(f"Curve '{curve_obj.name}' has unapplied transformations.")

	muscle_name = ensure_muscle_name(collection.name)
	export_dir = directory if directory else os.path.dirname(bpy.data.filepath)
	has_max = any(obj.data.shape_keys and "max" in obj.data.shape_keys.key_blocks for obj in curves)

	variants = ["Min", "Max"] if has_max else [""]

	for variant in variants:
		group_filepaths = []
		for idx, curve_obj in enumerate(curves):
			base_name = muscle_name.replace("Muscle_", "").replace("Muscle", "")
			group_name = f"Group_{base_name}{variant}_{idx}"
			group_filepath = os.path.join(export_dir, group_name + ".prop.prop_t")
			shape_key = "max" if variant == "Max" else None

			offsets, percentages, radii = get_curve_data(curve_obj, shape_key)
			write_group_file(group_filepath, offsets, percentages, radii)
			group_filepaths.append(group_filepath)

			# Symmetric export for group
			if export_symmetric:
				sym_offsets = [(-x, y, z) for (x, y, z) in offsets]
				sym_group_filepath = os.path.join(export_dir, group_name + "-symmetric.prop.prop_t")
				write_group_file(sym_group_filepath, sym_offsets, percentages, radii)

		# Normal muscle file
		muscle_filename = f"{muscle_name}{variant}.prop.prop_t"
		muscle_filepath = os.path.join(export_dir, muscle_filename)
		write_muscle_file(muscle_filepath, group_filepaths)

		# Symmetric muscle file
		if export_symmetric:
			sym_group_paths = [
				os.path.splitext(p)[0] + "-symmetric.prop.prop_t"
				for p in group_filepaths
			]
			sym_muscle_filename = f"{muscle_name}{variant}-symmetric.prop.prop_t"
			sym_muscle_filepath = os.path.join(export_dir, sym_muscle_filename)
			write_muscle_file(sym_muscle_filepath, sym_group_paths)

	if warnings: show_multi_message_box(warnings, title=f"Exported with {len(warnings)} warnings", icon="ERROR")
	else: show_message_box(f"Exported {len(curves)} group(s) and {len(variants)} muscle file(s) to {export_dir}", title="Export Complete", icon='INFO')
	return {'FINISHED'}