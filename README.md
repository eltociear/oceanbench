# OceanBench: Sea Surface Height Edition [IN PROGRESS!]

Primary Devs:
* J. Emmanuel Johnson
* Quentin Febvre

Other Devs:
* Maxime B
* Sammy Metref
* Maxime B
* Ronan Fablet

---
## About

This repo will provide the full preprocessing and postprocessing pipeline for sea surface height interpolation.
It builds upon the SSH interpolation data challenges already provide across several repos.
This will prove the data-driving learning community with a suite of tools to make the modeling
framework easier.

---

## Package Elements


### Data Storage


We use `AWS` as our primary storage (for now) with `dvc` to track the data changes.

### Configurations

We use `hydra` for all of our configuration definitions.

### Geopreprocessing

We use `xarray` and various other packages to handle the geo-processing (e.g. slicing, etc)

### Storage

We use `.zarr` files (with an xarray backend) to store all datasets for training.


### Datasets, DataLoaders, DataModules

We use `pytorch-lightning` to handle our datasets, dataloaders and data modules.


---
## Tutorials


* How to download the data from AWS (**TODO**)
* How to load the data from `dvc` (**TODO**)

---

## Installation Guide


### pip

We can directly install it via pip from the

```bash
pip install "git+https://github.com/jejjohnson/oceanbench.git"
```

### Cloning

We can also clone the git repository

```bash
git clone https://github.com/jejjohnson/oceanbench.git
cd oceanbench
```

#### Conda Environment (RECOMMENDED)

We use conda/mamba as our package manager. To install from the provided environment files
run the following command.

```bash
mamba env create -n environments/linux.yaml
```

**Note**: we also have a `macos.yaml` file for MACOS users as well.


#### Testing dependency

In order to run the tests, first run the following:

```
pip install --no-deps xarray-dataclasses
```
#### poetry

The easiest way to get started is to simply use the poetry package which installs all necessary dev packages as well

```bash
poetry install
```

#### pip

We can also install via `pip` as well

```bash
pip install .
```

---
## Conversion between `.ipynb` and `.py`

Above examples are stored in [jbook/content](jbook/content) directory in the myst.md (`md`) format. Checkout [jupytext
using-cli](https://jupytext.readthedocs.io/en/latest/using-cli.html) for more
info.

* To convert `example.md` to `example.ipynb`, run:

```bash
jupytext --to notebook example.md
```

* To convert `example.ipynb` to `example.md`, run:

```bash
jupytext --to myst example.ipynb
```


 ## Jupyter 
 if you want to add the oceanbench conda environment as a jupyter kernel, you need to set the ESMF environment variable:

  ```
  conda activate oceanbench
  mamba install ipykernel -y 
  python -m ipykernel install --user --name=oceanbench --env ESMFMKFILE "$ESMFMKFILE"

