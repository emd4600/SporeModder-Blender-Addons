__Author__ = 'Allison'

import bpy
import math


# Geometry Nodes

def object_set_geo_node(obj, node_group):
	geo_mod = obj.modifiers.new(name="InstanceBuildings", type='NODES')
	geo_mod.node_group = node_group

# TODO: fix scaling to be handled local to the empty object, not along the mesh.
def create_geonode_buildings():
	return create_vertex_geonode(name = "Buildings", displaysize=2.5, scale=(1,1,1.5), offset=(0,0,3.75))

def create_geonode_turrets():
	return create_vertex_geonode(name = "Turrets", displaytype="SPHERE", displaysize=2.1,)

def create_geonode_decor():
	return create_vertex_geonode(name = "Decor", displaytype="SPHERE", scale=(1,1,0))

def create_geonode_gates():
	return create_vertex_geonode(name = "Gates", scale=(1,1,0.5), offset=(0,0,-0.5))

# Create a geometry node that places "empties" on mesh vertices
def create_vertex_geonode(name : str, displaytype='CUBE', displaysize=2, scale=(1,1,1), offset=(0,0,0), rotation=(0,0,0)):
	# Create and return a Geo Node to place Empties on building/tool locations
	# Create a new geometry node modifier
	node_group = bpy.data.node_groups.new('Instance' + name.capitalize() + "Group", 'GeometryNodeTree')

	# Create a temporary empty cube object to instance
	# NOTE: DO NOT EXPORT temp_ objects!
	temp_building = bpy.data.objects.new("temp_" + name.lower(), None)
	temp_building.empty_display_type = displaytype.upper()
	temp_building.hide_render = True
	temp_building.empty_display_size = displaysize
	bpy.context.scene.collection.objects.link(temp_building)
	temp_building.hide_set(True)

	# Add nodes
	nodes = node_group.nodes
	links = node_group.links

	# Group Input
	group_input = nodes.new(type="NodeGroupInput")
	group_input.location = (-400, 0)
	node_group.inputs.new('NodeSocketGeometry', "Geometry")

	# Point Instance
	point_instance = nodes.new(type="GeometryNodePointInstance")
	point_instance.location = (-200, -100)
	point_instance.inputs['Object'].default_value = temp_building

	# Transform
	transform = nodes.new(type="GeometryNodeTransform")
	transform.location = (0, -100)
	transform.inputs['Scale'].default_value = scale
	transform.inputs['Translation'].default_value = offset
	transform.inputs['Rotation'].default_value = (math.radians(rotation[0]), math.radians(rotation[1]), math.radians(rotation[2]))

	# Join Geometry
	join_geometry = nodes.new(type="GeometryNodeJoinGeometry")
	join_geometry.location = (200, 0)

	# Group Output
	group_output = nodes.new(type="NodeGroupOutput")
	group_output.location = (400, 0)
	node_group.outputs.new('NodeSocketGeometry', "Geometry")

	# Connect nodes
	links.new(group_input.outputs['Geometry'], point_instance.inputs['Geometry'])
	links.new(group_input.outputs['Geometry'], join_geometry.inputs[0])
	links.new(point_instance.outputs['Geometry'], transform.inputs[0])
	links.new(transform.outputs['Geometry'], join_geometry.inputs[1])
	links.new(join_geometry.outputs['Geometry'], group_output.inputs['Geometry'])

	return node_group
