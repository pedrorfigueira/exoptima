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
