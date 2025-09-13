__author__ = 'Allison'

from operator import ne
import os, re
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
# But right now its not a big deal

#------------------------------------------
# Classes

class ResourceKey():
	def __init__(self, instance, group = "", type = ""):
		self.instance = instance
		self.group = group
		self.type = type
	
	def __str__(self):
		if self.group != "":
			if self.type != "":
				return f"{self.group}!{self.instance}.{self.type}"
			return f"{self.group}!{self.instance}"
		else:
			if self.type != "":
				return f"{self.instance}.{self.type}"
			return f"{self.instance}"

	# Returns the file path for this resource key, given a project name in the SMFX projects folder.
	# If no project is specified, the default mod project path will be used.
	def get_file_path(self, project : str = ""):
		type = self.type
		folder = self.group
		if folder == "": folder = "animations~"
		if type == "prop": type += ".prop_t"
		if type == "cnv": type += ".cnv_t"
		return os.path.join(project, f"{self.instance}.{self.type}")


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
				self.value = get_hash(value)
				#raise ValueError("Unsupported type for Hash value")
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
		self.key : str = key # property name
		self.value = value # property value
		self.type : str = type # value type
		# Set marked to true when used, so unmarked properties can be filtered.
		# Also set any properties from the Parent files as marked.
		self.marked = False
		# Parent will be true if the property was taken from a parent file.
		self.parent = False


	def kv(self):
		return [self.key, self.value]
	
	def is_key(self, keyname):
		return self.key.lower() == keyname.lower()

	def is_type(self, type):
		return self.type.lower() == type.lower()

	def is_list_value(self):
		return isinstance(self.value, (list))

	def mark(self):
		self.marked = True
	
	def unmark(self):
		self.marked = False

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
	def __init__(self, filepath, write = False):
		self.filepath = filepath
		self.key = os.path.basename(filepath).split('.')[0] # Filename sans extension
		self.directory = os.path.dirname(filepath) # Directory path

		self.properties = {}
		if (not write and filepath and os.path.isfile(filepath)):
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

	def mark_all(self):
		for prop in self.properties.values():
			prop.mark()
	
	def unmark_all(self):
		for prop in self.properties.values():
			prop.unmark()

	# Write the properties to a file
	def write(self, filepath):
		with open(filepath, "w", encoding="utf-8") as f:
			self.unmark_all()
			self.sort()
			for prop in self.properties.values():
				self._write_prop_line(f, prop)

	def _write_prop_line(self, f, prop, only_unmarked=True):
		# Always write, don't skip based on marked
		if (only_unmarked and prop.marked):
			return

		def round_value(value):
			if isinstance(value, float):
				value = round(value, 6)
			elif isinstance(value, (list, tuple)):
				value = [round(v, 6) for v in value if isinstance(v, float)]
				return f"({', '.join(str(v) for v in value)})"
			return value

		# list value
		if isinstance(prop.value, list):
			f.write(f"{prop.type} {prop.key}\n")
			for item in prop.value:
				f.write(f"\t{round_value(item)}\n")
			f.write("end\n")
		else:
			f.write(f"{prop.type} {prop.key} {round_value(prop.value)}\n")
		prop.mark()


	# Parse and return [Property(key, value, type), nextline] from a file's lines
	# 'line' is the line to begin reading from. nextline will be the line to read next.
	def parse_property(self, lines : list, line : int):
		nextline : int = line + 1 # what line to read for the next call of this func.
		propdata : list[str] = lines[line].split('#')[0].strip().split() # Line used to define the property, as an array

		if not propdata or len(propdata) < 2:
			return [None, nextline] # No property data found
		
		type = propdata[0].lower() # Property type
		key = propdata[1] # Property name
		data_array = [] # Array of the property values

		# If the propline contains a value after the prop key, use that. Otherwise, look on the next lines.
		if len(propdata) > 2:
			value = lines[line].strip()
			value = re.sub(f"{type}|{key}", '', value).strip()
			data_array.append(value)
		else:
			# Gather the list data until we hit 'end'
			while nextline < len(lines):
				line = lines[nextline].split('#')[0].strip()
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
				if str(item).startswith("hash("):
					values.append(Hash(value))
				else:
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
				chunk_group = item.split(".")[0].split("!")
				chunks_inst_type = item.split("!")[-1].split(".")
				reskey = ResourceKey(chunks_inst_type[0])

				if (len(chunk_group) == 2):
					reskey.group = chunk_group[0]
				if (len(chunks_inst_type) == 2):
					reskey.type = chunks_inst_type[1]

				values.append(reskey)
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

	def sort(self):
		# Custom sort order: parent, description, blockName, then natural sort for the rest
		def sort_key(prop: Property):
			if prop.is_key("parent"):
				return (0, "")
			elif prop.is_key("description"):
				return (1, "")
			elif prop.is_key("blockname"):
				return (2, "")
			else:
				return (3, prop._natural_sort_key())
		sorted_props = sorted(self.properties.values(), key=sort_key)
		self.properties = {prop.key.lower(): prop for prop in sorted_props}


	#--------------------------
	# Properties

	def add_property(self, property: Property):
		self.properties[property.key.lower()] = property

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
	
	def get_properties_containing(self, substr):
		array = [self.properties.get(key.lower()) for key in self.keys() if substr.lower() in key.lower()]
		array.sort()
		return array
	
	def get_properties_by_type(self, type):
		array = [prop for prop in self.properties.values() if prop.type == type]
		array.sort()
		return array

	#----------------------------
	# Parent / marked properties

	def get_marked_properties(self):
		return [prop for prop in self.properties.values() if prop.marked]

	def get_unmarked_properties(self):
		return [prop for prop in self.properties.values() if not prop.marked]
	
	def get_parent_properties(self):
		return [prop for prop in self.properties.values() if prop.parent]

	def get_nonparent_properties(self):
		return [prop for prop in self.properties.values() if not prop.parent]

	#--------------------------
	# Values

	# Get value from key
	def get_value(self, key, default=None):
		if key.lower() not in self.properties:
			return default
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
		return [[key, self.properties.get(key.lower()).value] for key in keys]
