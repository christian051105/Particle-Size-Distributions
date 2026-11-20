# TGSD — Particle-Size Distribution Fitting

TGSD provides tools and a PyQt6 graphical interface for loading, fitting, and exporting particle-size distribution data.

## Requirements

- Linux
- [Pixi](https://pixi.sh/) for environment and task management
- Git

## Setup for a new installation

From your terminal:

```bash
git clone <repository-url>
cd TGSD
pixi run install
```

The `install` task uses the Pixi environment and installs this project in editable mode. Re-run it after cloning or when the project metadata changes.

To enter the Pixi environment manually instead:

```bash
pixi shell
pip install -e .
```

## Launch the GUI

After installation, launch the GUI from the TGSD root directory by default:

```bash
psdfit-gui
```

Alternatively, run it through Pixi:

```bash
pixi run gui
```

Or launch the Python module directly:

```bash
python -m psdfit
```

The first option requires an editable installation, such as `pixi run install`. The alternative Pixi and module commands should be run from the TGSD root directory.

## Pixi tasks

List the available tasks:

```bash
pixi task list
```

Install the package:

```bash
pixi run install
```

Launch the GUI:

```bash
pixi run gui
```
