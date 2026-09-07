import glob
import toml
import os
import subprocess
import sys
import platform

def run_command(cmd, shell=False):
    """Run command with proper shell settings for Windows/Unix"""
    is_windows = platform.system() == "Windows"
    try:
        # On Windows, we need shell=True for poetry/pip commands
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=is_windows if not shell else True,
            # Prevent console window on Windows
            creationflags=subprocess.CREATE_NO_WINDOW if is_windows else 0
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Command not found: {cmd[0]}")
        sys.exit(1)

def setup_wheels():
    print("Exporting requirements from poetry...")
    result = run_command(['poetry', 'export', '-f', 'requirements.txt', '--output', 'requirements.txt'])
    if result.returncode != 0:
        print(f"Error exporting requirements: {result.stderr}")
        sys.exit(1)

    # Create wheels directory if it doesn't exist
    os.makedirs('./wheels', exist_ok=True)

    print("Downloading wheels...")
    # Use python -m pip to ensure we use the right Python environment
    pip_cmd = [sys.executable, '-m', 'pip', 'download', '-r', 'requirements.txt', '-d', './wheels']
    result = run_command(pip_cmd)
    if result.returncode != 0:
        print(f"Error downloading wheels: {result.stderr}")
        sys.exit(1)

def update_manifest_wheels():
    manifest_file = 'blender_manifest.toml'
    
    if not os.path.exists(manifest_file):
        print(f"{manifest_file} not found, setting up wheels first...")
        setup_wheels()
        if not os.path.exists(manifest_file):
            print(f"Error: {manifest_file} still not found after wheel setup")
            sys.exit(1)
    
    # Read current manifest
    with open(manifest_file, 'r', encoding='utf-8') as f:
        manifest = toml.load(f)
    
    # Find all wheel files and normalize paths
    wheel_files = glob.glob(os.path.join('wheels', '*.whl'))
    # Convert paths to use forward slashes even on Windows
    wheel_paths = [f'./{os.path.normpath(file).replace(os.sep, "/")}' for file in wheel_files]
    
    # Update wheels section
    manifest['wheels'] = wheel_paths
    
    # Write updated manifest with proper line endings
    with open(manifest_file, 'w', encoding='utf-8', newline='\n') as f:
        toml.dump(manifest, f)
    
    print(f"Updated {manifest_file} with wheels: {wheel_paths}")

if __name__ == "__main__":
    update_manifest_wheels()