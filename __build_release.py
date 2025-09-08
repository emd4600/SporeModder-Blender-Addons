import os
import zipfile

def create_zip():
	blender_version = 4
	blacklist = {".git", ".vscode", "__pycache__", "userscripts", "sporemodder-blender-addons_updater"}

	script_path = os.path.abspath(__file__)
	script_dir = os.path.dirname(script_path)
	script_name = os.path.basename(script_path)
	folder_name = os.path.basename(script_dir)

	# build name string
	zip_base = folder_name.replace("-", ".")
	if "Blender" in zip_base:
		parts = zip_base.split("Blender", 1)
		zip_base = f"{parts[0]}Blender.{blender_version}{parts[1]}"

	zip_filename = f"{zip_base}.zip"
	zip_path = os.path.join(script_dir, zip_filename)

	# delete old zip if it exists
	if os.path.exists(zip_path):
		os.remove(zip_path)

	with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
		for root, dirs, files in os.walk(script_dir, topdown=True, followlinks=False):
			dirs[:] = [d for d in dirs if d not in blacklist]

			for file in files:
				if file in {script_name, zip_filename}:
					continue  # skip this script and the zip being written

				file_path = os.path.join(root, file)
				rel_path = os.path.relpath(file_path, script_dir)
				arcname = os.path.join("sporemodder", rel_path)
				zipf.write(file_path, arcname)

	print(f"Created zip: {zip_path}")

if __name__ == "__main__":
	create_zip()