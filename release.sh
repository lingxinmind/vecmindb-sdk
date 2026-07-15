#!/bin/bash
# Production-Grade Automated Release Script for VecminDB SDKs
# Ensures multi-language SDK versions align and clean builds are produced.
set -e

# Check version argument
if [ -z "$1" ]; then
    echo "❌ Error: Please specify the version to release."
    echo "Usage:   ./release.sh <version>"
    echo "Example: ./release.sh 1.0.0"
    exit 1
fi

VERSION=$1

echo "=========================================================="
echo "🚀 Starting automated release pipeline for version: $VERSION"
echo "=========================================================="

# --------------------------------------------------------
# 1. Update Version Strings
# --------------------------------------------------------
echo "📝 Step 1: Aligning version strings to $VERSION..."

# Python Version Bump
if [ -d "python" ]; then
    echo "  - Updating Python configuration..."
    if [ -f "python/pyproject.toml" ]; then
        # Handle setuptools pyproject version field
        sed -i "s/^version\s*=\s*\".*\"/version = \"$VERSION\"/" python/pyproject.toml
    fi
    if [ -f "python/vecmindb/__init__.py" ]; then
        # Handle Python internal module version
        sed -i "s/^__version__\s*=\s*\".*\"/__version__ = \"$VERSION\"/" python/vecmindb/__init__.py
    fi
fi

# TypeScript Version Bump
if [ -d "typescript" ]; then
    echo "  - Updating TypeScript package configuration..."
    if [ -f "typescript/package.json" ]; then
        # Handle Node.js package.json version field
        sed -i "s/\"version\":\s*\".*\"/\"version\": \"$VERSION\"/" typescript/package.json
    fi
fi

# --------------------------------------------------------
# 2. Purge Build Caches
# --------------------------------------------------------
echo "🧹 Step 2: Purging historical build caches..."

if [ -d "python" ]; then
    rm -rf python/build/ python/dist/* python/*.egg-info/ python/vecmindb_sdk.egg-info/
fi

if [ -d "typescript" ]; then
    rm -rf typescript/dist/
fi

# --------------------------------------------------------
# 3. Compile Python SDK (Wheel & Tarball)
# --------------------------------------------------------
if [ -d "python" ]; then
    echo "🏗️ Step 3: Compiling Python SDK..."
    cd python
    python3 -m build
    cd ..
fi

# --------------------------------------------------------
# 4. Compile TypeScript SDK (NPM Distribution)
# --------------------------------------------------------
if [ -d "typescript" ]; then
    echo "🏗️ Step 4: Compiling TypeScript SDK..."
    cd typescript
    if [ -f "package.json" ]; then
        # Ensure dependencies are installed and trigger the compiler
        npm install
        npm run build
    fi
    cd ..
fi

echo "=========================================================="
echo "✨ Release compilation completed successfully for version: $VERSION"
echo "=========================================================="
echo "📦 Final steps to publish your packages:"
echo ""
echo "  1. Publish Python SDK to PyPI:"
echo "     cd python && python3 -m twine upload dist/*"
echo ""
echo "  2. Publish TypeScript SDK to NPM:"
echo "     cd typescript && npm publish"
echo "=========================================================="
