# precision calculation tools

import math
import numpy as np

from typing import Optional, Dict

from astropy import units as u
from astropy.constants import G

from exoptima.config.instruments import Instrument, INSTRUMENTS

def recompute_precision(app_state):
    star = app_state.star
    inst = app_state.instrument
    pp = app_state.planet_params
    t_req = app_state.exposure_time

    if star is None or inst is None:
        app_state.precision_result = None
        return None

    if star.vmag is None or star.sptype is None:
        app_state.precision_result = None
        return None

    # --------------------------------------------------
    # 1. Time grid definition
    # --------------------------------------------------
    if t_req < 15 * 60:
        t_min = 60
        t_max = 30 * 60
    elif t_req < 30 * 60:
        t_min = 60
        t_max = 60 * 60
    else:
        t_min = 60
        t_max = 3.0 * t_req

    times = np.linspace(t_min, t_max, 60)

    # --------------------------------------------------
    # 2. SNR and RV curves
    # --------------------------------------------------
    snr_vals = []
    rv_vals = []

    for t in times:
        r = compute_rv_precision(
            instrument=inst,
            spectral_type=star.sptype,
            vmag=star.vmag,
            exposure_time=t,
        )
        if r is None:
            snr_vals.append(np.nan)
            rv_vals.append(np.nan)
        else:
            snr_vals.append(r["snr"])
            rv_vals.append(r["rv_precision"])

    snr_vals = np.array(snr_vals)
    rv_vals = np.array(rv_vals)

    # --------------------------------------------------
    # 3. Requested point
    # --------------------------------------------------
    req = compute_rv_precision(
        instrument=inst,
        spectral_type=star.sptype,
        vmag=star.vmag,
        exposure_time=t_req,
    )

    if req is None:
        app_state.precision_result = None
        return None

    # --------------------------------------------------
    # 4. Planet RV amplitudes
    # --------------------------------------------------
    K_cases = None
    if (
        pp is not None
        and pp.planet_mass_mjup is not None
        and pp.orbital_period_days is not None
    ):
        K_cases = compute_rv_amplitudes_two_cases(
            planet_mass_mjup=pp.planet_mass_mjup,
            orbital_period_days=pp.orbital_period_days,
            stellar_mass_msun=pp.stellar_mass_msun,
        )

    # --------------------------------------------------
    # 5. Detectability curves
    # --------------------------------------------------
    detectability = None
    if K_cases is not None:
        sig_opt = compute_detection_significance_curve(
            exposure_times=times,
            instrument=inst,
            spectral_type=star.sptype,
            vmag=star.vmag,
            K_value=K_cases["optimistic"],
        )

        sig_real = compute_detection_significance_curve(
            exposure_times=times,
            instrument=inst,
            spectral_type=star.sptype,
            vmag=star.vmag,
            K_value=K_cases["realistic"],
        )

        detectability = {
            "optimistic": sig_opt,
            "realistic": sig_real,
        }

    # --------------------------------------------------
    # 6. Store everything in state
    # --------------------------------------------------
    app_state.precision_result = {
        "times": times,
        "snr_curve": snr_vals,
        "rv_curve": rv_vals,
        "requested": req,
        "K_cases": K_cases,
        "detectability": detectability,
    }

    return app_state.precision_result


def compute_rv_precision(
    *,
    instrument: Instrument,
    spectral_type: str,
    vmag: float,
    exposure_time: float,  # seconds
) -> Optional[Dict]:
    """
    Compute RV precision and SNR.

    If the instrument has its own RVEstimation model, use it directly.
    Otherwise, scale from ESPRESSO using:
      - SNR ∝ D * sqrt(t) * 10^{-0.2 Δmag}
      - RV ∝ (1/SNR) * R^{-1.5}

    Returns:
        {
            "snr": float,
            "rv_precision": float,   # m/s
            "snr_ref": float,
            "rv_ref": float,
            "scaled_from": str,
        }
    or None if not computable.
    """

    # --------------------------------------------------
    # Select base model
    # --------------------------------------------------

    if instrument.rv_estimation is not None:
        model = instrument.rv_estimation
        base_instrument = instrument
    else:
        # Fallback to ESPRESSO
        espresso = INSTRUMENTS.get("ESPRESSO")
        if espresso is None or espresso.rv_estimation is None:
            return None

        model = espresso.rv_estimation
        base_instrument = espresso

    # --------------------------------------------------
    # Fetch reference values
    # --------------------------------------------------

    snr_ref = model.ref_snr.get(spectral_type)
    rv_ref = model.ref_rv_precision.get(spectral_type)

    if snr_ref is None or rv_ref is None:
        return None

    t_ref = model.ref_exptime
    m_ref = model.ref_mag
    R_ref = base_instrument.resolution
    D_ref = base_instrument.telescope_diameter

    # --------------------------------------------------
    # Target instrument properties
    # --------------------------------------------------

    D = instrument.telescope_diameter
    R = instrument.resolution

    # --------------------------------------------------
    # SNR scaling
    # --------------------------------------------------

    time_factor = math.sqrt(exposure_time / t_ref)
    mag_factor = 10.0 ** (-0.2 * (vmag - m_ref))
    diameter_factor = D / D_ref

    snr = snr_ref * diameter_factor * time_factor * mag_factor

    if snr <= 0.0:
        return None

    # --------------------------------------------------
    # RV scaling
    # --------------------------------------------------

    resolution_factor = (R_ref / R) ** 1.5
    rv = rv_ref * (snr_ref / snr) * resolution_factor

    # --------------------------------------------------
    # Output
    # --------------------------------------------------

    return {
        "snr": snr,
        "rv_precision": rv,
        "snr_ref": snr_ref,
        "rv_ref": rv_ref,
        "scaled_from": base_instrument.name,
    }


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

