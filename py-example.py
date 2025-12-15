import os
import subprocess
import h5py

# -----------------------------------------------------------------------------
# Build steps (Removed - please build manually as per README)
# -----------------------------------------------------------------------------
# subprocess.run(["cmake", "."], check=True)
# subprocess.run(["make"], check=True)
# subprocess.run(["make", "install"], check=True)

# -----------------------------------------------------------------------------
# Environment setup
# -----------------------------------------------------------------------------
PWD = os.getcwd()

def append_env_path(var_name: str, value: str) -> None:
    current = os.environ.get(var_name, "")
    os.environ[var_name] = f"{current}:{value}" if current else value

append_env_path("HDF5_PLUGIN_PATH", PWD)
append_env_path("FILTER_LIB_PATH", os.environ.get("HDF5_PLUGIN_PATH", ""))
append_env_path("LD_LIBRARY_PATH", os.environ.get("HDF5_PLUGIN_PATH", ""))
append_env_path("DYLD_LIBRARY_PATH", os.environ.get("HDF5_PLUGIN_PATH", ""))

# -----------------------------------------------------------------------------
# Processing logic
# -----------------------------------------------------------------------------
H5TURBOPFOR_ID = 62016
CHUNK_X = 5
CHUNK_Y = 5
PROCESS_CHUNK_SIZE = 15 * 15

def process_data(original_das_file: str, compressed_das_file: str) -> None:
    with h5py.File(original_das_file, "r") as src_file:
        src_dset = src_file["data"]
        shape = src_dset.shape

        compression_args = (
            0,
            0,
            CHUNK_X,
            CHUNK_Y,
            shape[2],
        )

        with h5py.File(compressed_das_file, "w") as dst_file:
            dst_dset = dst_file.create_dataset(
                "data",
                shape=shape,
                dtype="int16",
                chunks=(CHUNK_X, CHUNK_Y, shape[2]),
                compression=H5TURBOPFOR_ID,
                compression_opts=compression_args,
            )

            total_chunks = (
                (shape[0] // PROCESS_CHUNK_SIZE)
                * (shape[1] // PROCESS_CHUNK_SIZE)
            )
            processed_chunks = 0

            print(src_dset[0, 0, :])

            for x in range(0, shape[0], PROCESS_CHUNK_SIZE):
                for y in range(0, shape[1], PROCESS_CHUNK_SIZE):
                    data = src_dset[
                        x : x + PROCESS_CHUNK_SIZE,
                        y : y + PROCESS_CHUNK_SIZE,
                        :
                    ]

                    dst_dset[
                        x : x + PROCESS_CHUNK_SIZE,
                        y : y + PROCESS_CHUNK_SIZE,
                        :
                    ] = (data * 0.01 + 330 - 273.15) * 20

                    processed_chunks += 1
                    progress = (processed_chunks / total_chunks) * 100
                    print(f"Progress: {progress:.2f}%")

                dst_dset.flush()

# -----------------------------------------------------------------------------
# Batch processing
# -----------------------------------------------------------------------------
def process_multiple_files(file_names):
    for file_name in file_names:
        # Use local file for example
        original_path = file_name
        compressed_path = f"{file_name.rsplit('.', 1)[0]}_compressed_pfor.h5"
        
        if not os.path.exists(original_path):
            print(f"Skipping {original_path}: File not found")
            continue

        print(f"Processing {original_path} -> {compressed_path}")
        process_data(original_path, compressed_path)

file_names = [
    "das_example.h5",
]

process_multiple_files(file_names)
