# precision calculation tools

import math
import numpy as np

from typing import Optional, Dict

from astropy import units as u
from astropy.constants import G

from exoptima.config.instruments import Instrument, INSTRUMENTS

# --------------------------------------------------
# Throughput models
# --------------------------------------------------

def fiber_encircled_energy(
    seeing_fwhm_arcsec: float,
    fiber_diameter_arcsec: float,
) -> float:
    """
    Fraction of light entering a centered circular fiber
    assuming a Gaussian PSF.
    """
    if seeing_fwhm_arcsec <= 0 or fiber_diameter_arcsec <= 0:
        return 1.0

    sigma = seeing_fwhm_arcsec / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    radius = fiber_diameter_arcsec / 2.0

    return 1.0 - np.exp(-(radius**2) / (2.0 * sigma**2))


def extinction_coeff_from_wavelength(wavelength_um: float) -> float:
    """
    Approximate broadband atmospheric extinction coefficient [per airmass]
    as a function of representative wavelength.

    Values are rough, site-agnostic, and intended for first-order exposure/SNR scaling.
    """

    # Tabulated anchor points: (wavelength [um], extinction coefficient [airmass^-1])
    wl_grid = np.array([0.40, 0.55, 0.70, 0.90, 1.10, 1.25, 1.65])
    k_grid  = np.array([0.22, 0.12, 0.08, 0.06, 0.05, 0.06, 0.05])

    # Clamp outside range
    wavelength_um = np.clip(wavelength_um, wl_grid.min(), wl_grid.max())

    return float(np.interp(wavelength_um, wl_grid, k_grid))


def airmass_transmission(airmass: float, extinction_coeff: float) -> float:
    """
    Atmospheric transmission loss relative to zenith.

    Parameters
    ----------
    airmass : float
    extinction_coeff : float
        Broadband extinction coefficient in mag / airmass

    Returns
    -------
    float
        Relative transmission factor
    """
    if airmass <= 1.0:
        return 1.0

    return 10.0 ** (-0.4 * extinction_coeff * (airmass - 1.0))


def seeing_at_wavelength(
    seeing_ref_arcsec: float,
    wavelength_um: float,
    reference_wavelength_um: float = 0.55,
) -> float:
    """
    Scale seeing from a reference wavelength using Kolmogorov turbulence:

        seeing ∝ λ^(-1/5)

    Parameters
    ----------
    seeing_ref_arcsec : float
        Seeing at reference wavelength (typically 0.55 µm)
    wavelength_um : float
        Instrument central wavelength
    reference_wavelength_um : float
        Reference wavelength of input seeing

    Returns
    -------
    float
        Effective seeing at the instrument wavelength
    """
    if seeing_ref_arcsec <= 0:
        return seeing_ref_arcsec

    return seeing_ref_arcsec * (wavelength_um / reference_wavelength_um) ** (-0.2)


def throughput_factor(
    *,
    instrument,
    airmass: float | None,
    seeing_ref_arcsec: float | None,
) -> tuple[float, float | None, float | None, float | None]:
    """
    Compute total throughput factor = atmospheric transmission × fiber coupling.

    Parameters
    ----------
    instrument : Instrument
    airmass : float or None
    seeing_ref_arcsec : float or None
        Seeing defined at 0.55 µm.

    Returns
    -------
    throughput, T_airmass, T_fiber, seeing_eff
    """
    T_airmass = 1.0
    T_fiber = 1.0
    seeing_eff = None

    # Airmass term
    if airmass is not None:
        k_ext = extinction_coeff_from_wavelength(instrument.central_wavelength_um)
        T_airmass = airmass_transmission(airmass, k_ext)

    # Fiber term
    fiber_diam = getattr(instrument, "fiber_diameter_arcsec", None)
    if fiber_diam is not None and seeing_ref_arcsec is not None:
        seeing_eff = seeing_at_wavelength(
            seeing_ref_arcsec=seeing_ref_arcsec,
            wavelength_um=instrument.central_wavelength_um,
        )
        T_fiber = fiber_encircled_energy(seeing_eff, fiber_diam)

    throughput = max(T_airmass * T_fiber, 1e-6)

    return throughput, T_airmass, T_fiber, seeing_eff


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
            conditions=app_state.conditions,
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
        conditions=app_state.conditions,
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
            conditions=app_state.conditions,
        )

        sig_real = compute_detection_significance_curve(
            exposure_times=times,
            instrument=inst,
            spectral_type=star.sptype,
            vmag=star.vmag,
            K_value=K_cases["realistic"],
            conditions=app_state.conditions,
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
    conditions=None,
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

    # Base SNR (no losses)
    snr = snr_ref * diameter_factor * time_factor * mag_factor

    # --------------------------------------------------
    # Throughput corrections (relative to reference conditions)
    # --------------------------------------------------

    k_ext = extinction_coeff_from_wavelength(instrument.central_wavelength_um)

    # User conditions
    user_airmass = getattr(conditions, "airmass_rv", None) if conditions is not None else None
    user_seeing = getattr(conditions, "seeing_arcsec", None) if conditions is not None else None

    throughput_user, T_airmass, T_fiber, seeing_eff = throughput_factor(
        instrument=instrument,
        airmass=user_airmass,
        seeing_ref_arcsec=user_seeing,
    )

    # Reference conditions
    ref_airmass = model.ref_airmass
    ref_seeing = model.ref_seeing_arcsec

    throughput_ref, T_airmass_ref, T_fiber_ref, seeing_eff_ref = throughput_factor(
        instrument=base_instrument,
        airmass=ref_airmass,
        seeing_ref_arcsec=ref_seeing,
    )

    # Relative correction only
    throughput_ratio = throughput_user / max(throughput_ref, 1e-6)

    # Apply to SNR (sqrt law)
    snr *= math.sqrt(throughput_ratio)

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
        "throughput": throughput_user,
        "throughput_ref": throughput_ref,
        "throughput_ratio": throughput_ratio,
        "airmass_transmission": T_airmass,
        "fiber_coupling": T_fiber,
        "airmass_transmission_ref": T_airmass_ref,
        "fiber_coupling_ref": T_fiber_ref,
        "extinction_coeff": k_ext,
        "seeing_eff": seeing_eff,
        "seeing_eff_ref": seeing_eff_ref,
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
    conditions=None,
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
            conditions=conditions,
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
