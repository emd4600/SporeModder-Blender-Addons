from gettext import find
import bpy
import os

# Sporemodder paths

paths = {
	'GAME' : "Spore (Game & Graphics)",
	'Audio' : "Spore Audio",
	'BP1' : "BoosterPack_01",
	'BP2' : "BP2_Data",
	'EXO' : "Spore_Pack_03",
	#'MOD' : "",
}

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

# Set the folder name of the current mod.
# will not set if this matches an existing path in the dict
def set_mod_folder(foldername):
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

# Get the path of the current mod, or the path to a manually specified mod.
# If this does not exist, fallback to the spore data folder.
# TODO: read the mod dependency paths from the mod config file..?
def get_mod_path(foldername : str = ""):
	modspath = get_mod_projects_path()
	if modspath:
		if foldername:
			return modspath + foldername + "\\"
		elif 'MOD' in paths:
			return modspath + paths['MOD'] + "\\"
		else: return get_spore_data_path()
	return ""
