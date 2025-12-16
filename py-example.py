import h5py
import numpy as np
import os
import sys

# --- Auto-configure HDF5 Plugin Path ---
# This ensures the script can find the compiled plugin in the build/ directory
if "HDF5_PLUGIN_PATH" not in os.environ:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(current_dir, "build")
    
    if os.path.exists(os.path.join(build_dir, "libH5Zturbopfor.so")) or \
       os.path.exists(os.path.join(build_dir, "libH5Zturbopfor.dylib")):
        print(f"Auto-configuring HDF5_PLUGIN_PATH to: {build_dir}")
        os.environ["HDF5_PLUGIN_PATH"] = build_dir
    else:
        print("Warning: Could not find libH5Zturbopfor.so in build/. Please run 'source setup.sh' or build the project.")

# Configuration
OUTPUT_FILE = "demo_weather_data.h5"
FILTER_ID = 62016
SHAPE = (100, 100, 100) # Time, Lat, Lon
CHUNK_SHAPE = (1, 100, 100) # Chunk per time step

def generate_weather_data(shape):
    """Generates synthetic temperature-like data (smooth gradients)."""
    print(f"Generating synthetic weather data {shape}...")
    t = np.linspace(0, 10, shape[0])
    y = np.linspace(0, 10, shape[1])
    x = np.linspace(0, 10, shape[2])
    
    # Create a 3D field: T(t,y,x) = 20 + 10*sin(t) + 5*cos(y) + 2*sin(x)
    # This mimics daily cycles and spatial variation
    tt, yy, xx = np.meshgrid(t, y, x, indexing='ij')
    data = 20.0 + 10.0 * np.sin(tt) + 5.0 * np.cos(yy) + 2.0 * np.sin(xx)
    
    # Add some random noise
    data += np.random.normal(0, 0.5, shape)
    return data.astype(np.float32)

def quantize(data):
    """
    Quantizes Float32 data to Int16 for compression.
    Returns: (int16_data, scale, offset)
    """
    print("Quantizing data (Float32 -> Int16)...")
    min_val = np.nanmin(data)
    max_val = np.nanmax(data)
    
    # Map [min, max] -> [-32767, 32767]
    scale = (max_val - min_val) / (2 * 32767)
    offset = (max_val + min_val) / 2
    
    data_int16 = np.round((data - offset) / scale).astype(np.int16)
    return data_int16, scale, offset

def main():
    # 1. Create Data
    data_float = generate_weather_data(SHAPE)
    
    # 2. Quantize
    data_int16, scale, offset = quantize(data_float)
    
    # 3. Write Compressed File
    print(f"Writing to {OUTPUT_FILE}...")
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        
    with h5py.File(OUTPUT_FILE, "w", libver='latest') as f:
        # Filter Args: [type=0(short), ignored, chunk_dim_vertical, chunk_dim_horizontal]
        # Note: We pass the last two dimensions of the chunk as the "2D" block size
        cd_values = (0, 0, CHUNK_SHAPE[1], CHUNK_SHAPE[2])
        
        dset = f.create_dataset(
            "temperature",
            data=data_int16,
            chunks=CHUNK_SHAPE,
            compression=FILTER_ID,
            compression_opts=cd_values
        )
        
        # Save quantization parameters as attributes
        dset.attrs["scale_factor"] = scale
        dset.attrs["add_offset"] = offset
        dset.attrs["units"] = "Celsius"

    # 4. Report Results
    original_size = data_int16.nbytes
    compressed_size = os.path.getsize(OUTPUT_FILE)
    ratio = original_size / compressed_size
    
    print("-" * 40)
    print(f"Original Size (Int16): {original_size / 1024:.2f} KB")
    print(f"Compressed Size:       {compressed_size / 1024:.2f} KB")
    print(f"Compression Ratio:     {ratio:.2f}x")
    print("-" * 40)
    print("Success! You can inspect the file with:")
    print(f"  h5dump -H {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
