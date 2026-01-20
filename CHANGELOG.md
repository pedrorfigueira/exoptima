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