# Changelog

## v1.0.0 — 2026-01-19
### Added
- Observability computation (night / month / year)
- Transit-constrained observability
- RV precision calculator
- Panel-based GUI

### Changed
- Refactored observability core (pure functions)
- Separated UI from scientific core

### Fixed
- Planet parameter propagation
- Transit handling logic

## v1.0.1 — 2026-01-20
### Added
- CARMENES-VIS, NIRPS-HA, NIRPS-HE instruments

### Changed
- EXOTICA resolution updated to 65k
- Weather statistics moved to inside corresponding Observatory class

### Fixed
- pyproject.toml include matplotlib and assets from .svg in a clean way

## v1.0.2 — 2026-01-30
### Fixed
- Simbad query:
  - verbose on what is successfully loaded and what fails;
  - V mag and SpTp default to None / G2 at start and with failed loads
  - if Vmag SpTp not defined other parameters are still loaded and observability computation is still possible

## v1.1.0 — 2026-03-20
### Added
- Option to save plots in .png/.pdf and to save input conditions with the .txt summary.
- Star B-V and Gaia DR3 ids, plus hyperlinks to Simbad and Gaia queries
- Instrument+Telescope preset and readout overheads included

### Fixed
- Cleaner and simpler messages in observability summaries

## v1.2.0 — 2026-03-30
### Added
- Implementation of instantaneous airmass and seeing from Conditions tab.
- definition of on-sky fiber size, central wavelength, and extinction for instruments
- computation of chromatic fiber losses and adjustment of S/N and precision

### Changed
- default constrains defined in config/computation.py
- usage of three mask values G2/K2/M2 for simplicity

## v1.2.1 — 2026-08-18
### Fixed
- Issues with matplotlib backend on MacOS and get_moon() deprecation fix (issues #1, #2)

## v1.3.0 — 2026-09-25
### Added
- Iarget name is included in filenames of Observability plots and text summaries.
- Inclusion of AltAz info in Instrument class and zenith avoidance zone on observability.
- time offset controls improved

### Changed
- In the summaries, distinction between "not observable tonight" and "observable tonight"

## v1.3.1 — 2026-10-02
### Added
- Observing conditions are included in the RV precision summary.

### Fixed
- Handling of missing values in SIMBAD queries.
- More robust display scheme, now respecting predefined screen ratio values.

## v1.4.0 — 2026-10-26
### Added
- Save and Load input via .json files, controlled in the new Input/Output tab
- Workdir and file naming controllable by user

### Fixed
- Monthly and Yearly observability plots show beginning of night on top, and mark it graphically

## v2.0.0 — 2026-11-16

### Added
- **Scheduling mode implemented**: ability to create, configure and manipulate observing queues.
- Added queue ordering tools: by right ascension, to minimize airmass, and to minimize airmass while maximizing the temporal separation of repeated observations.
- Added queue save/load functionality, including restoration of configuration and observability calculations.
- Added observability visualization for individual targets and their scheduled integrations.
- Added support for selecting the SIMBAD server (CDS, Harvard or IDIA) through the configuration file, allowing alternative mirrors to be used when the primary service is unavailable.
- Added section-specific indicators to signal when recalculation is required.

### Changed
- Reorganized code to separate Planning and Scheduling into independent applications, with dedicated state management and user interfaces.
- Introduced shared services and configuration modules to centralize common functionality and settings.
- Improved the Load/Save interface to display and allow direct selection of existing files.
- Improved queue controls, including manual reordering and individual target priorities and constraints.
- Minor cosmetic changes (favicon, harmonized controls, etc.).

### Fixed
- Minor issues with display widgets, including rounding of input values and handling of NaNs.
- Improved consistency of observability calculations and handling of observing constraints.