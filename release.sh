#!/bin/bash
# Production-Grade Automated Release Script for VecminDB SDKs (Source of Truth)
# Ensures multi-language SDK versions align and clean builds are produced.
set -e

# Check version argument
if [ -z "$1" ]; then
    echo "❌ Error: Please specify the version to release."
    echo "Usage:   ./release.sh <version>"
    echo "Example: ./release.sh 1.0.1"
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
        sed -i "s/^version\s*=\s*\".*\"/version = \"$VERSION\"/" python/pyproject.toml
    fi
    if [ -f "python/vecmindb/__init__.py" ]; then
        sed -i "s/^__version__\s*=\s*\".*\"/__version__ = \"$VERSION\"/" python/vecmindb/__init__.py
    fi
fi

# TypeScript Version Bump
if [ -d "typescript" ]; then
    echo "  - Updating TypeScript package configuration..."
    if [ -f "typescript/package.json" ]; then
        sed -i "s/\"version\":\s*\".*\"/\"version\": \"$VERSION\"/" typescript/package.json
    fi
fi

# Server Configurations Version Bump
echo "  - Updating Server configurations..."
if [ -f "../Cargo.toml" ]; then
    sed -i '/name = "vecmindb"/{n;s/version = ".*"/version = "'"$VERSION"'"/}' ../Cargo.toml
fi
if [ -f "../docker-compose.yml" ]; then
    sed -i "s/APP_VERSION:\s*\".*\"/APP_VERSION: \"$VERSION\"/" ../docker-compose.yml
fi
if [ -f "../docker-compose.production.yml" ]; then
    sed -i "s/vecmindb:[0-9.]*/vecmindb:$VERSION/g" ../docker-compose.production.yml
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

echo "=========================================================="
echo "✨ Release alignment completed successfully for version: $VERSION"
echo "=========================================================="
echo "📦 Git Hook will automatically propagate these changes to vecmindb-sdk upon commit."
echo "=========================================================="
