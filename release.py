#!/usr/bin/env python3
"""
VecminDB SDK Release Manager (Source of Truth Version)
Aligns all SDK configurations (Python, TypeScript) to a unified version.
"""

import os
import re
import sys
import shutil
import argparse
import subprocess

# Paths relative to the sdk/ directory (Source of Truth)
FILES_TO_BUMP = {
    "python/pyproject.toml": [
        (r'(^version\s*=\s*")(\d+\.\d+\.\d+)(")', r'\g<1>{}\g<3>')
    ],
    "python/vecmindb/__init__.py": [
        (r'(^__version__\s*=\s*")(\d+\.\d+\.\d+)(")', r'\g<1>{}\g<3>')
    ],
    "typescript/package.json": [
        (r'("version"\s*:\s*")(\d+\.\d+\.\d+)(")', r'\g<1>{}\g<3>')
    ],
    "../Cargo.toml": [
        (r'(^name\s*=\s*"vecmindb"\s*\nversion\s*=\s*")(\d+\.\d+\.\d+)(")', r'\g<1>{}\g<3>')
    ],
    "../docker-compose.yml": [
        (r'(APP_VERSION:\s*")(\d+\.\d+\.\d+)(")', r'\g<1>{}\g<3>')
    ],
    "../docker-compose.production.yml": [
        (r'(vecmindb:)(\d+\.\d+\.\d+)', r'\g<1>{}')
    ]
}

def update_version(filename, version):
    if not os.path.exists(filename):
        print(f"  ⚠️ File not found: {filename}")
        return False
    
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = content
    for pattern, replacement in FILES_TO_BUMP[filename]:
        new_content = re.sub(pattern, replacement.format(version), new_content, flags=re.MULTILINE)

    with open(filename, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)
    print(f"  Updated: {filename}")
    return True

def purge_caches():
    print("\nPurging build and package caches...")
    # Python Caches
    if os.path.exists("python"):
        for path in ["python/build", "python/dist"]:
            if os.path.exists(path):
                shutil.rmtree(path)
        for d in os.listdir("python"):
            if d.endswith(".egg-info") or d == "vecmindb_sdk.egg-info":
                shutil.rmtree(os.path.join("python", d))
                
    # TypeScript Caches
    if os.path.exists("typescript/dist"):
        shutil.rmtree("typescript/dist")
    print("  Completed: Caches cleared.")

def main():
    parser = argparse.ArgumentParser(description="VecminDB SDK Release Manager")
    parser.add_argument("version", help="Version to release (e.g. 1.0.1)")
    parser.add_argument("--dry-run", action="store_true", help="Preview version changes without writing")
    args = parser.parse_args()

    version = args.version
    if not re.match(r'^\d+\.\d+\.\d+$', version):
        print(f"Error: Invalid version format '{version}'. Must be x.y.z")
        sys.exit(1)

    print("==========================================================")
    print(f"Aligning VecminDB SDKs to version: {version}")
    print("==========================================================")

    if args.dry_run:
        print("Dry run completed. No files modified.")
        return

    # Update Version configs
    for filename in FILES_TO_BUMP.keys():
        update_version(filename, version)

    # Purge caches
    purge_caches()

    # Compiling builds where possible
    print("\nCompiling packages...")
    if os.path.exists("python/pyproject.toml"):
        print("  Compiling Python SDK...")
        try:
            subprocess.run([sys.executable, "-m", "build"], cwd="python", shell=True, check=True)
        except Exception as e:
            print(f"  Warning: Python compilation skipped/failed: {e}")

    print("\n==========================================================")
    print(f"Release alignment completed successfully for version: {version}")
    print("==========================================================")
    print("Git Hook will automatically propagate these changes to vecmindb-sdk upon commit.")
    print("==========================================================")

if __name__ == "__main__":
    main()
