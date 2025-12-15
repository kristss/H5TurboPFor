# H5TurboPFor (Experimental Fork)

This repository is a **specialized fork** of [H5TurboPFor](https://github.com/dbinlbl/H5TurboPFor). It retains the original HDF5 plugin framework and Filter ID (`62016`) but **replaces the internal compression logic** with an Open-Meteo inspired pipeline (Delta Encoding + ZigZag).

The original software is part of the research paper:
* **Real-time and post-hoc compression for data from distributed acoustic sensing**, Bin Dong, Alex Popescu, Ver ́onica Rodr ́ıguez Tribaldos, Suren Byna, Jonathan Ajo-Franklin, Kesheng Wu, and the Imperial Valley Dark Fiber Team. Submitted on Sept 2021.*

## Features (Experimental)

*   **TurboPFor Integration**: Wraps the TurboPFor integer compression library for HDF5.
*   **Modified Pipeline**: Includes experimental Open-Meteo Delta and ZigZag encoding steps to test compression on meteorological data.
*   **Build System**: Updated CMake configuration and installation scripts for easier setup.
*   **Python Support**: Integration with `h5py` and `uv` package manager.

# Installation Guide

## Prerequisites

- **C/C++ Compiler**: GCC, Clang, or MSVC.
- **CMake**: Version 3.1 or higher.
  - Ubuntu: `sudo apt-get install cmake`
  - macOS: `brew install cmake`
- **HDF5**: Development headers and libraries.
  - Ubuntu: `sudo apt-get install libhdf5-dev`
  - macOS: `brew install hdf5`
- **MPI**: Message Passing Interface (Required).
  - Ubuntu: `sudo apt-get install libopenmpi-dev`
  - macOS: `brew install open-mpi`
- **Python**: 3.8 or higher.
- **uv**: Python package manager (optional but recommended).

## Step 1: Install Dependencies

We provide a script to download and build the required `TurboPFor` library.

```bash
chmod +x install_deps.sh
./install_deps.sh
```

This will clone `TurboPFor-Integer-Compression` into a `deps/` directory and build it. It also sets the `TurboPFor_HOME` environment variable for the build step.

## Step 2: Build H5TurboPFor Plugin

```bash
# Ensure TurboPFor_HOME is set (if you just ran install_deps.sh, it printed the path)
export TurboPFor_HOME=$(pwd)/deps/TurboPFor-Integer-Compression

mkdir -p build
cd build
cmake ..
make
cd ..
```

## Step 3: Configure Environment

Source the `setup.sh` script to add the plugin to your `HDF5_PLUGIN_PATH`. This tells HDF5 where to find the `H5Zturbopfor` plugin.

```bash
source setup.sh
```

# Usage with Python and uv

We recommend using `uv` to manage your Python environment.

1.  **Initialize a project (if needed):**

    ```bash
    uv init
    ```

2.  **Add dependencies:**

    ```bash
    uv add h5py numpy
    ```

3.  **Run your code:**

    Ensure `setup.sh` has been sourced in your current shell.

    ```bash
    uv run python py-example.py
    ```

### Python Example

```python
> python3 py-example.py
> h5dump -pH das_example_compressed_pfor.h5
```

## Running Tests

To validate the compression pipeline and quantization logic:

```bash
uv run python tests/test_compression.py
```

# Usage in C/C++

Based on the `H5TurboPFor_HOME` and `HDF5_HOME` set above:

```bash
export HDF5_PLUGIN_PATH=$HDF5_PLUGIN_PATH:$H5TurboPFor_HOME/lib
export LD_LIBRARY_PATH=$HDF5_PLUGIN_PATH:$HDF5_HOME/lib
# For macOS
export DYLD_LIBRARY_PATH=$LD_LIBRARY_PATH
```

Minimum code to use H5TurboPFor:

```c
unsigned int filter_flags = H5Z_FLAG_MANDATORY;
H5Z_filter_t filter_id = 62016;
hid_t create_dcpl_id = H5Pcreate(H5P_DATASET_CREATE);

/*
 * @param cd_values: the pointer of the parameter 
 * cd_values[0]: type of data:  short (0),  int (1)
 * cd_values[1]: Ignored (previously scalefactor)
 * cd_values[2, -]: size of each dimension of a chunk 
 */
size_t filter_cd_nelmts = 4;
unsigned int filter_cd_values[4];
filter_cd_values[0] = 0;
filter_cd_values[1] = 1; // Ignored
filter_cd_values[2] = 100;
filter_cd_values[3] = 100;

H5Pset_filter(create_dcpl_id, filter_id, filter_flags, filter_cd_nelmts, filter_cd_values);

hsize_t filter_chunk_size[2] = {100, 100};
H5Pset_chunk(create_dcpl_id, 2, filter_chunk_size);

hid_t did = H5Dcreate(fid, "FNAME", H5T_STD_I16LE, space_id, H5P_DEFAULT, create_dcpl_id, H5P_DEFAULT);
```

## Compression Pipeline

This plugin implements a compression pipeline inspired by Open-Meteo:

1.  **Quantization (User Responsibility)**: Convert floating-point data to `int16` (short). This step must be performed by the user before passing data to the HDF5 filter.
2.  **Vertical Delta Encoding**: Applies a 2D delta encoding (difference between adjacent rows) to exploit spatial/temporal correlations.
3.  **TurboPFor Compression**: Uses the TurboPFor library with ZigZag encoding to compress the delta-encoded integers.

# License

This project is a fork of H5TurboPFor.

*   **H5TurboPFor**: Original code is Copyright (c) 2021, The Regents of the University of California.
*   **TurboPFor-Integer-Compression**: This project links against the [TurboPFor-Integer-Compression](https://github.com/powturbo/TurboPFor-Integer-Compression) library, which is licensed under **GPLv2**.
*   **Open-Meteo Inspiration**: The delta encoding logic is inspired by [Open-Meteo](https://github.com/open-meteo/om-file-format), which is licensed under **AGPLv3**.

Consequently, binaries produced by this project are subject to the terms of the **GPLv3** (or compatible) license.

H5TurboPFor Copyright (c) 2021, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Dept. of Energy). All rights reserved.

If you have questions about your rights to use or distribute this software, please contact Berkeley Lab's Intellectual Property Office at IPO@lbl.gov.

NOTICE. This Software was developed under funding from the U.S. Department of Energy and the U.S. Government consequently retains certain rights. As such, the U.S. Government has been granted for itself and others acting on its behalf a paid-up, nonexclusive, irrevocable, worldwide license in the Software to reproduce, distribute copies to the public, prepare derivative works, and perform publicly and display publicly, and to permit others to do so.

*** License Agreement ***

H5TurboPFor Copyright (c) 2021, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Dept. of Energy). All rights reserved.
