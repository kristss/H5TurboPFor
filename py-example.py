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

import h5py

# Configuration
OUTPUT_FILE = "demo_weather_data.h5"
FILTER_ID = 62016
SHAPE = (100, 100, 100) # Time, Lat, Lon
CHUNK_SHAPE = (100, 20, 20) # Optimized for Timeseries 

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

def quantize_fixed(data, multiplier):
    """
    Quantizes Float32 data using a fixed precision multiplier.
    Formula: int_val = (float_val - offset) * multiplier
    Returns: (int16_data, scale, offset)
    """
    print(f"Quantizing data (Fixed Multiplier: {multiplier}x)...")
    
    # We use an offset to center the data or fit it within int16
    # If we didn't use an offset, 300K * 100 = 30000 (fits), but 330K * 100 overflows.
    # Using min_val as offset ensures we start from 0.
    offset = np.nanmin(data)
    
    # Calculate scale factor for reconstruction (value = int * scale + offset)
    scale = 1.0 / multiplier
    
    # Quantize
    scaled_data = (data - offset) * multiplier
    
    # Check for overflow
    if np.nanmax(np.abs(scaled_data)) > 32767:
        print(f"WARNING: Data range too large for multiplier {multiplier} in Int16!")
    
    data_int16 = np.round(scaled_data).astype(np.int16)
    return data_int16, scale, offset

def main():
    # 1. Create Data
    data_float = generate_weather_data(SHAPE)
    
    # 2. Prepare Datasets
    datasets = []
    
    # Case A: High Precision (0.01 K -> Multiplier 100)
    d_100, s_100, o_100 = quantize_fixed(data_float, 100.0)
    datasets.append({
        "name": "temperature_high_res",
        "desc": "Precision 0.01 (100x)",
        "data": d_100, "scale": s_100, "offset": o_100
    })
    
    # Case B: Low Precision (0.05 K -> Multiplier 20)
    d_20, s_20, o_20 = quantize_fixed(data_float, 20.0)
    datasets.append({
        "name": "temperature_low_res",
        "desc": "Precision 0.05 (20x)",
        "data": d_20, "scale": s_20, "offset": o_20
    })
    
    # 3. Write Compressed File
    print(f"Writing to {OUTPUT_FILE}...")
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        
    with h5py.File(OUTPUT_FILE, "w", libver='latest') as f:
        # Filter Args: [type=0(short), ignored, dim0, dim1, dim2, ...]
        # We pass all chunk dimensions so the filter can flatten them correctly
        cd_values = (0, 0) + CHUNK_SHAPE
        
        for ds_info in datasets:
            dset = f.create_dataset(
                ds_info["name"],
                data=ds_info["data"],
                chunks=CHUNK_SHAPE,
                compression=FILTER_ID,
                compression_opts=cd_values
            )
            
            # Save quantization parameters
            dset.attrs["scale_factor"] = ds_info["scale"]
            dset.attrs["add_offset"] = ds_info["offset"]
            dset.attrs["units"] = "Celsius"
            dset.attrs["description"] = ds_info["desc"]

    # 4. Report Results
    print("-" * 60)
    print(f"{'Dataset':<25} | {'Orig (KB)':<10} | {'Comp (KB)':<10} | {'Ratio':<5}")
    print("-" * 60)
    
    with h5py.File(OUTPUT_FILE, "r") as f:
        for ds_info in datasets:
            name = ds_info["name"]
            dset = f[name]
            
            # Get compressed size (storage size)
            # Note: get_storage_size() returns the size of the allocated chunks
            comp_size = dset.id.get_storage_size()
            orig_size = dset.size * dset.dtype.itemsize
            ratio = orig_size / comp_size if comp_size > 0 else 0
            
            print(f"{name:<25} | {orig_size/1024:<10.2f} | {comp_size/1024:<10.2f} | {ratio:<5.2f}x")
            
    print("-" * 60)
    print("Success! You can inspect the file with:")
    print(f"  h5dump -H {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
