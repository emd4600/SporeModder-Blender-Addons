__author__ = 'Allison'

import bpy
from mathutils import Vector
import os

def show_message_box(message, title="Import Error", icon='ERROR'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


# MuscleGroup = set of positions, percentages, and radii
def parse_muscle_group(filepath):
    mode = None
    offsets = []
    percentages = []
    radii = []
    with open(filepath, 'r') as file:
        for line in file:
            line = line.strip()
            if line.startswith('vector3s muscleOffsets'):
                mode = 'offsets'
                continue
            elif line.startswith('floats musclePercentages'):
                mode = 'percentages'
                continue
            elif line.startswith('floats muscleRadii'):
                mode = 'radii'
                continue
            elif line == 'end':
                mode = None
                continue

            # Act based on the current mode
            if mode == 'offsets' and line.startswith('('):
                vals = line.strip('()').split(',')
                offsets.append(Vector([float(v) for v in vals]))
            elif mode == 'percentages' and line:
                percentages.append(float(line))
            elif mode == 'radii' and line:
                radii.append(float(line))
    
    return offsets, percentages, radii


def import_muscle_group(filepath, curve_name):
    """
        Muscle groups are imported as polygon paths (curves)
    """
    offsets, percentages, radii = parse_muscle_group(filepath)
    n = len(offsets)
    if n != len(percentages) or n != len(radii):
        show_message_box("muscleOffsets, musclePercentages, and muscleRadii must have the same length.", "Import Error")
        return {'CANCELLED'}

    curve_data = bpy.data.curves.new(curve_name, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.fill_mode = 'FULL'
    curve_data.use_fill_caps = True
    curve_data.bevel_depth = 1.0
    curve_data.bevel_resolution = 2
    curve_data.bevel_mode = 'ROUND'

    spline = curve_data.splines.new(type='POLY')
    spline.points.add(n-1)
    for i in range(n):
        # place points along -Y axis, offset by muscleOffsets
        pos = Vector((offsets[i][0], -percentages[i], offsets[i][2]))
        spline.points[i].co = (pos.x, pos.y, pos.z, 1)
        spline.points[i].radius = radii[i]

    # create curve from data
    curve_obj = bpy.data.objects.new(curve_name, curve_data)
    bpy.context.scene.collection.objects.link(curve_obj)
    bpy.context.view_layer.objects.active = curve_obj

    return {'FINISHED'}



# Muscle = collection of muscle groups
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
            if line.startswith('keys muscleGroups'):
                mode = 'groups'
                continue
            elif line == 'end':
                mode = None
                continue
        
            # Pull in muscle group file paths
            if mode == 'groups' and line:
                # Create full path to muscle group file
                fname = line.split('!')[1].split('.')[0]  # filename without extension
                folder = line.split('!')[0]
                parent_dir = os.path.dirname(base_dir)
                group_path = os.path.join(parent_dir, folder, fname + '.prop.prop_t')
                muscle_groups.append(group_path)
    return muscle_groups


def import_muscle_file(filepath):
    """
        Import a Muscle file containing multiple muscle groups.
    """
    muscle_groups = parse_muscle_file(filepath)
    if not muscle_groups:
        show_message_box("No muscleGroups found in file.", "Import Error")
        return {'CANCELLED'}

    # Create new collection for this muscle file
    collection_name = os.path.splitext(os.path.basename(filepath))[0]
    collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(collection)

    imported_objs = []
    for group_path in muscle_groups:
        if not os.path.exists(group_path):
            show_message_box(f"Muscle group file not found:\n{group_path}", "Import Error")
            continue
        # Use group file name for curve name
        curve_name = os.path.splitext(os.path.basename(group_path))[0]
        result = import_muscle_group(group_path, curve_name)
        # Get the last created object (the curve)
        curve_obj = bpy.context.view_layer.objects.active
        if curve_obj is not None:
            # Move to collection
            collection.objects.link(curve_obj)
            bpy.context.scene.collection.objects.unlink(curve_obj)
            imported_objs.append(curve_obj)

    if not imported_objs:
        show_message_box("No muscle groups imported.", "Import Error")
        return {'CANCELLED'}

    # Set active object to first imported curve
    bpy.context.view_layer.objects.active = imported_objs[0]
    return {'FINISHED'}

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
    return import_muscle_group(filepath, os.path.splitext(os.path.basename(filepath))[0])
