import os
import sys

# --- Auto-configure HDF5 Plugin Path for Testing ---
# If HDF5_PLUGIN_PATH is not set, try to find the build directory relative to this script
# MUST BE DONE BEFORE IMPORTING h5py
if "HDF5_PLUGIN_PATH" not in os.environ:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    build_dir = os.path.join(project_root, "build")
    
    if os.path.exists(os.path.join(build_dir, "libH5Zturbopfor.so")) or \
       os.path.exists(os.path.join(build_dir, "libH5Zturbopfor.dylib")):
        print(f"Auto-configuring HDF5_PLUGIN_PATH to: {build_dir}")
        os.environ["HDF5_PLUGIN_PATH"] = build_dir
    else:
        print("Warning: Could not find libH5Zturbopfor.so in build/. Please run 'source setup.sh' or build the project.")

import h5py
import numpy as np

# Configuration
FILE_NAME = "validation_test.h5"
FILTER_ID = 62016  # Must match TURBOPFOR_FILTER in turbopfor_h5plugin.c
DATA_SHAPE = (1000, 1000) # 1 million points
CHUNK_SHAPE = (100, 100)

def quantize_data(data):
    """
    Mimics Open-Meteo quantization: Float -> Int16
    Maps min/max of data to the full range of int16.
    """
    print("--- Quantization Step ---")
    data_min = np.nanmin(data)
    data_max = np.nanmax(data)
    
    # Avoid division by zero
    if data_max == data_min:
        scale = 1.0
    else:
        # Map to range [-32767, 32767] (leaving -32768 for potential nodata)
        scale = (data_max - data_min) / (2 * 32767)
    
    offset = (data_max + data_min) / 2
    
    print(f"Data Range: [{data_min:.4f}, {data_max:.4f}]")
    print(f"Calculated Scale: {scale:.6f}, Offset: {offset:.6f}")
    
    # Quantize
    # Formula: value = scale * integer + offset
    # Therefore: integer = (value - offset) / scale
    data_int16 = np.round((data - offset) / scale).astype(np.int16)
    
    return data_int16, scale, offset

def dequantize_data(data_int16, scale, offset):
    """
    Reconstructs Float from Int16.
    """
    return data_int16.astype(np.float32) * scale + offset

def run_validation():
    # 1. Generate Synthetic Data (e.g., Temperature field)
    print(f"Generating {DATA_SHAPE} random float data...")
    # Create smooth-ish data to test delta encoding effectiveness
    x = np.linspace(0, 10, DATA_SHAPE[1])
    y = np.linspace(0, 10, DATA_SHAPE[0])
    xv, yv = np.meshgrid(x, y)
    original_data = np.sin(xv) * np.cos(yv) * 20.0 + 15.0 # Temp between -5 and 35
    original_data = original_data.astype(np.float32)

    # 2. Quantize (User Side)
    data_int16, scale, offset = quantize_data(original_data)

    # 3. Write to HDF5 with TurboPFor Filter
    print(f"\nWriting to {FILE_NAME} with Filter ID {FILTER_ID}...")
    if os.path.exists(FILE_NAME):
        os.remove(FILE_NAME)

    with h5py.File(FILE_NAME, "w", libver='latest') as f:
        # Filter options: [type (0=short), ignored, chunk_dim0, chunk_dim1]
        cd_values = (0, 0, CHUNK_SHAPE[0], CHUNK_SHAPE[1])
        
        dset = f.create_dataset(
            "temperature",
            data=data_int16,
            chunks=CHUNK_SHAPE,
            compression=FILTER_ID,
            compression_opts=cd_values
        )
        
        # Store metadata for reconstruction
        dset.attrs["scale_factor"] = scale
        dset.attrs["add_offset"] = offset
        
        file_size = os.path.getsize(FILE_NAME)
        raw_size = data_int16.nbytes
        print(f"Original Size (Int16): {raw_size / 1024 / 1024:.2f} MB")
        print(f"Compressed File Size:  {file_size / 1024 / 1024:.2f} MB")
        print(f"Compression Ratio:     {raw_size / file_size:.2f}x")

    # 4. Read Back and Validate
    print("\nReading back and validating...")
    with h5py.File(FILE_NAME, "r") as f:
        dset = f["temperature"]
        read_int16 = dset[:]
        read_scale = dset.attrs["scale_factor"]
        read_offset = dset.attrs["add_offset"]
        
        # Check raw integer integrity
        if np.array_equal(data_int16, read_int16):
            print("SUCCESS: Raw Int16 data matches exactly.")
        else:
            print("FAILURE: Raw Int16 data mismatch!")
            diff = np.abs(data_int16 - read_int16)
            print(f"Max integer difference: {np.max(diff)}")
            return

        # Check reconstructed float values
        reconstructed_data = dequantize_data(read_int16, read_scale, read_offset)
        max_error = np.max(np.abs(original_data - reconstructed_data))
        
        print(f"Max Reconstruction Error: {max_error:.6f}")
        # Error should be roughly scale / 2
        expected_error = scale
        if max_error <= expected_error:
            print(f"SUCCESS: Error is within quantization precision ({expected_error:.6f}).")
        else:
            print("WARNING: Error is larger than expected.")

if __name__ == "__main__":
    run_validation()
