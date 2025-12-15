#!/bin/bash

# Get the directory where this script is located
if [ -n "$BASH_SOURCE" ]; then
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
elif [ -n "$ZSH_VERSION" ]; then
    SCRIPT_DIR="$( cd "$( dirname "${(%):-%x}" )" && pwd )"
else
    SCRIPT_DIR="$(pwd)"
fi

# Default build directory
BUILD_DIR="$SCRIPT_DIR/build"

# Check if the plugin exists in build dir, otherwise assume current dir or check standard install paths
if [ -f "$BUILD_DIR/libH5Zturbopfor.so" ] || [ -f "$BUILD_DIR/libH5Zturbopfor.dylib" ]; then
    PLUGIN_PATH="$BUILD_DIR"
elif [ -f "$SCRIPT_DIR/libH5Zturbopfor.so" ] || [ -f "$SCRIPT_DIR/libH5Zturbopfor.dylib" ]; then
    PLUGIN_PATH="$SCRIPT_DIR"
else
    # Fallback to build dir even if not found, so it's ready for when it is built
    PLUGIN_PATH="$BUILD_DIR"
fi

# Append to HDF5_PLUGIN_PATH
if [[ ":$HDF5_PLUGIN_PATH:" != *":$PLUGIN_PATH:"* ]]; then
    export HDF5_PLUGIN_PATH="${HDF5_PLUGIN_PATH:+$HDF5_PLUGIN_PATH:}$PLUGIN_PATH"
fi

# Append to LD_LIBRARY_PATH
if [[ ":$LD_LIBRARY_PATH:" != *":$PLUGIN_PATH:"* ]]; then
    export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$PLUGIN_PATH"
fi

# Append to DYLD_LIBRARY_PATH (macOS)
if [[ ":$DYLD_LIBRARY_PATH:" != *":$PLUGIN_PATH:"* ]]; then
    export DYLD_LIBRARY_PATH="${DYLD_LIBRARY_PATH:+$DYLD_LIBRARY_PATH:}$PLUGIN_PATH"
fi

echo "H5TurboPFor environment configured."
echo "HDF5_PLUGIN_PATH: $HDF5_PLUGIN_PATH"

if [ ! -f "$PLUGIN_PATH/libH5Zturbopfor.so" ] && [ ! -f "$PLUGIN_PATH/libH5Zturbopfor.dylib" ]; then
    echo ""
    echo "WARNING: The H5TurboPFor plugin library was not found in:"
    echo "  $PLUGIN_PATH"
    echo "Please ensure you have built the project using 'cmake' and 'make'."
fi

