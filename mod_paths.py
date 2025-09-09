from gettext import find
import bpy
import os
from bpy.app.handlers import persistent

# Sporemodder paths

paths = {
	'GAME' : "Spore (Game & Graphics)",
	'AUDIO' : "Spore Audio",
	'BP1' : "BoosterPack_01",
	'BP2' : "BP2_Data",
	'EXO' : "Spore_Pack_03",
	#'MOD' : "Mod",
	#'IMPORT' : "File/Path/",
	#'EXPORT' : "File/Path/Name.ext",
}

def clear_import_export_paths():
	paths.pop('IMPORT', None)
	paths.pop('EXPORT', None)
	paths.pop('MOD', None)

@persistent
def on_blendfile_load(scene):
	clear_import_export_paths()

# Register the handler when the addon is enabled
def register():
	bpy.app.handlers.load_post.append(on_blendfile_load)

def unregister():
	if on_blendfile_load in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.remove(on_blendfile_load)


def using_import_folder():
	prefs = bpy.context.preferences.addons.get(__package__)
	if prefs and hasattr(prefs, "preferences"):
		if prefs.preferences.use_import_folder and prefs.preferences.mod_projects_path:
			return True
	return False

def get_mod_projects_path():
	addon_name = __package__ if __package__ else "SporeModder-Blender-Addons"
	prefs = bpy.context.preferences.addons.get(addon_name)
	if prefs and hasattr(prefs, "preferences"):
		path : str = prefs.preferences.mod_projects_path
		if path:
			if os.path.isdir(path):
				return path
			else:
				# Sanitize: convert slashes to backslashes, ensure trailing slash
				safe_path = path.replace("/", "\\")
				if not safe_path.endswith("\\"):
					safe_path += "\\"
				if os.path.isdir(safe_path):
					return safe_path
	return ""

# Set the folder name of the desired import directory
def set_import_path(path):
	paths['IMPORT'] = path.split('.')[0]

# Set the folder name of the desired export directory
def set_export_path(path):
	set_mod_folder(os.path.dirname(path))
	paths['EXPORT'] = path.split('.')[0]

# Set the folder name of the current mod.
# will not set if this matches an existing path in the dict
def set_mod_folder(foldername):
	foldername = foldername.split('.')[0]
	# foldername is a full path, find just the part after the projects directory
	if "\\" in foldername:
		patharray_folder = foldername.split("\\")
		projects_base_folder = get_mod_projects_path().split("\\")[:-1][-1]
		if projects_base_folder in patharray_folder:
			foldername = patharray_folder[patharray_folder.index(projects_base_folder) + 1]

	for item in paths.values():
		if item.lower() == foldername.lower():
			return
	paths['MOD'] = foldername

def get_spore_data_path(package = 'GAME'):
	modspath = get_mod_projects_path()
	if modspath:
		if package.upper() in paths:
			return modspath + paths[package.upper()] + "\\"
		else:
			return modspath + package + "\\"
	return ""

# Get the last import path of the current mod, or the path to a manually specified mod.
# If this does not exist, fallback to the spore data folder.
def get_import_path(foldername : str = ""):
	if 'IMPORT' in paths:
		return paths['IMPORT'].split('.')[0]
	else: return get_spore_data_path().split('.')[0]

# Get the last export path of the current mod, or the path to a manually specified mod.
# If this does not exist, fallback to the mod path.
def get_export_path(foldername : str = "", file : str = "", ext : str = ""):
	if 'EXPORT' in paths:
		return paths['EXPORT'].split('.')[0]
	elif using_import_folder():
		return get_mod_path(foldername, file, ext)
	else: return file.split('.')[0] + ext

# Get the path of the current mod, or the path to a manually specified mod.
# If this does not exist, fallback to the spore data folder.
# TODO: read the mod dependency paths from the mod config file..?
def get_mod_path(foldername : str = "", file : str = "", ext : str = ""):
	modspath = get_mod_projects_path()
	path = ""
	if modspath:
		if foldername:
			path = modspath + foldername + "\\"
		elif 'MOD' in paths:
			path = modspath + paths['MOD'] + "\\"
		else: path = get_spore_data_path()
	return path + os.path.basename(file).split('.')[0] + ext