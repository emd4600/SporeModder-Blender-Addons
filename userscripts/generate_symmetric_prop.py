import os
import sys

# To be used by modders to quickly generate -symmetric or -center variants of part .prop files.

def generate_symmetric_prop(input_path):
	generate_altside_prop(input_path, side='SYMMETRIC')
	
def generate_center_prop(input_path):
	generate_altside_prop(input_path, side='CENTER')

# Creates a new file and edits the existing one to add lines
def generate_altside_prop(input_path, side = 'SYMMETRIC'):
	side = side.lower()
	# Folder and file name (without extensions)
	folder = os.path.basename(os.path.dirname(input_path))
	file_name = os.path.splitext(os.path.basename(input_path))[0].split('.')[0]

	# File output path
	base, ext = input_path.split('.',1)
	output_path = base + '-'+side + '.'+ext

	# Prepare lines_out to insert into the output file
	lines_out = []
	lines_out.append(f"key parent {folder}!{file_name}")

	with open(input_path, "r", encoding="utf-8") as f:
		lines = f.readlines()

	# Find model line and add it to the output
	model_line = -1
	has_left_file = False
	has_right_file = False
	has_center_file = False
	for i, line in enumerate(lines):
		line = line.strip()
		if line.lower().startswith("key modelMeshLOD0".lower()):
			model_line = i
			# Get the key's value
			value = line.lower().removeprefix("key modelMeshLOD0 ".lower()).strip()
			# value_base includes the groupID
			value_base, value_ext = os.path.splitext(value)
			value_base += '-'+side
			lines_out.append(f"key modelMeshLOD0 {value_base}{value_ext}")
		# Check for side variant entries
		elif line.lower().startswith("key modelLeftFile".lower()):
			has_left_file = True
		elif line.lower().startswith("key modelRightFile".lower()):
			has_right_file = True
		elif line.lower().startswith("key modelCenterFile".lower()):
			has_center_file = True
		elif model_line > -1 and has_right_file and has_left_file and has_center_file:
			break

	if model_line == -1:
		print(f"ERROR: No modelMeshLOD0 line found in {input_path}. Aborting.")
		return

	#---------------------------------------------------------------------------------
	# Prepare lines_out_input to insert into the input file
	lines_out_input = []
	if side == 'symmetric':
		if not has_left_file: lines_out_input.append(f"key modelLeftFile {folder}!{file_name}\n")
		if not has_right_file: lines_out_input.append(f"key modelRightFile {folder}!{file_name}-symmetric\n")
	elif side == 'center':
		if not has_center_file: lines_out_input.append(f"key modelCenterFile {folder}!{file_name}-center\n")

	# Insert new lines after the model line
	lines = lines[:model_line+1] + lines_out_input + lines[model_line+1:]

	with open(input_path, "w", encoding="utf-8") as f:
		f.writelines(lines)

	#---------------------------------------------------------------------------------
	# Write lines_out to the new file
	with open(output_path, "w", encoding="utf-8") as f:
		for line in lines_out:
			f.write(line + "\n")

	print(f"{side.capitalize()} prop file written to: {output_path}")



# Run if file is dropped on script
if __name__ == "__main__":
	if len(sys.argv) > 1:
		generate_symmetric_prop(sys.argv[1])