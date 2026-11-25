# GSDFit

**Grain-Size Distribution Fitting Tools**

GSDFit provides fitting tools and a PyQt6 GUI for loading, fitting, and exporting grain-size distribution data.

## Download GSDFit for Windows

> [!IMPORTANT]
> **Windows users:** Download and run the pre-built installer—no Python or development environment is required.

**[Download the latest Windows installer](https://github.com/christian051105/Particle-Size-Distributions/releases/latest)**

## Installing GSDFit as a Python package on Windows, Linux, and macOS

The source code can be installed as a Python package using the following environment managers. We recommend the use of Pixi.

- **Pixi** — creates and activates the `gsdfit` Pixi environment
- **Conda** — creates and activates the `gsdfit` Conda environment
- **pip** — creates a Python virtual environment and installs the project package

This repository includes `pixi.toml` for Pixi, `environment.yml` for Conda, and `requirements.txt` for pip.

## Clone the repository

Clone the repository once, then enter the project directory:

```bash
git clone https://github.com/christian051105/Particle-Size-Distributions.git
cd Particle-Size-Distributions
```
## Create the environment

### with Pixi 

Install the Pixi environment and this project as an editable Python package:

```bash
pixi run install
```


### with Conda

Create the environment from `environment.yml`, activate it, and install this project as an editable Python package:

```bash
conda env create -f environment.yml
conda activate gsdfit
python -m pip install -e .
```

To update an existing Conda environment instead:

```bash
conda env update -n gsdfit -f environment.yml --prune
conda activate gsdfit
python -m pip install -e .
```

### with pip

Create and activate a Python virtual environment, install the dependencies, and install this project as an editable package:

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
python -m gsdfit
```

Or without activating the shell:

```bash
pixi run gui
```


### Conda root

Make sure the Conda environment is activated:

```bash
conda activate gsdfit
```
Then:
```bash
gsdfit-gui
```

Or launch the GUI directly:

```bash
python -m gsdfit
```

### pip

With the virtual environment activated:

```bash
gsdfit-gui
```

Or launch the GUI directly:

```bash
python -m gsdfit
```

## Building a Windows Distribution
Windows installers are built automatically via github actions when a new version is released. They can also be built manually by following the instructions below. 

### Requirements

The Windows build environment is provided by `gsdfit-dev.yml` and contains:

- Python >=3.14.6,<3.15
- PyQt6 >=6.11.0,<7
- pandas >=3.0.5,<4
- SciPy >=1.18.0,<2
- Matplotlib >=3.11.1,<4
- NumPy >=2.5.1,<3
- pip
- PyInstaller
- Make

You will also need Conda or Miniconda/Miniforge, Git and [Inno Setup](https://jrsoftware.org/inno-setup).

### Create and activate the development environment

From the repository root in a Windows terminal:

```bash
conda env create -f gsdfit-dev.yml
conda activate gsdfit-dev
python -m pip install -e .
```

If the environment already exists, update it instead:

```bash
conda env update -n gsdfit-dev -f gsdfit-dev.yml --prune
conda activate gsdfit-dev
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

With `gsdfit-dev` activated, run this command from the repository root:

```bash
make build
```

The provided Makefile removes an existing `dist/gsdfit` directory and uses `gsdfit.spec` to build the application with PyInstaller.

The distributable is written to:

```text
dist/gsdfit/
```

To remove generated build files:

```bash
make clean
```

### Build the Windows installer

After building `dist/gsdfit`, install [Inno Setup](https://jrsoftware.org/isinfo.php). The installer script is `gsdfit.iss`, and the resulting setup executable is written to `dist/`.

To compile the installer with the fallback version defined in `gsdfit.iss`, open a Command Prompt or PowerShell window in the repository root and run:

```powershell
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" gsdfit.iss
```

To use a specific release version, pass it as `MyAppVersion`:

```powershell
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DMyAppVersion=1.2.3 gsdfit.iss
```

For example, version `1.2.3` creates:

```text
dist/GSDFit-1.2.3-Setup.exe
```