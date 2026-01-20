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
    weather_statistics: WeatherStatistics | None = None

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
class RVEstimation:
    """
    Reference RV precision and SNR values for a spectrograph.

    All values are defined at:
        - reference_exptime (seconds)
        - reference_mag (V magnitude)

    Dictionaries are keyed by spectral type: "G2", "K2", "K7", "M2"
    """

    ref_exptime: float   # seconds
    ref_mag: float       # V magnitude

    ref_snr: Dict[str, Optional[float]]
    ref_rv_precision: Dict[str, Optional[float]]  # m/s

@dataclass(frozen=True)
class Instrument:
    name: str
    observatory: Observatory
    resolution: int                     # lambda / delta_lambda
    telescope_diameter: float           # primary mirror diameter
    rv_estimation: Optional[RVEstimation] = None

# ------------------------------------------------------------------
# Observatories
# ------------------------------------------------------------------

LA_SILLA = Observatory(
    name="La Silla Observatory",
    latitude_deg=-29.2567,
    longitude_deg=-70.7346,
    elevation_m=2400,
    weather_statistics=WeatherStatistics(
        yearly_usable_fraction=0.80,
        description=(
            "Crude estimate from the very limited available information. "
            "Contact Instrument Scientists at La Silla for more."
        ),
        reference_url="https://www.eso.org/sci/facilities/lasilla/astclim/weather.html",
    ),
)

LA_PALMA = Observatory(
    name="Roque de los Muchachos Observatory",
    latitude_deg=28.7606,
    longitude_deg=-17.8850,
    elevation_m=2396,
    weather_statistics=WeatherStatistics(
        yearly_usable_fraction=0.70,
        description=(
            "Estimate based on refereed publication."
            "Published studies find ~63% (ground-based) to ~72% (satellite-based) clear-night fraction."
            "Used upper range for spectroscopic nights."
        ),
        reference_url="https://academic.oup.com/mnras/article/401/3/1904/1096431",
    ),
)

PARANAL = Observatory(
    name="Paranal Observatory",
    latitude_deg=-24.6270,
    longitude_deg=-70.4040,
    elevation_m=2635,
    weather_statistics=WeatherStatistics(
            yearly_usable_fraction=0.90,
            description=(
                "Based on long-term ESO statistics. "
                "Considers photometric, clear and thin-cloud nights."
            ),
            reference_url="https://www.eso.org/sci/facilities/paranal/astroclimate/Obsconditions.html",
        ),
)

CALAR_ALTO = Observatory(
    name="Calar Alto Observatory",
    latitude_deg=37.2236,
    longitude_deg=-2.5463,
    elevation_m=2168,
    weather_statistics=WeatherStatistics(
                yearly_usable_fraction=0.70,
                description=(
                    "Derived from long-term Calar Alto night statistics "
                    "as reported in the literature."
                ),
                reference_url="https://arxiv.org/abs/0709.0813",
            ),
)

KECK_OBSERVATORY = Observatory(
    name="W. M. Keck Observatory",
    latitude_deg=19.8261,
    longitude_deg=-155.4749,
    elevation_m=4160,
    weather_statistics=WeatherStatistics(
            yearly_usable_fraction=0.76,  # seems low, but that's what is published
            description="Mauna Kea long-term weather statistics (clear fraction).",
            reference_url="https://arxiv.org/abs/0811.2448",
        ),
)

# ------------------------------------------------------------------
# Instruments
# ------------------------------------------------------------------

INSTRUMENTS: Dict[str, Instrument] = {

    "EXOTICA": Instrument(
        name="EXOTICA",
        observatory=CALAR_ALTO,
        resolution=65000,
        telescope_diameter=1.23,
        rv_estimation=None,
    ),

    "CORALIE": Instrument(
        name="CORALIE",
        observatory=LA_SILLA,
        resolution=60000,
        telescope_diameter=1.2,
        rv_estimation=None,
    ),

    "HARPS": Instrument(
        name="HARPS",
        observatory=LA_SILLA,
        resolution=115000,
        telescope_diameter=3.6,
        rv_estimation=None,
    ),

    "HARPS-N": Instrument(
        name="HARPS-N",
        observatory=LA_PALMA,
        resolution=115000,
        telescope_diameter=3.58,
        rv_estimation=None,
    ),

    "ESPRESSO": Instrument(
        name="ESPRESSO",
        observatory=PARANAL,
        resolution=140000,
        telescope_diameter=8.2,
        rv_estimation=RVEstimation(
            ref_exptime=600.0,
            ref_mag=10.0,
            ref_snr={
                "G2": 112.456,
                "K2": 113.19,
                "K7": 114.972,
                "M2": 110.771,
            },
            ref_rv_precision={
                "G2": 0.53,
                "K2": 0.53,
                "K7": 0.52,
                "M2": 0.54,
            },
        )
    ),

    "KPF" : Instrument(
        name="KPF",
        observatory=KECK_OBSERVATORY,
        telescope_diameter=10.0,
        resolution=98000,
        rv_estimation=None,
    ),

    "CARMENES-VIS": Instrument(
            name="CARMENES-VIS",
            observatory=CALAR_ALTO,
            resolution=94600,
            telescope_diameter=3.25,
            rv_estimation=None,
        ),

    "NIRPS-HA": Instrument(
            name="NIRPS-HA",
            observatory=LA_SILLA,
            resolution=75000,
            telescope_diameter=3.6,
            rv_estimation=None,
        ),

    "NIRPS-HE": Instrument(
        name="NIRPS-HE",
        observatory=LA_SILLA,
        resolution=100000,
        telescope_diameter=3.6,
        rv_estimation=None,
    ),

}
