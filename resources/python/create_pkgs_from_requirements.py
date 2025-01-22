import os
import sys
import shutil
import subprocess
import glob
from zipfile import ZipFile

# ----------------------------------------------------
print("----------------------------------------------------")
print("Get python version")

python_major_version = sys.version_info.major
python_minor_version = sys.version_info.minor
python_version = f"{python_major_version}.{python_minor_version}"

print(f"Python version is {python_version}")

# ----------------------------------------------------
print("----------------------------------------------------")
print("Set base paths")

requirements_filename = "explicit_requirements.txt"
package_filename = "pkgs.zip"
source_dir = os.path.join("src", python_version)
source_requirements = os.path.join(source_dir, requirements_filename)

print(f"Source Dir: {source_dir}")
print(f"Source Requirements: {source_requirements}")

# ----------------------------------------------------
print("----------------------------------------------------")
print("Remove current packages")

for item in os.listdir(source_dir):
    item_path = os.path.join(source_dir, item)
    if item not in [package_filename, requirements_filename]:
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)
        else:
            os.remove(item_path)

# ----------------------------------------------------
print("----------------------------------------------------")
print("Install new packages")

subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=True)
subprocess.run([
    sys.executable, "-m", "pip", "install",
    "--target", source_dir,
    "--no-deps",
    "-r", source_requirements
], check=True)

# ----------------------------------------------------
print("----------------------------------------------------")
print("Remove unnecessary files")

paths_to_remove = [
    os.path.join(source_dir, "autobahn", "test"),
    os.path.join(source_dir, "autobahn", "*", "test"),
    os.path.join(source_dir, "twisted", "test"),
    os.path.join(source_dir, "twisted", "*", "test"),
    os.path.join(source_dir, "twisted", "*", "*", "test"),
    os.path.join(source_dir, "automat", "_test"),
    os.path.join(source_dir, "hyperlink", "test"),
    os.path.join(source_dir, "incremental", "tests"),
    os.path.join(source_dir, "twisted", "python", "_sendmsg.so"),
]

for path in paths_to_remove:
    if "*" in path:
        for matched_path in glob.glob(path, recursive=True):
            if os.path.isdir(matched_path):
                shutil.rmtree(matched_path)
            elif os.path.exists(matched_path):
                os.remove(matched_path)
    elif os.path.exists(path):
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

# Compress all files
print("----------------------------------------------------")
print("Compressing files")

with ZipFile(os.path.join(source_dir, package_filename), 'w') as zipf:
    for root, _, files in os.walk(source_dir):
        for file in files:
            if file != package_filename:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=source_dir)
                zipf.write(file_path, arcname)

# Remove files
print("----------------------------------------------------")
print("Cleaning up files")
for item in os.listdir(source_dir):
    item_path = os.path.join(source_dir, item)
    if item not in [package_filename, requirements_filename]:
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)
        else:
            os.remove(item_path)

# ----------------------------------------------------
print("----------------------------------------------------")
print("Adding new files to git")
subprocess.run(["git", "add", source_dir], check=True)
