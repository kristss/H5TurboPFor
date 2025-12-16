import os
import sys
import time
import numpy as np

# --- Auto-configure HDF5 Plugin Path ---
if "HDF5_PLUGIN_PATH" not in os.environ:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    build_dir = os.path.join(project_root, "build")
    if os.path.exists(os.path.join(build_dir, "libH5Zturbopfor.so")) or \
       os.path.exists(os.path.join(build_dir, "libH5Zturbopfor.dylib")):
        os.environ["HDF5_PLUGIN_PATH"] = build_dir

import h5py

INPUT_FILE = "material/norway_tasmin_2020.nc4"
OUTPUT_RAW = "material/benchmark_raw.h5"
OUTPUT_GZIP = "material/benchmark_gzip.h5"
OUTPUT_LZF = "material/benchmark_lzf.h5"
OUTPUT_SZIP = "material/benchmark_szip.h5"
OUTPUT_TURBO = "material/benchmark_turbopfor.h5"

FILTER_ID = 62016
# Chunking: All time steps, small spatial block
# Input shape is (366, 1550, 1195)
CHUNK_SHAPE = (366, 20, 20) 

def benchmark_read_timeseries(filename, num_points=1000):
    """
    Benchmarks random timeseries access.
    Reads full time dimension for random (y, x) locations.
    """
    if not os.path.exists(filename):
        return float('nan')
        
    with h5py.File(filename, "r") as f:
        dset = f["tasmin"]
        shape = dset.shape
        # shape is (Time, Y, X) -> (366, 1550, 1195)
        
        # Generate random coordinates
        ys = np.random.randint(0, shape[1], num_points)
        xs = np.random.randint(0, shape[2], num_points)
        
        start_time = time.time()
        
        # Perform reads
        for i in range(num_points):
            # Read full time series for one location
            _ = dset[:, ys[i], xs[i]]
            
        end_time = time.time()
        
    return end_time - start_time

def quantize_fixed(data, multiplier, fill_value_float):
    """
    Quantizes Float32 data to Int16 with fixed precision.
    Handles FillValues by mapping them to -32768.
    """
    print(f"  Quantizing (Multiplier: {multiplier}x)...")
    
    # Create mask for valid data
    # Check for NaN or specific FillValue
    if fill_value_float is not None:
        mask = (data != fill_value_float) & (~np.isnan(data))
    else:
        mask = ~np.isnan(data)
        
    valid_data = data[mask]
    
    if valid_data.size == 0:
        return np.full(data.shape, -32768, dtype=np.int16), 1.0/multiplier, 0.0

    # Calculate offset from valid data min
    offset = np.min(valid_data)
    scale = 1.0 / multiplier
    
    # Prepare output array filled with "No Data" (-32768)
    out = np.full(data.shape, -32768, dtype=np.int16)
    
    # Quantize valid data
    # val_int = (val_float - offset) * multiplier
    quantized = (valid_data - offset) * multiplier
    
    # Check bounds
    if np.max(np.abs(quantized)) > 32767:
        print("  WARNING: Quantized values exceed Int16 range!")
        
    out[mask] = np.round(quantized).astype(np.int16)
    
    return out, scale, offset

