import os
import sys
import subprocess
import shutil
import stat
import time

# -------------------------------
# CLI arguments: Provider Name and Version
# -------------------------------
if len(sys.argv) != 4:
    print("Usage: python 1_generate_schema.py <Provider Supplier> <Provider Name> <Provider Version>")
    sys.exit(1)

# Vars
provider_suplier = sys.argv[1]
provider_name = sys.argv[2]
provider_version = sys.argv[3]

# Constants
TEMP_FOLDER = "./terraform_schema_temp"
SCHEMA_OUTPUT = f"./{provider_name}_{provider_version}_schema.json"

def _on_rm_error(func, path, exc_info):
  # Attempt to clear read-only attribute and retry the operation
  try:
    os.chmod(path, stat.S_IWRITE)
  except Exception:
    pass
  try:
    func(path)
  except Exception:
    # Swallow to allow retry at higher level
    pass

def _rmtree_force(path: str, retries: int = 10, delay: float = 0.5):
  last_err = None
  for _ in range(retries):
    try:
      if not os.path.exists(path):
        return
      shutil.rmtree(path, onerror=_on_rm_error)
      if not os.path.exists(path):
        return
    except Exception as e:
      last_err = e
    time.sleep(delay)
  if os.path.exists(path):
    # Prefer raising the last encountered error if available
    if last_err:
      raise last_err
    raise OSError(f"Failed to remove '{path}' after {retries} retries")

# Clean temp dir (robust on Windows)
if os.path.exists(TEMP_FOLDER):
  _rmtree_force(TEMP_FOLDER)
os.makedirs(TEMP_FOLDER, exist_ok=True)

# Write minimal main.tf
main_tf = f"""
terraform {{
  required_providers {{
    {provider_name} = {{
      source  = "{provider_suplier}/{provider_name}"
      version = "{provider_version}"
    }}
  }}
}}

provider "{provider_name}" {{
  features {{}}
}}
"""

with open(os.path.join(TEMP_FOLDER, "main.tf"), "w") as f:
    f.write(main_tf)

# Run terraform init
print("👉 Running 'terraform init'...")
subprocess.run(["terraform", "init"], cwd=TEMP_FOLDER, check=True)

# Run terraform providers schema -json
print("👉 Exporting provider schema...")
try:
  with open(SCHEMA_OUTPUT, "w") as outfile:
    subprocess.run(
      ["terraform", "providers", "schema", "-json"],
      cwd=TEMP_FOLDER,
      check=True,
      stdout=outfile
    )
finally:
  # Clean up temp folder (robust, don't fail the whole script if cleanup fails)
  try:
    _rmtree_force(TEMP_FOLDER)
  except Exception as e:
    print(f"⚠️  Warning: could not remove temp folder '{TEMP_FOLDER}': {e}")

print(f"✅ Schema export completed: {SCHEMA_OUTPUT}")
