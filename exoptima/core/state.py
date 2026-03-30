# General state variables and dataclasses used to store it

import param
from dataclasses import dataclass
from typing import Sequence, Optional
from datetime import date

import numpy as np

from astropy import units as u
from astropy.time import Time

from exoptima.config.instruments import Instrument, INSTRUMENTS

# ----------------------------------------
# Objects used to store params and results
# ----------------------------------------

@dataclass(frozen=True)
class Star:
    name: str
    ra: str
    dec: str
    vmag: float | None
    sptype: str

@dataclass
class PlanetParameters:
    """
    Planet and stellar parameters relevant for RV precision and detectability.
    """
    planet_mass_mjup: Optional[float] = None            # MJup
    orbital_period_days: Optional[float] = None         # days
    stellar_mass_msun: float = 1.0                      # MSun (default 1)

    t0_jd: Optional[float] = None                       # JD reference transit time
    total_observation_duration: Optional[float] = None  # hours
    include_transit_in_observability: bool = False

@dataclass
class ObservingConditions:
    # airmass constraints
    max_airmass: float
    min_duration: u.Quantity

    # Moon-related constraints
    min_moon_separation: float           # degrees
    ignore_moon_if_fli_above: float      # fraction (0–1)

    # instantaneous seeing and airmass
    seeing_arcsec: float
    airmass_rv: float

@dataclass
class ObservabilityResult:
    time_grid: Time
    altitude: u.Quantity
    mask: np.ndarray
    observable_time: u.Quantity
    night_start: Time
    night_end: Time
    night_duration: u.Quantity
    is_observable: bool
    min_airmass : float
    min_moon_sep : float
    mean_fli : float

@dataclass(frozen=True)
class NightObservability:
    date: date                     # civil date of the night (sunset date)
    result: ObservabilityResult    # full single-night observability

@dataclass(frozen=True)
class MultiNightObservability:
    nights: Sequence[NightObservability]

# ----------------------------------------
#   Valid entris for string inputs
# ----------------------------------------

VALID_SPTYPES = ["G2", "K2", "M2"]

VALID_NIGHT_DEFINITIONS = [
    "Sunset to sunrise",
    "Nautical twilight",
    "Astronomical twilight",
]

# ----------------------------------------
#   Master State
# ----------------------------------------

class AppState(param.Parameterized):
    # ---------------------------------
    # Scientific state
    # ---------------------------------
    star = param.ClassSelector(class_=Star, allow_None=True)
    instrument = param.ClassSelector(class_=Instrument, allow_None=True)
    conditions = param.ClassSelector(class_=ObservingConditions, allow_None=False)

    planet_params = param.ClassSelector(
        class_=PlanetParameters,
        allow_None=False,
        doc="Planet and stellar parameters for RV computations",
    )

    exposure_time = param.Number(
        default=60.0,
        bounds=(1, None),
        doc="Exposure time in seconds for RV precision computation",
    )

    observability = param.ClassSelector(
        class_=ObservabilityResult,
        allow_None=True,
        default=None,
    )

    monthly_observability = param.ClassSelector(
        class_=MultiNightObservability,
        allow_None=True,
        default=None,
        doc="Observability results for monthly scope",
    )

    yearly_observability = param.ClassSelector(
        class_=MultiNightObservability,
        allow_None=True,
        default=None,
        doc="Observability results for yearly scope",
    )

    precision_result = param.Dict(
        default=None,
        doc="Result object of RV precision computation",
    )

    # ---------------------------------
    # UI / execution scope
    # ---------------------------------
    observability_scope = param.ObjectSelector(
        default="Night",
        objects=["Night", "Month", "Year"],
        doc="Scope of observability computation",
    )

    weather_losses_mode = param.ObjectSelector(
        default="None",
        objects=[
            "None",
            "Yearly average",
            "Monthly average",
        ],
        doc="Weather losses model to apply",
    )

    # ---------------------------------
    # Progress tracking in computation
    # ---------------------------------
    is_computing_observability = param.Boolean(
        default=False,
        doc="True while observability computation is running",
    )

    is_computing_precision = param.Boolean(
        default=False,
        doc="True while precision computation is running",
    )

    # ---------------------------------
    # UI validity / readiness flags
    # ---------------------------------
    star_coords_valid = param.Boolean(default=False)
    star_vmag_defined = param.Boolean(default=False)

    # ---------------------------------
    # Application hooks
    # ---------------------------------
    on_compute_observability = param.Callable(default=None)
    on_compute_precision = param.Callable(default=None)

    # ---------------------------------
    # Time used for observability
    # ---------------------------------
    reference_time = param.ClassSelector(
        class_=Time,
        allow_None=False,
        default=Time.now(),
        doc="Reference time for observability computation (UTC)",
    )

    # ---------------------------------
    # Night limits
    # ---------------------------------
    night_definition = param.ObjectSelector(
        default="Nautical twilight",
        objects=VALID_NIGHT_DEFINITIONS,
        doc="Definition of night boundaries for observability",
    )

    # ---------------------------------
    # Cache of computed nights
    # ---------------------------------
    night_cache = param.Dict(
        default={},
        doc="Cache: date -> NightObservability"
    )

    def __init__(self, **params):
        super().__init__(**params)

        self.planet_params = PlanetParameters()

        # Import here to avoid config ↔ state circular dependency
        from exoptima.config.computation import (
            DEFAULT_SP_TYPE,
            DEFAULT_EXPOSURE_TIME,
            DEFAULT_INSTRUMENT,
            DEFAULT_MAX_AIRMASS,
            DEFAULT_MIN_DURATION_HOUR,
            DEFAULT_MIN_MOON_SEP,
            DEFAULT_IGNORE_MOON_FLI,
            DEFAULT_SEEING_ARCSEC,
            DEFAULT_AIRMASS_RV,
            DEFAULT_NIGHT_DEFINITION,
        )

        if DEFAULT_SP_TYPE in VALID_SPTYPES:
            self.sp_type = DEFAULT_SP_TYPE
        else:
            print(
                f"Warning: DEFAULT_SPTYPE='{DEFAULT_SP_TYPE}' is invalid. "
                f"Falling back to 'G2'."
            )
            self.sp_type = "G2"

        self.exposure_time=DEFAULT_EXPOSURE_TIME

        if DEFAULT_INSTRUMENT not in INSTRUMENTS:
            raise ValueError(
                f"DEFAULT_INSTRUMENT='{DEFAULT_INSTRUMENT}' is not defined in INSTRUMENTS"
            )

        self.instrument=INSTRUMENTS[DEFAULT_INSTRUMENT]

        self.conditions = ObservingConditions(
            max_airmass=DEFAULT_MAX_AIRMASS,
            min_duration=DEFAULT_MIN_DURATION_HOUR * u.hour,
            min_moon_separation=DEFAULT_MIN_MOON_SEP,
            ignore_moon_if_fli_above=DEFAULT_IGNORE_MOON_FLI,
            seeing_arcsec=DEFAULT_SEEING_ARCSEC,
            airmass_rv=DEFAULT_AIRMASS_RV,
        )

        if DEFAULT_NIGHT_DEFINITION in VALID_NIGHT_DEFINITIONS:
            self.night_definition = DEFAULT_NIGHT_DEFINITION
        else:
            print(
                f"Warning: DEFAULT_NIGHT_DEFINITION='{DEFAULT_NIGHT_DEFINITION}' "
                f"is invalid. Falling back to 'Nautical twilight'."
            )
            self.night_definition = "Nautical twilight"
