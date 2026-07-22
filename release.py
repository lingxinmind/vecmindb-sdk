#!/usr/bin/env python3
"""
VecminDB SDK Release Manager (Cross-platform Python version)
Aligns all SDK configurations (Python, TypeScript, Rust) to a unified version.
"""

import os
import re
import sys
import shutil
import argparse
import subprocess

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
    "rust/Cargo.toml": [
        (r'(^version\s*=\s*")(\d+\.\d+\.\d+)(")', r'\g<1>{}\g<3>')
    ]
}

def update_version(filename, version):
    if not os.path.exists(filename):
        return False
    
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = content
    for pattern, replacement in FILES_TO_BUMP[filename]:
        new_content = re.sub(pattern, replacement.format(version), new_content, flags=re.MULTILINE)

    with open(filename, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)
    print(f"  ✓ Updated {filename}")
    return True

def purge_caches():
    print("\n🧹 Purging build and package caches...")
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
        
    # Rust Caches
    if os.path.exists("rust/target"):
        shutil.rmtree("rust/target")
    print("  ✓ Caches cleared.")

def main():
    parser = argparse.ArgumentParser(description="VecminDB SDK Release Manager")
    parser.add_argument("version", help="Version to release (e.g. 1.0.1)")
    parser.add_argument("--dry-run", action="store_true", help="Preview version changes without writing")
    args = parser.parse_args()

    version = args.version
    if not re.match(r'^\d+\.\d+\.\d+$', version):
        print(f"❌ Error: Invalid version format '{version}'. Must be x.y.z")
        sys.exit(1)

    print("==========================================================")
    print(f"🚀 Aligning VecminDB SDKs to version: {version}")
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
    print("\n🏗️ Compiling packages...")
    if os.path.exists("python/pyproject.toml"):
        print("  Compiling Python SDK...")
        subprocess.run([sys.executable, "-m", "build"], cwd="python", shell=True)

    print("\n==========================================================")
    print(f"✨ Release alignment completed successfully for version: {version}")
    print("==========================================================")
    print("📦 Instructions to publish:")
    print("\n  1. Publish Python SDK to PyPI:")
    print("     cd python && python -m twine upload dist/*")
    print("\n  2. Publish TypeScript SDK to NPM:")
    print("     cd typescript && npm publish")
    print("\n  3. Publish Rust SDK to crates.io:")
    print("     cd rust && cargo publish")
    print("==========================================================")

if __name__ == "__main__":
    main()
