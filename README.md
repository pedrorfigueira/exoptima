# `exoptima` - **EXOTICA Observation Preparation Tool for Instrumentation and Mission Assessment** 

<img src="exoptima/assets/exoptima-logo.svg" alt="EXOPTIMA logo" width="220" align="right">

`exoptima` is a browser-based interface for planning astronomical observations developed as support for the **EXOTICA** project. 

The user interface is opened via a command-line tool that launches a Panel server and runs entirely in Python.

## ✨ Features

**TBD**

## 📦 Installation

### 1. Install Python ≥ 3.10

### 2. Create and activate a virtual environment (recommended)

For instance, using `conda`
```
conda create -n fist python=3.10
conda activate exoptima
```
### 3. Download and install package locally

Clone the repository and move to its local folder

```
git clone https://github.com/pedrorfigueira/exoptima.git
cd exoptima
```

and run

```
pip install .
```
To install in editable / developer mode use the flag `-e`; this enables live code editing without having to reinstall.

## 🔧 Dependencies

`exoptima` depends on the following Python packages:

- Python ≥ 3.10
- [NumPy](https://numpy.org/)
- [Astropy](https://www.astropy.org/)
- [Bokeh](https://bokeh.org/)
- [Panel](https://panel.holoviz.org/)
- [Matplotlib](https://matplotlib.org/)

All dependencies are declared in `pyproject.toml` and are installed automatically when running `pip install .`.

## 🖥️ Running and using `opt`

After installation, the software can be launched from the command line

```
exoptima
```

Where:

 - `--port 6006` specifies the port on which the web server runs. Default: `5006`.
 - `--host 0.0.0.0` specifies the network interface to bind to; useful when accessing the interface from another machine on the same network. Default: `127.0.0.1`
 - `--no-show` prevent `opt` from opening a web browser; recommended when running on a remote machine or over SSH.

When launched, the interface opens in your browser and displays a series of controls (left) and visibility and analysis tools (right). 

## 📚 Folder Structure

```
exoptima/
├── README.md
├── LICENSE
├── pyproject.toml
├── .gitignore
│
└── exoptima/
    ├── __init__.py
    ├── app.py
    ├── cli.py
    │
    ├── core/
    │   ├── __init__.py
    │   ├── state.py       
    │   ├── observability.py       
    │   └── precision.py   
    │
    ├── config/
    │   ├── __init__.py
    │   ├── instruments.py
    │   ├── computation.py
    │   └── layout.py
    │
    ├── tabs/
    │   ├── __init__.py
    │   ├── interface.py
    │   ├── controls.py
    │   ├── display.py
    │   └── export.py
    │
    └── assets/
        ├── exoptima-alogo.svg
        └── exoptima-logo.svg
```

## TODO
- [ ] Check behavior of time constr on plot
- [ ] Implement monthly weather-loss statistics

## 📄 License

This project is distributed under the MIT License.

## 🙌 Acknowledgements

Pedro Figueira acknowledges financial support from the Severo Ochoa grant CEX2021-001131-S funded by MCIN/AEI/10.13039/501100011033. Pedro Figueira is also funded by the European Union (ERC, THIRSTEE, 101164189). Views and opinions expressed are however those of the author(s) only and do not necessarily reflect those of the European Union or the European Research Council. Neither the European Union nor the granting authority can be held responsible for them.

This project depends on several open-source scientific and visualization packages. We gratefully acknowledge their authors and contributors:

[NumPy](https://numpy.org/) and [Scipy](https://scipy.org/) provide the core array infrastructure and numerical utilities used in backend processing. [Astropy](https://www.astropy.org/) provides tools for FITS and for reading, parsing, and handling astronomical data formats. [Matplotlib](https://matplotlib.org/) is used for plotting and[Panel](https://panel.holoviz.org/) enables the UI layout, reactive widgets, and server backend that make this application possible as a web interface.

We extend sincere thanks to all of these communities for developing and maintaining the scientific Python ecosystem.
