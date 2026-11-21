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