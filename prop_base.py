__author__ = 'Allison'

from operator import ne
import re, os
import string
from .file_io import get_hash

prop_bool = ["bool"]
prop_numbers = ["int", "int32", "float"]
prop_hash = ["uint32"]
prop_vector = ["vector", "vector2", "vector3", "vector4", "colorRGB"]
prop_text = ["string", "string16", "string8", "text"]
prop_key = ["key"]
prop_transform = ["transform"]
prop_bbox = ["bbox"]

types = [
	prop_bool,
	prop_numbers,
	prop_hash,
	prop_vector,
	prop_text,
	prop_key,
	prop_transform,
	prop_bbox
]

# TODO: we need to eventually try to pull in the "parent" key before loading in the file itself (recursively)
# But right now is not a big deal

#------------------------------------------
# Classes

class ResourceKey():
	def __init__(self, instance, group = 0x0, type = 0x0):
		self.instance = instance
		self.group = group
		self.type = type
	
	def __str__(self):
		if self.group != 0x0:
			if self.type != 0x0:
				return f"{self.group}!{self.instance}.{self.type}"
			return f"{self.group}!{self.instance}"
		else:
			if self.type != 0x0:
				return f"{self.instance}.{self.type}"
			return f"{self.instance}"

class Hash():
	def __init__(self, value):
		self.value = 0x0

		if isinstance(value, str):
			if value.startswith("0x"):
				self.value = int(value, 16)
			elif value.startswith("hash("):
				# Remove 'hash(' and ')'
				self.value = get_hash(value[5:-1]) 
			else:
				raise ValueError("Unsupported type for Hash value")
		elif isinstance(value, int):
			self.value = value
		else:
			self.value = int(value)

	def __str__(self):
		# Returns value as 0x00000000 format (8 digits, lowercase)
		return f"0x{self.value:08x}"

	def get(self):
		return self.value


#-----------------------------------------------------------------------------------------

class Property():
	def __init__(self, key, value, type):
		self.key : str = key
		self.value = value
		self.type : str = type
		# Set marked to true when used, so unmarked properties can be filtered.
		# Also set any properties from the Parent files as marked.
		self.marked = False

	def kv(self):
		return [self.key, self.value]
		
	def is_key(self, keyname):
		return self.key.lower() == keyname.lower()
	
	def mark(self):
		self.marked = True
	
	def unmark(self):
		self.marked = True

	def set_marked(self, marked):
		self.marked = marked

	def __len__(self):
		return len(self.value) if isinstance(self.value, list) else 1
	
	def __str__(self):
		return f"Property(key={self.key}, value={self.value}, type={self.type})"

	def _natural_sort_key(self):
		# Split key into text and number chunks for natural sorting
		return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', self.key.lower())]

	def __lt__(self, other):
		return self._natural_sort_key() < other._natural_sort_key()

	def __gt__(self, other):
		return self._natural_sort_key() > other._natural_sort_key()

	def __eq__(self, other):
		return self._natural_sort_key() == other._natural_sort_key()


