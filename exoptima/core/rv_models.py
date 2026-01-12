# RV models

import numpy as np
from astropy import units as u
from astropy.constants import G

from exoptima.core.precision import compute_rv_precision

def compute_rv_semi_amplitude(
    *,
    planet_mass_mjup: float,
    orbital_period_days: float,
    stellar_mass_msun: float,
    sin_i: float,
    eccentricity: float,
) -> float:
    """
    Compute RV semi-amplitude K in m/s.

    Parameters
    ----------
    planet_mass_mjup : float
    orbital_period_days : float
    stellar_mass_msun : float
    sin_i : float
        sin(inclination)
    eccentricity : float

    Returns
    -------
    float
        Semi-amplitude in m/s
    """

    Mp = planet_mass_mjup * u.M_jup
    Mstar = stellar_mass_msun * u.M_sun
    P = orbital_period_days * u.day

    factor = (2 * np.pi * G / P) ** (1 / 3)
    K = factor * (Mp * sin_i) / (Mstar ** (2 / 3)) / np.sqrt(1 - eccentricity ** 2)

    return K.to(u.m / u.s).value

def compute_rv_amplitudes_two_cases(
    *,
    planet_mass_mjup: float,
    orbital_period_days: float,
    stellar_mass_msun: float,
) -> dict:
    """
    Compute RV semi-amplitude for optimistic and realistic cases.
    """

    # Optimistic
    K_opt = compute_rv_semi_amplitude(
        planet_mass_mjup=planet_mass_mjup,
        orbital_period_days=orbital_period_days,
        stellar_mass_msun=stellar_mass_msun,
        sin_i=1.0,
        eccentricity=0.0,
    )

    # Realistic
    sin_i_mean = np.pi / 4.0   # ≈ 0.785
    e_median = 0.2

    K_real = compute_rv_semi_amplitude(
        planet_mass_mjup=planet_mass_mjup,
        orbital_period_days=orbital_period_days,
        stellar_mass_msun=stellar_mass_msun,
        sin_i=sin_i_mean,
        eccentricity=e_median,
    )

    return {
        "optimistic": K_opt,
        "realistic": K_real,
    }

def compute_detection_significance_curve(
    *,
    exposure_times: np.ndarray,   # seconds
    instrument,
    spectral_type: str,
    vmag: float,
    K_value: float | None,
) -> np.ndarray | None:
    """
    Compute detection significance curve: K / sigma(t)

    Returns array of significance values, or None if not computable.
    """

    if K_value is None:
        return None

    sig_vals = []

    for t in exposure_times:
        res = compute_rv_precision(
            instrument=instrument,
            spectral_type=spectral_type,
            vmag=vmag,
            exposure_time=t,
        )

        if res is None:
            sig_vals.append(np.nan)
            continue

        sigma = res.get("rv_precision")

        if sigma is None or not np.isfinite(sigma) or sigma <= 0:
            sig_vals.append(np.nan)
            continue

        sig_vals.append(K_value / sigma)

    sig_vals = np.array(sig_vals)

    if not np.any(np.isfinite(sig_vals)):
        return None

    return sig_vals

