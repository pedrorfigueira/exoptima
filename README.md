# `exoptima` - **EXOTICA Observation Preparation Tool for Instrumentation and Mission Analysis** 

<img src="exoptima/assets/exoptima-logo.svg" alt="EXOPTIMA logo" width="250" align="right">

`exoptima` is a browser-based interface for planning astronomical observations developed as support for the **EXOTICA** project. 

The user interface is opened via a command-line tool that launches a Panel server and runs entirely in Python.

## ✨ Features

### 🌌 Target-Based Observability

* Automatic SIMBAD resolution of targets
* Single-night, monthly, and yearly observability computation
* Supports **Sunset–Sunrise**, **Nautical**, and **Astronomical twilight** definitions
* Constraints on Airmass and Moon properties, suitable for spectroscopy

---

### 🏔️ Observatory & Instrument Awareness

* Built-in database of instruments with:

  * Observatory location
  * Telescope diameter
  * Spectral resolution
  * Weather Statistics

* Supported spectrographs are EXOTICA, CORALIE, HARPS/HARPS-N, ESPRESSO (extensible)

### 🎯 RV Precision Estimation

* Reference-based RV model using:

  * Spectral type
  * V magnitude
  * Exposure time

* Scaling laws:

  * **S/N ∝ D · √t · 10⁻⁰·²Δmag**
  * **RV ∝ 1/SNR · R⁻¹·⁵**

* Automatic fallback scaling from ESPRESSO for instruments without native models


### 🪐 Planet Detection Significance

* Computes RV semi-amplitude **K** using:

  * Optimistic case (i = 90°, e = 0)
  * Realistic case (⟨sin i⟩, median eccentricity)

* Detection significance curves **K / σRV vs exposure time** for optimistic and realistic scenarios

---

### 🧩 Extensible Architecture

* Modular design enabling:

  * New instruments (and observatories)
  * Future multi-scenario support
  * batch processing for a large number of stars and constraints

---

### RV Precision Estimation Model

EXOPTIMA estimates radial-velocity (RV) precision using a physically motivated scaling model anchored to reference values provided for the **ESPRESSO** spectrograph. For instruments without their own RV calibration model, results are scaled from ESPRESSO using telescope diameter, spectral resolution, exposure time, and target magnitude.

#### Reference Model

For each supported spectral type (G2, K2, K7, M2), ESPRESSO provides:

* Reference signal-to-noise ratio: `SNR_ref`
* Reference RV precision: `σ_RV,ref`

calculated for a reference exposure time `t_ref` of 10 min and a reference magnitude `m_ref` of V=10.

These values were defined for a seeing of 1.0" and an airmass of 1.3, which we consider to be standard conditions.

#### Signal-to-Noise Scaling

The signal-to-noise ratio is assumed to scale as:

SNR ∝ D · √t · 10^(-0.2 · (m − `m_ref`))

where:

* ( D ) is the telescope diameter for the chosen instrument
* ( t ) is the exposure time
* ( m ) is the target magnitude

In practice, for the input-provided parameters:

SNR = `SNR_ref` · (D / `D_ref`) · √(t / `t_ref`) · 10^(-0.2 · (m − `m_ref`))

#### RV Precision Scaling

Radial-velocity precision is assumed to scale as:

RV ∝ (1 / SNR) · R^(-1.5)

where ( R ) is the spectral resolution.

Thus:

σ_RV = `σ_RV,ref` · (`SNR_ref` / SNR) · (`R_ref` / R)^1.5

#### Instrument Handling

* If an instrument provides its own RV estimation model, it is used directly.
* Otherwise, [ESPRESSO](https://www.eso.org/observing/etc/bin/gen/form?INS.NAME=ESPRESSO+INS.MODE=spectro) is used as the reference instrument and results are scaled using:

  * Telescope diameter ratio
  * Spectral resolution ratio
  * Exposure time
  * Target magnitude

#### Scope and Limitations

This model:

* Assumes photon-noise–dominated performance
* Remains a good approximation for seeing conditions similar to the fiber diameter, which should be the case by construction
* Does not (yet) include:

  * Throughput differences
  * Wavelength band dependence
  * Seeing, airmass, or sky background effects
  * Stellar rotation 

The goal is to provide **order-of-magnitude realistic estimates** suitable for feasibility assessment and instrument comparison, not detailed exposure-time calculator accuracy.

The user is reminded graphically of the barrier of SNR < 30, where the approximations do not hold, and 30 < SNR < 50, where they are poor and should not be used either.

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

`exoptima` uses Python ≥ 3.10 and depends on the following packages:
- [NumPy](https://numpy.org/)
- [Astropy](https://www.astropy.org/)
- [Panel](https://panel.holoviz.org/)
- [Matplotlib](https://matplotlib.org/)

All dependencies are declared in `pyproject.toml` and are installed automatically when running `pip install .`.

## 🖥️ Running and using `exoptima`

After installation, the software can be launched from the command line

```
exoptima
```

Where:

 - `--port 6006` specifies the port on which the web server runs. Default: `5006`.
 - `--host 0.0.0.0` specifies the network interface to bind to; useful when accessing the interface from another machine on the same network. Default: `127.0.0.1`
 - `--no-show` prevent `exoptima` from opening a web browser; recommended when running on a remote machine or over SSH.

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
- [ ] test precision estimation with ETCs
- [ ] implement orbit sampling and transit scheduling
- [ ] allow ingestion of input via files
- [ ] include average / user-defined seeing and airmass penalty (?)
- [ ] Implement monthly weather-loss statistics

## 📄 License

This project is distributed under the MIT License.

## 🙌 Acknowledgements

Pedro Figueira acknowledges financial support from the Severo Ochoa grant CEX2021-001131-S funded by MCIN/AEI/10.13039/501100011033. Pedro Figueira is also funded by the European Union (ERC, THIRSTEE, 101164189). Views and opinions expressed are however those of the author(s) only and do not necessarily reflect those of the European Union or the European Research Council. Neither the European Union nor the granting authority can be held responsible for them.

This project depends on several open-source scientific and visualization packages. We gratefully acknowledge their authors and contributors:

[NumPy](https://numpy.org/) and [Scipy](https://scipy.org/) provide the core array infrastructure and numerical utilities used in backend processing. [Astropy](https://www.astropy.org/) provides tools for FITS and for reading, parsing, and handling astronomical data formats. [Matplotlib](https://matplotlib.org/) is used for plotting and[Panel](https://panel.holoviz.org/) enables the UI layout, reactive widgets, and server backend that make this application possible as a web interface.

We extend sincere thanks to all of these communities for developing and maintaining the scientific Python ecosystem.
