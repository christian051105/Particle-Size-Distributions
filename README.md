psdfit - Particle-Size Distribution Fitting

psdfit provides tools and a PyQt6 graphical interface for loading, fitting, and exporting particle-size distribution data.

## Requirements

- [Pixi](https://pixi.sh/), [Conda or Miniconda](https://docs.conda.io/), or Python (>=3.14.6) with `pip`
- Git

## Choose an installation pathway
The psdfit module can be installed using one of the following environment managers. We recommend using Pixi.

- **Pixi** — creates and activates the `psdfit` Pixi environment
- **Conda** — creates and activates the `psdfit` Conda environment
- **pip** — creates a Python virtual environment and installs the project module

This repository includes `pixi.toml` for Pixi, `environment.yml` for Conda, and `requirements.txt` for pip.

## Clone the repository

Clone the repository once, then enter the project directory:

```bash
git clone https://github.com/christian051105/Particle-Size-Distributions.git
cd Particle-Size-Distributions
```
## Create the environment

### with Pixi 

Install the Pixi environment and this project as an editable Python module:

```bash
pixi run install
```


### with Conda

Create the environment from `environment.yml`, activate it, and install this project as an editable Python module:

```bash
conda env create -f environment.yml
conda activate psdfit
python -m pip install -e .
```

To update an existing Conda environment instead:

```bash
conda env update -f environment.yml --prune
conda activate psdfit
python -m pip install -e .
```

### with pip

Create and activate a Python virtual environment, install the dependencies, and install this project as an editable module:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

Run pip commands from inside this project directory.

## Launch the GUI

### Pixi

First activate the Pixi environment from the Particle-Size-Distribution directory:

```bash
pixi shell
```
Then with the Pixi shell activated:

```bash
psdfit-gui
```
or 

```bash
python -m psdfit
```

Or without activating the shell:

```bash
pixi run gui
```


### Conda root

Make sure the Conda environment is activated:

```bash
conda activate psdfit
```
Then:
```bash
psdfit-gui
```

Or launch the Python module directly:

```bash
python -m psdfit
```

### pip

With the virtual environment activated:

```bash
psdfit-gui
```

Or launch the Python module directly:

```bash
python -m psdfit
```
## Building a Windows Distribution

### Requirements

The Windows build environment is provided by `psdfit-dev.yml` and contains:

- Python >=3.14.6,<3.15
- PyQt6 >=6.11.0,<7
- pandas >=3.0.5,<4
- SciPy >=1.18.0,<2
- Matplotlib >=3.11.1,<4
- NumPy >=2.5.1,<3
- pip
- PyInstaller
- Make

You will also need Conda or Miniconda/Miniforge and Git.

### Create and activate the development environment

From the repository root in a Windows terminal:

```bash
conda env create -f psdfit-dev.yml
conda activate psdfit-dev
python -m pip install -e .
```

If the environment already exists, update it instead:

```bash
conda env update -n psdfit-dev -f psdfit-dev.yml --prune
conda activate psdfit-dev
python -m pip install -e .
```

Verify the build tools and package dependencies:

```bash
python --version
pyinstaller --version
make --version
python -c "import PyQt6, pandas, scipy, matplotlib, numpy; print('Build dependencies available')"
```

### Build the distribution

With `psdfit-dev` activated, run this command from the repository root:

```bash
make build
```

The provided Makefile removes an existing `dist/psdfit` directory and uses `psdfit.spec` to build the application with PyInstaller.

The distributable is written to:

```text
dist/psdfit/
```

To remove generated build files:

```bash
make clean
```