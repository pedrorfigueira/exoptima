"""Target observability calculations for Scheduling."""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import numpy as np
import astropy.units as u

from astroplan import FixedTarget
from astropy.coordinates import SkyCoord
from astropy.time import Time

from exoptima.config.computation import OBSERVABILITY_CADENCE_MINUTES
from exoptima.core.observability import (
    get_night_boundaries,
    calculate_observing_conditions,
    filter_short_observing_windows,
)


def _observatory_timezone(instrument):
    """Return the fixed-offset timezone used by Planning."""
    longitude = instrument.observatory.longitude_deg
    return "Etc/GMT%+d" % int(round(-longitude / 15))


def get_scheduling_night_boundaries(
    night,
    night_definition,
    instrument,
):
    """Calculate night boundaries for a local observing date."""

    local_noon = datetime.combine(
        datetime.strptime(night, "%Y-%m-%d").date(),
        time(12, 0),
        tzinfo=ZoneInfo(_observatory_timezone(instrument)),
    )

    reference_time = Time(local_noon.astimezone(timezone.utc))

    observer = instrument.observatory.to_astroplan_observer()

    return get_night_boundaries(
        observer=observer,
        ref_time=reference_time,
        night_definition=night_definition,
    )

def _format_observing_windows(times, mask):
    """Convert a Boolean mask into a list of continuous observing windows."""

    windows = []
    indices = np.flatnonzero(mask)

    if len(indices) == 0:
        return windows

    groups = np.split(
        indices,
        np.where(np.diff(indices) > 1)[0] + 1,
    )

    for group in groups:
        start = times[group[0]]
        end = times[group[-1]]
        duration = end - start

        windows.append({
            "start": start.utc.isot,
            "end": end.utc.isot,
            "duration_hours": duration.to_value(u.hour),
        })

    return windows


def calculate_target_observability(
    ra,
    dec,
    start,
    end,
    instrument,
    max_airmass=2.0,
    min_moon_separation=30.0,
    ignore_moon_if_fli_below=None,
    min_duration_hours=0.0,
    transit_window=None,
    cadence_minutes=OBSERVABILITY_CADENCE_MINUTES,
):
    """
    Calculate target observability throughout an observing night.

    Parameters
    ----------
    ra, dec : str or float
        Target coordinates. RA is interpreted as hour angle if supplied
        as a string; Dec is interpreted as degrees.
    start, end : astropy.time.Time
        UTC boundaries of the observing night.
    instrument : Instrument
        Instrument configuration.
    max_airmass : float
        Maximum permitted airmass.
    min_moon_separation : float
        Minimum angular separation from the Moon, in degrees.
    ignore_moon_if_fli_below : float or None
        Ignore the Moon-separation constraint when the fractional lunar
        illumination is below this threshold.
    min_duration_hours : float
        Minimum duration of a continuous observing window, in hours.
    transit_window : dict or None
        Optional dictionary with UTC ISO strings 'start' and 'end'.
        If supplied, observability is restricted to this interval.
    cadence_minutes : float
        Sampling cadence, in minutes.

    Returns
    -------
    dict
        Sampled conditions, Boolean observability masks, and continuous
        observing windows.
    """
    if cadence_minutes <= 0:
        raise ValueError("cadence_minutes must be positive")

    if end <= start:
        raise ValueError("The observing-night end must be after its start")

    if max_airmass <= 0:
        raise ValueError("max_airmass must be positive")

    if min_duration_hours < 0:
        raise ValueError("min_duration_hours cannot be negative")

    observer = instrument.observatory.to_astroplan_observer()

    target = FixedTarget(
        coord=SkyCoord(ra, dec, unit=(u.hourangle, u.deg))
    )

    # Generate a time grid and include the exact end of the night.
    duration_minutes = (end - start).to_value(u.min)

    offsets = np.arange(
        0,
        duration_minutes,
        cadence_minutes,
    ) * u.min

    times = start + offsets

    if len(times) == 0 or times[-1] < end:
        times = Time(
            np.append(times.jd, end.jd),
            format="jd",
            scale="utc",
        )

    observing_conditions = calculate_observing_conditions(
        observer=observer,
        target=target.coord,
        times=times,
        instrument=instrument,
        max_airmass=max_airmass,
        min_moon_separation=min_moon_separation,
        ignore_moon_if_fli_below=ignore_moon_if_fli_below,
    )

    altitude = observing_conditions["altitude"]
    airmass = observing_conditions["airmass"]
    moon_separation = observing_conditions["moon_separation"]
    fli = observing_conditions["fli"]

    above_horizon = observing_conditions["above_horizon"]
    airmass_ok = observing_conditions["airmass_ok"]
    moon_ok = observing_conditions["moon_ok"]
    zenith_ok = observing_conditions["zenith_ok"]

    observable = (
            airmass_ok
            & moon_ok
            & zenith_ok
    )

    # If a transit window is supplied, restrict observability to it.
    transit_mask = np.ones(len(times), dtype=bool)

    if transit_window is not None:

        transit_start = transit_window.get("start")
        transit_end = transit_window.get("end")

        if transit_start is None or transit_end is None:
            transit_mask[:] = False

        else:
            transit_start = Time(
                transit_start,
                format="isot",
                scale="utc",
            )

            transit_end = Time(
                transit_end,
                format="isot",
                scale="utc",
            )

            transit_mask = (
                    (times >= transit_start)
                    & (times <= transit_end)
            )

        observable &= transit_mask

    # Apply the shared minimum-duration criterion to each continuous window.
    accepted_mask, _ = filter_short_observing_windows(
        times,
        observable,
        min_duration_hours * u.hour,
    )

    # Format the accepted windows for the Scheduling output.
    windows = _format_observing_windows(times, accepted_mask)

    return {
        "times": times.utc.isot.tolist(),
        "altitude": altitude.tolist(),
        "airmass": airmass.tolist(),
        "moon_separation": moon_separation.tolist(),
        "fli": fli.tolist(),
        "above_horizon": above_horizon.tolist(),
        "airmass_ok": airmass_ok.tolist(),
        "moon_ok": moon_ok.tolist(),
        "zenith_ok": zenith_ok.tolist(),
        "transit_ok": transit_mask.tolist(),
        "observable": accepted_mask.tolist(),
        "windows": windows,
    }