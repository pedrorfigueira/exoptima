"""
Instrument configuration for EXOPTIMA / OPT.

All quantities are given explicitly with units documented.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from astroplan import Observer
from astropy.coordinates import EarthLocation
import astropy.units as u

# ------------------------------------------------------------------
# Data models
# ------------------------------------------------------------------

@dataclass(frozen=True)
class WeatherStatistics:
    """
    Weather loss statistics for an observatory/instrument.
    Fractions refer to *usable time* (not lost time).
    """

    description: str                            # explanatory text
    reference_url: str                          # authoritative webpage
    yearly_usable_fraction: float
    monthly_usable_fraction: Dict[str, float] | None = None  # keys: "Jan", "Feb", ...

@dataclass(frozen=True)
class Observatory:
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float

    def to_astroplan_observer(self) -> Observer:
        """
        Convert this Observatory into an Astroplan Observer.
        """
        location = EarthLocation(
            lat=self.latitude_deg * u.deg,
            lon=self.longitude_deg * u.deg,
            height=self.elevation_m * u.m,
        )

        return Observer(
            location=location,
            name=self.name,
            timezone="UTC",
        )

@dataclass(frozen=True)
class Instrument:
    name: str
    observatory: Observatory
    resolution: int                     # lambda / delta_lambda
    telescope_diameter: float           # primary mirror diameter
    rv_precision_mps: Optional[float] = None
    weather_statistics: Optional[WeatherStatistics] = None


# ------------------------------------------------------------------
# Observatories
# ------------------------------------------------------------------

LA_SILLA = Observatory(
    name="La Silla Observatory",
    latitude_deg=-29.2567,
    longitude_deg=-70.7346,
    elevation_m=2400,
)

LA_PALMA = Observatory(
    name="Roque de los Muchachos Observatory",
    latitude_deg=28.7606,
    longitude_deg=-17.8850,
    elevation_m=2396,
)

PARANAL = Observatory(
    name="Paranal Observatory",
    latitude_deg=-24.6270,
    longitude_deg=-70.4040,
    elevation_m=2635,
)

CALAR_ALTO = Observatory(
    name="Calar Alto Observatory",
    latitude_deg=37.2236,
    longitude_deg=-2.5463,
    elevation_m=2168,
)

# ------------------------------------------------------------------
# Instruments
# ------------------------------------------------------------------

INSTRUMENTS: Dict[str, Instrument] = {

    "EXOTICA": Instrument(
        name="EXOTICA",
        observatory=CALAR_ALTO,
        resolution=60000,
        telescope_diameter=1.23,
        rv_precision_mps=None,
        weather_statistics=WeatherStatistics(
            yearly_usable_fraction=0.70,
            description=(
                "Derived from long-term Calar Alto night statistics "
                "as reported in the literature."
            ),
            reference_url="https://arxiv.org/abs/0709.0813",
        ),
    ),

    "CORALIE": Instrument(
        name="CORALIE",
        observatory=LA_SILLA,
        resolution=60000,
        telescope_diameter=1.2,
        rv_precision_mps=3.0,
        weather_statistics=WeatherStatistics(
            yearly_usable_fraction=0.80,
            description=(
                "Crude estimate from the very limited available information. "
                "Contact Instrument Scientists at La Silla for more."
            ),
            reference_url="https://www.eso.org/sci/facilities/lasilla/astclim/weather.html",
        ),
    ),

    "HARPS": Instrument(
        name="HARPS",
        observatory=LA_SILLA,
        resolution=115000,
        telescope_diameter=3.6,
        rv_precision_mps=1.0,
        weather_statistics=WeatherStatistics(
            yearly_usable_fraction=0.80,
            description=(
                "Crude estimate from the very limited available information. "
                "Contact Instrument Scientists at La Silla for more."
            ),
            reference_url="https://www.eso.org/sci/facilities/lasilla/astclim/weather.html",
        ),
    ),

    "HARPS-N": Instrument(
        name="HARPS-N",
        observatory=LA_PALMA,
        resolution=115000,
        telescope_diameter=3.58,
        rv_precision_mps=1.0,
        weather_statistics=WeatherStatistics(
            yearly_usable_fraction=0.70,
            description=(
                "Estimate based on refereed publication."
                "Published studies find ~63% (ground-based) to ~72% (satellite-based) clear-night fraction." 
                "Used upper range for spectroscopic nights."
            ),
            reference_url="https://academic.oup.com/mnras/article/401/3/1904/1096431",
        ),
    ),

    "ESPRESSO": Instrument(
        name="ESPRESSO",
        observatory=PARANAL,
        resolution=140000,
        telescope_diameter=8.2,
        rv_precision_mps=0.1,
        weather_statistics=WeatherStatistics(
            yearly_usable_fraction=0.90,
            description=(
                "Based on long-term ESO statistics. "
                "Considers photometric, clear and thin-cloud nights."
            ),
            reference_url="https://www.eso.org/sci/facilities/paranal/astroclimate/Obsconditions.html",
        ),
    ),

}