def run_benchmark():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file {INPUT_FILE} not found.")
        return

    print(f"Reading {INPUT_FILE} (via h5py)...")
    with h5py.File(INPUT_FILE, "r") as nc:
        # Read variable
        var = nc["tasmin"]
        data = var[:] # Read into memory
        
        # Handle FillValue
        fill_value = var.attrs.get("_FillValue")
        if isinstance(fill_value, np.ndarray):
            fill_value = fill_value[0]
            
        print(f"  Shape: {data.shape}")
        print(f"  Dtype: {data.dtype}")
        print(f"  FillValue: {fill_value}")

        # Convert Kelvin to Celsius
        print("  Converting Kelvin to Celsius...")
        valid_mask = (data != fill_value) & (~np.isnan(data))
        data[valid_mask] -= 273.15

    # --- 1. Quantize Data (Int16) ---
    print(f"\nQuantizing Data (Multiplier: 20.0x)...")
    data_int16, scale, offset = quantize_fixed(data, 20.0, fill_value)

    # --- 2. Raw Int16 (Uncompressed) ---
    print(f"\nWriting {OUTPUT_RAW} (Int16, Uncompressed)...")
    start = time.time()
    if os.path.exists(OUTPUT_RAW): os.remove(OUTPUT_RAW)
    with h5py.File(OUTPUT_RAW, "w", libver='latest') as f:
        dset = f.create_dataset("tasmin", data=data_int16, chunks=CHUNK_SHAPE)
        dset.attrs["scale_factor"] = scale
        dset.attrs["add_offset"] = offset
        dset.attrs["_FillValue"] = -32768
    print(f"  Time: {time.time() - start:.2f}s")

    # --- 3. GZIP Int16 ---
    print(f"\nWriting {OUTPUT_GZIP} (Int16, GZIP=4)...")
    start = time.time()
    if os.path.exists(OUTPUT_GZIP): os.remove(OUTPUT_GZIP)
    with h5py.File(OUTPUT_GZIP, "w", libver='latest') as f:
        dset = f.create_dataset("tasmin", data=data_int16, chunks=CHUNK_SHAPE, compression="gzip", compression_opts=4)
        dset.attrs["scale_factor"] = scale
        dset.attrs["add_offset"] = offset
        dset.attrs["_FillValue"] = -32768
    print(f"  Time: {time.time() - start:.2f}s")

    # --- 3a. LZF Int16 ---
    print(f"\nWriting {OUTPUT_LZF} (Int16, LZF)...")
    start = time.time()
    if os.path.exists(OUTPUT_LZF): os.remove(OUTPUT_LZF)
    with h5py.File(OUTPUT_LZF, "w", libver='latest') as f:
        dset = f.create_dataset("tasmin", data=data_int16, chunks=CHUNK_SHAPE, compression="lzf")
        dset.attrs["scale_factor"] = scale
        dset.attrs["add_offset"] = offset
        dset.attrs["_FillValue"] = -32768
    print(f"  Time: {time.time() - start:.2f}s")

    # --- 3b. Shuffle + GZIP Int16 ---
    OUTPUT_SHUFFLE_GZIP = "material/benchmark_shuffle_gzip.h5"
    print(f"\nWriting {OUTPUT_SHUFFLE_GZIP} (Int16, Shuffle + GZIP=4)...")
    start = time.time()
    if os.path.exists(OUTPUT_SHUFFLE_GZIP): os.remove(OUTPUT_SHUFFLE_GZIP)
    with h5py.File(OUTPUT_SHUFFLE_GZIP, "w", libver='latest') as f:
        dset = f.create_dataset("tasmin", data=data_int16, chunks=CHUNK_SHAPE, compression="gzip", compression_opts=4, shuffle=True)
        dset.attrs["scale_factor"] = scale
        dset.attrs["add_offset"] = offset
        dset.attrs["_FillValue"] = -32768
    print(f"  Time: {time.time() - start:.2f}s")

    # --- 4. SZIP Int16 ---
    print(f"\nWriting {OUTPUT_SZIP} (Int16, SZIP)...")
    start = time.time()
    if os.path.exists(OUTPUT_SZIP): os.remove(OUTPUT_SZIP)
    try:
        with h5py.File(OUTPUT_SZIP, "w", libver='latest') as f:
            # SZIP options: ('nn', 32) is a common default (Nearest Neighbor, 32 pixels per block)
            dset = f.create_dataset("tasmin", data=data_int16, chunks=CHUNK_SHAPE, compression="szip", compression_opts=('nn', 32))
            dset.attrs["scale_factor"] = scale
            dset.attrs["add_offset"] = offset
            dset.attrs["_FillValue"] = -32768
        print(f"  Time: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"  Failed: {e}")
        if os.path.exists(OUTPUT_SZIP): os.remove(OUTPUT_SZIP)

    # --- 4. TurboPFor Int16 ---
    print(f"\nWriting {OUTPUT_TURBO} (Int16, TurboPFor)...")
    start = time.time()
    
    if os.path.exists(OUTPUT_TURBO): os.remove(OUTPUT_TURBO)
    with h5py.File(OUTPUT_TURBO, "w", libver='latest') as f:
        # Filter Args: [type=0(short), ignored, dim0, dim1, dim2]
        cd_values = (0, 0) + CHUNK_SHAPE
        
        dset = f.create_dataset(
            "tasmin",
            data=data_int16,
            chunks=CHUNK_SHAPE,
            compression=FILTER_ID,
            compression_opts=cd_values
        )
        dset.attrs["scale_factor"] = scale
        dset.attrs["add_offset"] = offset
        dset.attrs["_FillValue"] = -32768
        
    print(f"  Time: {time.time() - start:.2f}s")

    # --- Read Benchmarks ---
    print("\nRunning Read Benchmarks (1000 random timeseries)...")
    read_times = {}
    files_to_test = [
        ("Raw Int16", OUTPUT_RAW),
        ("GZIP Int16", OUTPUT_GZIP),
        ("LZF Int16", OUTPUT_LZF),
        ("Shuffle+GZIP", OUTPUT_SHUFFLE_GZIP),
        ("SZIP Int16", OUTPUT_SZIP),
        ("TurboPFor Int16", OUTPUT_TURBO)
    ]
    
    for name, path in files_to_test:
        if os.path.exists(path):
            try:
                t = benchmark_read_timeseries(path, num_points=1000)
                read_times[name] = t
                print(f"  {name}: {t:.4f}s")
            except Exception as e:
                print(f"  {name}: FAILED ({e})")
                read_times[name] = float('nan')
        else:
            read_times[name] = float('nan')

    # --- Report ---
    print("\n=== Results (Int16 Quantized) ===")
    sizes = {
        "Original (NC4)": os.path.getsize(INPUT_FILE),
        "Raw Int16 (H5)": os.path.getsize(OUTPUT_RAW),
        "GZIP Int16 (H5)": os.path.getsize(OUTPUT_GZIP) if os.path.exists(OUTPUT_GZIP) else 0,
        "LZF Int16 (H5)": os.path.getsize(OUTPUT_LZF) if os.path.exists(OUTPUT_LZF) else 0,
        "Shuffle+GZIP (H5)": os.path.getsize(OUTPUT_SHUFFLE_GZIP) if os.path.exists(OUTPUT_SHUFFLE_GZIP) else 0,
        "SZIP Int16 (H5)": os.path.getsize(OUTPUT_SZIP) if os.path.exists(OUTPUT_SZIP) else 0,
        "TurboPFor Int16 (H5)": os.path.getsize(OUTPUT_TURBO)
    }
    
    base_size = sizes["Raw Int16 (H5)"]
    
    print(f"{'Format':<20} | {'Size (MB)':<10} | {'Ratio':<8} | {'Read 1k (s)':<12}")
    print("-" * 60)
    for name, size in sizes.items():
        mb = size / (1024 * 1024)
        ratio = base_size / size if size > 0 else 0
        
        # Map file name to read time key
        read_key = name.replace(" (H5)", "")
        r_time = read_times.get(read_key, float('nan'))
        
        r_str = f"{r_time:.4f}" if not np.isnan(r_time) else "-"
        
        print(f"{name:<20} | {mb:<10.2f} | {ratio:<8.2f} | {r_str:<12}")

if __name__ == "__main__":
    run_benchmark()
