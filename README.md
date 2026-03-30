# `exoptima` - **EXOTICA Observation Preparation Tool for Instrumentation and Mission Analysis**

<img src="exoptima/assets/exoptima-logo.svg" alt="EXOPTIMA logo" width="250" align="right">

`exoptima` is a browser-based interface for planning astronomical observations developed as support for the **EXOTICA** project.

It streamlines observability computations, using SIMBAD id queries, observatory and instrument databases, and typical constraints used for RV studies. These can be done not only for a night but visualized over a month or the whole year. It also allows calculation of transit visibility. It uses simple scaling laws to estimate the RV precision attained on different spectrographs, including **EXOTICA**.

The user interface is opened via a command-line tool that launches a Panel server and runs entirely on Python.

## ✨ Features

### 🌌 Target-Based Observability

* Automatic SIMBAD resolution of targets
* Single-night, monthly, and yearly observability computation
* Constraints on Airmass and Moon properties, suitable for spectroscopy


### 🏔️ Observatory & Instrument Awareness

* Built-in database of instruments with:

  * Observatory location
  * Telescope diameter
  * Spectral resolution
  * Weather Statistics

* Supported spectrographs: EXOTICA, CORALIE, HARPS/HARPS-N, ESPRESSO, KPF, CARMENES and NIRPS (extensible)

### 🎯 RV Precision Estimation

* Reference-based RV model using V magnitude, Spectral type, and Exposure time.

* Scaling laws:

  * **S/N ∝ D · √t · 10⁻⁰·²Δmag**
  * **RV ∝ 1/SNR · R⁻¹·⁵**

* Automatic fallback scaling from ESPRESSO for instruments without native models


### 🪐 Planet Detection Significance

* Computes RV semi-amplitude **K** using:

  * Optimistic case (i = 90°, e = 0)
  * Realistic case (⟨sin i⟩, median eccentricity)

* Detection significance curves **K / σRV vs exposure time** for optimistic and realistic scenarios

### 🧩 Extensible Architecture

* Modular design enabling:

  * New instruments (and observatories)
  * Future multi-scenario support
  * batch processing for a large number of stars and constraints

---

### RV Precision Estimation Model

EXOPTIMA estimates radial-velocity (RV) precision using a physically motivated scaling model anchored to instrument-specific reference values. For instruments without their own RV calibration model, results are scaled from the **ESPRESSO** spectrograph using telescope diameter, spectral resolution, exposure time, target magnitude, and observing conditions.

#### Reference Model

For each supported spectral mask (**G2, K2, M2**), the RV precision model provides:

* Reference signal-to-noise ratio: `SNR_ref`
* Reference RV precision: `σ_RV,ref`

defined at:

* a reference exposure time `t_ref`
* a reference magnitude `m_ref`
* a reference airmass `X_ref`
* a reference seeing `seeing_ref`

These reference values are instrument-dependent and represent the calibration point from which EXOPTIMA scales.

#### Signal-to-Noise Scaling

The signal-to-noise ratio is assumed to scale as:

SNR ∝ D · √t · 10^(-0.2 · (m − `m_ref`))

where:

* ( D ) is the telescope diameter
* ( t ) is the exposure time
* ( m ) is the target magnitude

In practice:

SNR = `SNR_ref` · (D / `D_ref`) · √(t / `t_ref`) · 10^(-0.2 · (m − `m_ref`))

#### Throughput Corrections

EXOPTIMA additionally applies a first-order correction for observing conditions through a relative throughput factor:

T = `T_airmass` × `T_fiber`

where:

* `T_airmass` accounts for atmospheric extinction as a function of **airmass** and **instrument central wavelength**
* `T_fiber` accounts for **fiber coupling losses** as a function of **seeing** and **fiber diameter on sky**

The effective seeing at the instrument wavelength is estimated from the user-provided seeing at 0.55 µm using a Kolmogorov scaling law:

seeing(λ) ∝ λ^(-1/5)

The final signal-to-noise ratio is then corrected relative to the instrument reference conditions:

SNR = `SNR_ref,scaled` × √(T / `T_ref`)

where `T_ref` is the throughput under the instrument reference airmass and seeing.

This ensures that changes in airmass and seeing are applied **relative to the calibration point**, rather than as an absolute loss.

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
  * Relative throughput correction from observing conditions

#### Scope and Limitations

This model is intended as a **first-order feasibility estimator**, not as a replacement for a full instrument exposure-time calculator.

It assumes:

* photon-noise–dominated performance
* a centered point source
* Gaussian image quality for fiber coupling
* no detailed treatment of blaze response, tellurics, line density, detector systematics, or template mismatch
* a single representative wavelength per instrument

As such, it is best suited for:

* quick target feasibility assessment
* approximate exposure-time planning
* relative instrument comparison

The user is reminded graphically of the barrier at **SNR < 30**, where the approximations become unreliable, and **30 < SNR < 50**, where results should be interpreted with caution.

## 📦 Installation

### 1. Install Python ≥ 3.10

### 2. Create and activate a virtual environment (recommended)

For instance, using `conda`
```
conda create -n exoptima python=3.10
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
- [Astroquery](https://astroquery.readthedocs.io)
- [Astroplan](https://astroplan.readthedocs.io/)
- [Panel](https://panel.holoviz.org/)
- [Matplotlib](https://matplotlib.org/)

All dependencies are declared in `pyproject.toml` and are installed automatically when running `pip install .`.

## 🖥️ Running and using `exoptima`

After installation, the software can be launched from the command line

```
exoptima
```

and the interface opens in your browser, displaying a series of controls (left) and visualization panes (right).

## 📚 Folder Structure

```
exoptima/
├── README.md
├── CHANGELOG.md
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
- [ ] allow ingestion of input via config files
- [ ] allow multiple stellar input in a queue
- [ ] Implement monthly weather-loss statistics

## 📄 License

This project is distributed under the MIT License.

## 🙌 Acknowledgements

Immense thanks to Luc Weber and Nicolas Buchschacher for all they thought me about observing tools through the years!

Pedro Figueira acknowledges financial support from the Severo Ochoa grant CEX2021-001131-S funded by MCIN/AEI/10.13039/501100011033. Pedro Figueira is also funded by the European Union (ERC, THIRSTEE, 101164189). Views and opinions expressed are however those of the author(s) only and do not necessarily reflect those of the European Union or the European Research Council. Neither the European Union nor the granting authority can be held responsible for them.

This project depends on several open-source scientific and visualization packages. We gratefully acknowledge their authors and contributors:

NumPy and SciPy provide the core array infrastructure and numerical utilities used in backend processing. Astropy supplies the foundational astronomy framework, including coordinate handling, time systems, and FITS support. Astroplan is used for observability calculations and scheduling-related constraints, while Astroquery enables access to external astronomical databases such as SIMBAD. Matplotlib is used for plotting, and Panel provides the UI layout, reactive widgets, and server backend that power the web-based interface.

We extend sincere thanks to all of these communities for developing and maintaining the scientific Python ecosystem.
