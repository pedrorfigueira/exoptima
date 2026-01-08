# precision calculation tools

import math
from typing import Optional, Dict

from exoptima.config.instruments import Instrument, INSTRUMENTS, RVEstimation

def recompute_precision(app_state):
    if app_state.star is None or app_state.instrument is None:
        return None

    star = app_state.star
    inst = app_state.instrument

    if star.vmag is None or star.sptype is None:
        return None

    result = compute_rv_precision(
        instrument=inst,
        spectral_type=star.sptype,
        vmag=star.vmag,
        exposure_time=app_state.exposure_time,
    )

    app_state.precision_result = result

    print("Precision computed on:", id(app_state))
    print("result:", result)
    return result

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

