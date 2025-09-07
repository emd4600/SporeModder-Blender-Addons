import bpy
import os
import re
from .prop_base import PropFile, Property, Hash, ResourceKey
from .message_box import show_message_box, show_multi_message_box


def get_export_collection():
	active_collection = bpy.context.view_layer.active_layer_collection.collection
	if active_collection.name == "Master Collection":
		active_collection = None
	
	# Try collection of active object
	if not active_collection:
		active_obj = bpy.context.active_object
		if active_obj:
			for coll in bpy.data.collections:
				if active_obj.name in coll.objects and coll.name != "Prop_t":
					active_collection = coll

	# Try first user collection in scene (not master collection)
	if not active_collection:
		for coll in bpy.data.collections:
			active_collection = coll
			break

	# If active collection is Prop_t, try to set to its parent
	if active_collection:
		if active_collection.name.lower() == "prop_t":
			parent = getattr(bpy.context.view_layer.active_layer_collection, "parent", None)
			if parent:
				active_collection = parent.collection

	return active_collection

def get_vertgroup_first_vert(obj, group_name):
	"""
	Return the index of the first vertex assigned to a given vertex group name in a mesh object.
	Returns None if not found.
	"""
	vgroups = obj.vertex_groups
	verts = obj.data.vertices
	# Find the vertex group index by name
	vg_idx = None
	for vg in vgroups:
		if vg.name == group_name:
			vg_idx = vg.index
			break
	if vg_idx is None:
		return None
	# Find the first vertex assigned to this group
	for v in verts:
		for g in v.groups:
			if g.group == vg_idx:
				return v.index
	return None

def get_vertex_edge_map(obj):
	"""
	Given a mesh object, returns a dict mapping each vertex index to a list of vertex indices it is connected to by an edge.
	"""
	edge_map = {}
	edges = obj.data.edges
	for v in obj.data.vertices:
		edge_map[v.index] = []
	for edge in edges:
		v1, v2 = edge.vertices
		edge_map[v1].append(v2)
		edge_map[v2].append(v1)
	return edge_map

def get_vertex_connection_bools(obj):
	"""
	Returns a dict mapping each vertex index to a list of bools, where each bool indicates
	whether that vertex is connected to each other vertex (by index order), including itself (always False).
	"""
	edge_map = get_vertex_edge_map(obj)
	num_verts = len(obj.data.vertices)
	connection_bools = {}
	for idx in range(num_verts):
		bools = []
		for j in range(num_verts):
			if idx == j:
				bools.append(False)
			else:
				bools.append(j in edge_map[idx])
		connection_bools[idx] = bools
	return connection_bools

# Handle complex behavior for exporter meshes
def export_mesh_properties(obj, propfile):
	vgroups = obj.vertex_groups
	verts = obj.data.vertices
	# Store which groups to store as vector3 or vector3s
	single_vectors = {}
	group_vectors = {}

	# Loop through vertex groups. if a vertex group has multiple verts assigned, export it as a vector3s.
	# Otherwise, if only 1 vert assigned, export as a vector3
	for vg in vgroups:
		name = vg.name
		assigned_verts = [v for v in verts if vg.index in [g.group for g in v.groups]]
		if len(assigned_verts) > 1:
			positions = [tuple(obj.matrix_world @ v.co) for v in assigned_verts]
			# set all Z values to 5 for TribeChatAreas
			if (name.lower() == "tribechatareas"):
				positions = [(x, y, 5) for (x, y, z) in positions]
			group_vectors[name] = positions
		elif len(assigned_verts) == 1:
			pos = tuple(obj.matrix_world @ assigned_verts[0].co)
			single_vectors[name] = pos
	
	# Export vector3 properties
	for name, pos in single_vectors.items():
		if (name.lower() == "cityhall"): continue
		propfile.add_property(Property(name, pos, 'vector3'))
	# Export vector3s properties
	for prefix, positions in group_vectors.items():
		propfile.add_property(Property(prefix, positions, 'vector3s'))

	if obj.name == "Buildings":
		export_building_links(obj, propfile)


# Special handling for "Buildings" mesh: export BuildingLink# bools and cityhall stuff item
def export_building_links(obj, propfile):
	cityhall_pos = propfile.get_value("cityHall", (0,0,0))
	propfile.add_property(Property("cityHallDiasHeight", cityhall_pos[2], "float"))

	# Export BuildingLink# bools for each vertex
	connection_bools = get_vertex_connection_bools(obj)
	for idx, bools in connection_bools.items():
		propfile.add_property(Property(f"BuildingLink{idx}", bools, "bools"))


def export_metadata_properties(prop_t_coll, propfile):
	for obj in prop_t_coll.objects:
		if obj.type == 'EMPTY' and obj.name == '.prop_t':
			for meta in obj.keys():
				if meta not in '_RNA_UI':  # Don't export internal blender stuff
					value = obj[meta]
					type = meta.split()[0]
					key = meta.split()[1]
					propfile.add_property(Property(key, value, type))



def export_citywall(filepath):
	warnings = set()
	collection = get_export_collection()
	if not collection or len(collection.objects) == 0:
		show_message_box("No valid collection with objects found for export.", title="Export Error", icon="ERROR")
		return {'CANCELLED'}
	warnings.add(f"Exporting from collection: {collection.name}") # Temp
	propfile = PropFile(filepath, True)

	propfile.add_property(Property("description", f"\"{collection.name}\"", 'string16'))
	for obj in collection.objects:
		if obj.name.startswith('temp_'):
			continue
		elif obj.type == 'EMPTY':
			# Export radius properties from circle empties
			if obj.empty_display_type == 'CIRCLE':
				propfile.add_property(Property(obj.name, obj.empty_display_size, 'float'))
			# Export vector3 properties from cube empties
			elif obj.empty_display_type == 'CUBE':
				propfile.add_property(Property(obj.name, tuple(obj.location), 'vector3'))
			# Export other empties as vector3
			elif obj.empty_display_type not in ['CUBE', 'CIRCLE']:
				propfile.add_property(Property(obj.name, tuple(obj.location), 'vector3'))

		elif obj.type == 'MESH':
			export_mesh_properties(obj, propfile)

	# Export custom metadata properties from the '.prop_t' empty in the 'Prop_t' collection
	prop_t_coll = None
	for child in collection.children:
		if child.name == "Prop_t":
			prop_t_coll = child
			break
	if prop_t_coll:
		export_metadata_properties(prop_t_coll, propfile)

	if not propfile.properties:
		warnings.add("No valid properties found for export.")

	# Write out to file only if there are properties
	if propfile.properties:
		propfile.write(filepath)
		if warnings:
			show_multi_message_box(warnings, title=f"Exported with {len(warnings)} warnings", icon="ERROR")
		return {'FINISHED'}
	else:
		show_message_box("No properties to write to file.", title="Export Error", icon="ERROR")
		return {'CANCELLED'}
