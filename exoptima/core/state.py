# General state variables and dataclasses used to store it

import param
from dataclasses import dataclass
from typing import Sequence
from datetime import date

import numpy as np

from astropy import units as u
from astropy.time import Time

from exoptima.config.instruments import Instrument

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
class ObservingConditions:
    # airmass constraints
    max_airmass: float = 2.0
    min_duration: u.Quantity = 1 * u.hour

    # Moon-related constraints
    min_moon_separation: float = 30.0      # degrees
    ignore_moon_if_fli_above: float = 0.5  # fraction (0–1)

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
#   Master State
# ----------------------------------------

class AppState(param.Parameterized):
    # ---------------------------------
    # Scientific state
    # ---------------------------------
    star = param.ClassSelector(class_=Star, allow_None=True)
    instrument = param.ClassSelector(class_=Instrument, allow_None=True)
    conditions = param.ClassSelector(class_=ObservingConditions, allow_None=False)

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
        objects=[
            "Sunset to sunrise",
            "Nautical twilight",
            "Astronomical twilight",
        ],
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

        # Import here to avoid config ↔ state circular dependency
        from exoptima.config.computation import (
            DEFAULT_MAX_AIRMASS,
            DEFAULT_MIN_DURATION,
            DEFAULT_MIN_MOON_SEP,
            DEFAULT_IGNORE_MOON_FLI,
        )

        self.conditions = ObservingConditions(
            max_airmass=DEFAULT_MAX_AIRMASS,
            min_duration=DEFAULT_MIN_DURATION,
            min_moon_separation=DEFAULT_MIN_MOON_SEP,
            ignore_moon_if_fli_above=DEFAULT_IGNORE_MOON_FLI,
        )
