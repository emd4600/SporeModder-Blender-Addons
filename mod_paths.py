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

# Set the folder name of the current mod
def set_mod_folder(foldername):
	paths['MOD'] = foldername

def get_spore_data_path(package = 'GAME'):
	modspath = get_mod_projects_path()
	if modspath:
		if package.upper() in paths:
			return modspath + paths[package.upper()] + "\\"
		else:
			return modspath + package + "\\"
	return ""

def get_mod_path():
	modspath = get_mod_projects_path()
	if modspath:
		if 'MOD' in paths:
			return modspath + paths['MOD'] + "\\"
	return ""
