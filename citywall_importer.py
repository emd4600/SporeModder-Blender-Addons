__author__ = 'Allison'

import bpy, re, math, os
from . import geo_nodes as geo
from . import mod_paths

# TODO: implement cityHallDiasHeight for cityhall Z height? and export accordingly
# Also store other imported paramters for export, maybe as metadata or empty objects

def import_citywall(filepath):
	print("Importing from:", filepath)
	mod_paths.set_mod_folder(filepath)

	from .prop_base import PropFile
	propfile : PropFile = PropFile(filepath)

	geonode_buildings = geo.create_geonode_buildings()
	geonode_turrets = geo.create_geonode_turrets()
	geonode_decor = geo.create_geonode_decor()
	geonode_gates = geo.create_geonode_gates()

	# Create new collection for the imported object
	collection_name = os.path.basename(filepath).split('.')[0]
	collection = bpy.data.collections.new(collection_name)
	bpy.context.scene.collection.children.link(collection)

	collection_properties = bpy.data.collections.new("Prop_t")
	collection.children.link(collection_properties)
	# TODO: Collapse Category... doesnt seem to be possible

	# Import radius properties as circle empties
	for prop in propfile.get_properties(['radiusInner', 'radiusOuter', 'terraformClearFloraRadius', 'tribeGridScale']):
		prop.mark()
		bpy.ops.object.empty_add(type='CIRCLE', location=(0, 0, 0), rotation=(math.radians(90), 0, 0))
		obj = bpy.context.active_object
		move_to_collection(obj, collection)
		obj.name = prop.key
		obj.empty_display_size = prop.value
		if prop.is_key('tribeGridScale'):
			obj.empty_display_type = 'PLAIN_AXES'


	# Import single vector3 locations as empty objects
	for prop in propfile.get_properties_by_type('vector3'):
		prop.mark()
		# City hall will be set to show up in the buildings list, no need to add it here.
		if prop.is_key('City_Hall'):
			continue
		# Make the "Gates" into a mesh with vert groups instead
		if "_gate" in prop.key.lower():
			continue
		#------------------------------
		bpy.ops.object.empty_add(type='CUBE', location=prop.value, radius=2)
		obj = bpy.context.active_object
		move_to_collection(obj, collection)
		obj.name = prop.key
		#------------------------------
		if prop.is_key('modelOffset'):
			obj.empty_display_type = 'PLAIN_AXES'
		elif prop.is_key('totemPolePosition'):
			obj.empty_display_type = 'SINGLE_ARROW'
			obj.empty_display_size = 10
		elif prop.is_key('animalPenPosition'):
			obj.empty_display_type = 'CIRCLE'
			obj.rotation_euler = (math.radians(90), 0, 0)
			obj.empty_display_size = 7.5
		elif prop.is_key('eggPenPosition'):
			obj.empty_display_size = 1.0
		elif prop.is_key('foodMatPosition'):
			obj.scale.z = 0.5
		elif prop.is_key('tribeGridScale'):
			obj.empty_display_size = 1.0
		elif prop.key.startswith('0x') or prop.is_key('modelLevelParams'):
			obj.empty_display_type = 'PLAIN_AXES'
			obj.empty_display_size = 1.0

	# Import vector3s as mesh object point clouds with unconnected vertices
	for prop in propfile.get_properties_by_type('vector3s'):
		prop.mark()
		# Handle separately.
		if prop.is_key('Side_Gates'):
			continue
		mesh = bpy.data.meshes.new(prop.key)
		obj = bpy.data.objects.new(prop.key, mesh)
		bpy.context.scene.collection.objects.link(obj)

		# Create verts from vector list
		verts = prop.value
		edges = []

		# Negate the "5" z values of the tribal chat areas. Revert on export.
		if prop.is_key('TribeChatAreas'):
			for idx, vert in enumerate(verts):
				verts[idx] = (vert[0], vert[1], 1)

		# For Buildings, connect edges according to BuildingLink*
		if prop.is_key('Buildings'):
			# Add in City hall position
			cityhallpos = propfile.get_value('City_Hall')
			cityhalldiasheight = propfile.get_property('cityHallDiasHeight')
			if (cityhalldiasheight):
				cityhalldiasheight.mark()
				cityhallpos[2] = propfile.get_value('cityHallDiasHeight', cityhallpos[2])
			verts.insert(0, cityhallpos)

			bld_links = propfile.get_properties_by_prefix('BuildingLink')
			# loop thru buildings
			for idx_src in range(len(verts)):
				# loop thru connections
				for idx_connect in range(len(bld_links[idx_src].value)):
					bld_links[idx_src].mark()
					if bld_links[idx_src].value[idx_connect]:
						# Only add edge if both indices are valid
						if idx_src < len(verts) and idx_connect < len(verts):
							edges.append((idx_src, idx_connect))
					else:
						pass
						if (idx_src, idx_connect) in edges:
							edges.remove((idx_src, idx_connect))
						if (idx_connect, idx_src) in edges:
							edges.remove((idx_connect, idx_src))
		
		# For Turrets, connect edges in order
		if prop.is_key('Turrets'):
			for idx in range(len(verts) - 1):
				edges.append((idx, idx + 1))
			if len(verts) > 1:
				edges.append((len(verts) - 1, 0))

		# Build mesh
		mesh.from_pydata(verts, edges, [])
		mesh.update()
		bpy.context.view_layer.objects.active = obj
		move_to_collection(obj, collection)

		# Add each vertex to its own vertex group labeled after its property name + idx
		for idx in range(len(verts)):
			if prop.is_key('Buildings') and idx == 0:
				name = "CityHall"
			else: name = prop.key + str(idx)

			vg = obj.vertex_groups.new(name=name)
			vg.add([idx], 1.0, 'ADD')

		# Assign geometry nodes
		if prop.is_key('Buildings') or prop.is_key('ToolPositions'):
			geo.object_set_geo_node(obj, geonode_buildings)
		elif prop.is_key('Turrets'):
			geo.object_set_geo_node(obj, geonode_turrets)
		elif prop.is_key('Decorations'):
			geo.object_set_geo_node(obj, geonode_decor)

	# Handle gates as one mesh.
	if (True):
		# Create verts from vector list
		verts = []
		edges = []
		vertgroupnames = []

		# Set up mesh
		mesh = bpy.data.meshes.new(prop.key)
		obj = bpy.data.objects.new(prop.key, mesh)
		bpy.context.scene.collection.objects.link(obj)

		# Find all gate properties and add to the mesh data
		for prop in propfile.get_properties_containing('_gate'):
			if prop.is_type('vector3s'):
				i = 0
				for item in prop.value:
					verts.append(item)
					vertgroupnames.append(prop.key + str(i))
					i += 1
			elif prop.is_type('vector3'):
				verts.append(prop.value)
				vertgroupnames.append(prop.key)

		# Build mesh
		mesh.from_pydata(verts, edges, [])
		mesh.update()
		bpy.context.view_layer.objects.active = obj
		move_to_collection(obj, collection)

		# Add each vertex to its own vertex group named after the vertgroupnames array
		for idx in range(len(verts)):
			groupname = vertgroupnames[idx]
			vg = obj.vertex_groups.new(name=groupname)
			vg.add([idx], 1.0, 'ADD')
		
		# Assign geometry node
		geo.object_set_geo_node(obj, geonode_gates)

	# for all unmarked properties, create a new empty object
	bpy.ops.object.empty_add(type='PLAIN_AXES')
	obj = bpy.context.active_object
	obj.name = ".prop_t"
	move_to_collection(obj, collection_properties)
	
	# Assign metadata to the object for each property
	# TODO: Make sure not to do this for any parent file properties
	from .prop_base import Hash, ResourceKey
	for prop in propfile.get_unmarked_properties():
		if prop.is_key("description"): continue
		meta_name = prop.type + " " + prop.key
		if isinstance(prop.value, (Hash, ResourceKey)) or not isinstance(prop.value, (int, float, dict, str, list)):
			obj[meta_name] = str(prop.value)
		elif isinstance(prop.value, list):
			listvalues = []
			for item in prop.value:
				if isinstance(item, (Hash, ResourceKey)) or not isinstance(item, (int, float, dict, str)):
					listvalues.append(str(item))
				else:
					listvalues.append(item)
			obj[meta_name] = listvalues
		else:
			obj[meta_name] = prop.value

	# Deselect all objects
	bpy.ops.object.select_all(action='DESELECT')

	return {'FINISHED'}



def move_to_collection(obj, collection):
	# Move the object to the specified collection
	collection.objects.link(obj)
	scene_collection = bpy.context.scene.collection
	if obj.name in scene_collection.objects:
		scene_collection.objects.unlink(obj)


