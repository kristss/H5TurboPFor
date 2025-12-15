#!/bin/bash
set -e

# Directory to install dependencies
DEPS_DIR="${PWD}/deps"
mkdir -p "$DEPS_DIR"

echo "Installing dependencies into $DEPS_DIR..."

# --- TurboPFor ---
if [ ! -d "$DEPS_DIR/TurboPFor-Integer-Compression" ]; then
    echo "Cloning TurboPFor-Integer-Compression..."
    git clone https://github.com/powturbo/TurboPFor-Integer-Compression.git "$DEPS_DIR/TurboPFor-Integer-Compression"
    
    echo "Building TurboPFor..."
    cd "$DEPS_DIR/TurboPFor-Integer-Compression"
    make
    cd -
else
    echo "TurboPFor-Integer-Compression already exists. Skipping clone."
fi

# Set environment variable for CMake
export TurboPFor_HOME="$DEPS_DIR/TurboPFor-Integer-Compression"

echo ""
echo "Dependencies setup complete."
echo "TurboPFor_HOME is set to: $TurboPFor_HOME"
echo ""
echo "You can now build the plugin:"
echo "  mkdir -p build"
echo "  cd build"
echo "  cmake .."
echo "  make"
echo ""
echo "Don't forget to source setup.sh before using the plugin!"
