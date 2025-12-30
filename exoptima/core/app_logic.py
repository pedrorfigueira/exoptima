import numpy as np

import astropy.units as u
from astropy.time import Time
from astropy.coordinates import SkyCoord, get_moon

from astroplan.moon import moon_illumination

from exoptima.config.layout import DAYTIME_INTERVAL, DAY_OBS_NSAMPLES
from exoptima.core.state import AppState
app_state = AppState()
from exoptima.core.state import ObservabilityResult


def recompute_observability(app_state: AppState) -> ObservabilityResult | None:
    if (
        app_state.star is None
        or app_state.instrument is None
        or app_state.conditions is None
    ):
        return None

    observer = app_state.instrument.observatory.to_astroplan_observer()

    target = SkyCoord(
        app_state.star.ra,
        app_state.star.dec,
        unit=(u.hourangle, u.deg),
    )

    # Timestamp se for observability
    tstamp = app_state.reference_time or Time.now()

    # Night logic (as before)
    if observer.is_night(tstamp):
        sunset = observer.sun_set_time(tstamp, which="previous")
        sunrise = observer.sun_rise_time(tstamp, which="next")
    else:
        sunset = observer.sun_set_time(tstamp, which="next")
        sunrise = observer.sun_rise_time(sunset, which="next")

    t_start = sunset - DAYTIME_INTERVAL
    t_end = sunrise + DAYTIME_INTERVAL

    times = t_start + np.linspace(
        0,
        (t_end - t_start).to(u.hour).value,
        DAY_OBS_NSAMPLES,
    ) * u.hour

    altaz = observer.altaz(times, target)
    altitude = altaz.alt.to(u.deg)

    min_altitude = np.arcsin(1.0 / app_state.conditions.max_airmass) * u.rad

    # Moon separation and illumination
    moon = get_moon(times, observer.location)
    moon_sep = target.separation(moon)
    fli = moon_illumination(times)

    moon_sep_mask = moon_sep >= app_state.conditions.min_moon_separation * u.deg

    if app_state.conditions.ignore_moon_if_fli_above < 1.0:
        moon_fli_mask = fli <= app_state.conditions.ignore_moon_if_fli_above
        moon_mask = moon_sep_mask | ~moon_fli_mask
    else:
        moon_mask = moon_sep_mask

    # mask including both altitude/mask and moon constraints
    mask = (
            (altitude >= min_altitude)
            & moon_mask
            & np.isfinite(altitude)
    )

    dt = (times[1] - times[0]).to(u.minute)
    observable_time = mask.sum() * dt

    # min duration condition
    meets_min_duration = observable_time >= app_state.conditions.min_duration
    is_observable = bool(meets_min_duration)

    night_duration = (sunrise - sunset).to(u.hour)

    min_airmass = np.nanmin(1.0 / np.sin(altitude[mask].to_value(u.rad)))
    min_moon_sep = moon_sep[mask].min().to_value(u.deg)
    mean_fli = np.mean(fli[mask])

    result = ObservabilityResult(
        time_grid=times,
        altitude=altitude,
        mask=mask,
        observable_time=observable_time,
        sunset=sunset,
        sunrise=sunrise,
        night_duration=night_duration,
        is_observable=is_observable,
        min_airmass=min_airmass,
        min_moon_sep=min_moon_sep,
        mean_fli=mean_fli
    )

    app_state.observability = result
    return result



def recompute_precision(app_state):
    if app_state.star is None or app_state.instrument is None:
        return None

    return print("TBD")