class PropFile():
	def __init__(self, filepath):
		self.filepath = filepath
		self.key = os.path.basename(filepath).split('.')[0] # Filename sans extension
		self.directory = os.path.dirname(filepath) # Directory path

		self.properties = {} # name : Property
		self.read(filepath)

	# Parse file and load and properties into self.properties
	def read(self, filepath):
		with open(filepath, 'r') as file:
			lines = file.readlines()
			# Read lines into properties until we hit the end
			nextline = 0
			while nextline > -1 and nextline < len(lines):
				prop = self.parse_property(lines, nextline)
				if prop:
					if prop[0] is not None:
						self.properties[prop[0].key.lower()] = prop[0]
					nextline = prop[1]
				else:
					nextline = -1

	# Append any unique properties from another PropFile
	# if replace = true, append all properties (overwrite existing)
	def append_prop_file(self, propfile, mode = 'APPEND'):
		mode = mode.upper()
		# Append properties from another PropFile
		for key, property in propfile.properties.items():
			if mode == 'APPEND':
				if key not in self.properties:
					self.properties[key] = property
				continue
			elif mode == 'MERGE':
				# If the property already exists, append values to the existing property, as lists
				existing_prop = self.properties[key]
				if isinstance(existing_prop.value, list):
					existing_prop.value.append(property.value)
				else:
					existing_prop.value = [existing_prop.value, property.value]
			# Replace all existing properties with the new ones
			elif mode == 'REPLACE':
				self.properties[key] = property

	# Parse and return [Property(key, value, type), nextline] from a file's lines
	# start_line is the line to begin reading from. nextline will be the line to read next.
	def parse_property(self, lines : list, start_line : int):
		nextline : int = start_line + 1 # what line to read next.
		propdata : list[str] = lines[start_line].strip().split() # Line used to define the property, as lowercase array

		if not propdata or len(propdata) < 2:
			return [None, nextline] # No property data found
		
		type = propdata[0].lower() # Property type
		key = propdata[1] # Property name
		data_array = [] # Array of the property values

		# If the propline contains a value after the prop key, use that. Otherwise, look on the next lines.
		if len(propdata) > 2:
			value = lines[start_line].strip().lower()
			value = re.sub(f"{type}|{key.lower()}", '', value).strip()
			data_array.append(value)
		else:
			# Gather the list data until we hit 'end'
			while nextline < len(lines):
				line = lines[nextline].strip().lower()
				# remove any trailing comments
				line = re.sub(r'\s*#.*$', '', line)

				if line == 'end':
					break
				elif line:
					data_array.append(line)
				else:
					break
				nextline += 1
		
		# Helper func
		def is_type(type : str, typelist: list):
			if type in typelist:
				return True
			else:
				typesingular = type[:-2] if type.endswith("es") else type[:-1]
				if typesingular in typelist:
					return True
			return False

		values = []
		for item in data_array:
			# bool
			if is_type(type, prop_bool):
				values.append(item.lower() == 'true' or item.lower() == '1')
			# int or float
			elif is_type(type, prop_numbers): 
				values.append(float(item))
			# uint32 hex
			elif is_type(type, prop_hash): 
				values.append(Hash(int(item, 16)))
			# vector2, 3, or 4
			elif is_type(type, prop_vector): 
				item = item.replace("(", "").replace(")", "").replace(" ", "")
				values.append([float(x) for x in item.split(",")])
			# text or string
			elif is_type(type, prop_text): 
				# if item contains quotes, only use the part inside quotes.
				if '"' in item:
					text = re.search(r'"([^"]*)"', item)
					if text:
						item = text.group(1)
				values.append(item)
			# Resource Key
			elif is_type(type, prop_key):
				chunks = re.split(r'[!.]', item)
				if len(chunks) == 3:
					values.append(ResourceKey(chunks[1], chunks[0], chunks[2]))
				elif len(chunks) == 2:
					values.append(ResourceKey(chunks[1], chunks[0], 0x0))
				elif len(chunks) == 1:
					values.append(ResourceKey(chunks[0], 0x0, 0x0))
				else:
					values.append(item)
			# Transform
			elif is_type(type, prop_transform): # format -offset (0, 0, 0) -scale 1 -rotateXYZ 0 -0 0
				values.append(item)
			# BBox
			elif is_type(type, prop_bbox):
				minmax = item.split(")")
				min = minmax[0].replace("(", "").replace(")", "")
				max = minmax[1].replace("(", "").replace(")", "")
				values.append(
						(float, min.split(",")),
						(float, max.split(","))
						)

		if len(values) == 1 and not type.endswith('s'):
			values = values[0]  # If there's only one value, use that.
		return [Property(key, values, type), nextline]

	def write(self, filepath):
		with open(filepath, "w", encoding="utf-8") as f:
			for prop in self.properties.items():
				# list value
				if isinstance(prop.value, list) and prop.key:
					f.write(f"{prop.type} {prop.key}")
					for item in prop.value:
						f.write(f"\t{item}")
					f.write("end")
				# single value
				else:
					f.write(f"{prop.type} {prop.key} {prop.value}\n")

	# Returns array of keys
	def keys(self):
		return self.properties.keys()
	
	# Returns array of values
	def values(self):
		return [prop.value for prop in self.properties.values()]
	
	# Returns array of types
	def types(self):
		return [prop.type for prop in self.properties.values()]

	def size(self):
		return len(self.properties)

	#--------------------------
	# Properties

	def get_all_properties(self):
		return [self.properties.get(key.lower()) for key in self.keys()]

	# By Key
	def get_property(self, key : str):
		return self.properties.get(key.lower())

	# By Key Array
	def get_properties(self, keys : list):
		array = [self.properties.get(key.lower()) for key in keys if key.lower() in self.properties.keys()]
		array.sort()
		return array
	
	def get_properties_by_prefix(self, prefix):
		array = [self.properties.get(key.lower()) for key in self.keys() if key.lower().startswith(prefix.lower())]
		array.sort()
		return array
	
	def get_properties_by_type(self, type):
		array = [prop for prop in self.properties.values() if prop.type == type]
		array.sort()
		return array

	def get_marked_properties(self):
		return [prop for prop in self.properties.values() if prop.marked]

	def get_unmarked_properties(self):
		return [prop for prop in self.properties.values() if not prop.marked]

	#--------------------------
	# Values

	# Get value from key
	def get_value(self, key):
		return self.properties.get(key.lower()).value

	# Get values for multiple keys
	def get_values(self, keys):
		return [self.properties.get(key.lower()).value for key in keys]

	#--------------------------
	# KVs [key: value]

	# Get [key, value] for a key
	def get_keyvalue(self, key):
		return [key, self.properties.get(key.lower()).value]

	# Get [key, value]s for multiple keys
	def get_keyvalues(self, keys):
		return [[key, self.properties.get(key.lower()).value] for key in keys]

