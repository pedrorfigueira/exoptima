# observability computation tools

import numpy as np
from typing import Iterable
from datetime import datetime, timedelta, date

import astropy.units as u
from astropy.time import Time
from astropy.coordinates import SkyCoord, get_moon
from astroplan.moon import moon_illumination

from exoptima.config.computation import YEAR_OBS_NIGHTSTEP
from exoptima.config.layout import DAYTIME_INTERVAL, DAY_OBS_NSAMPLES
from exoptima.core.state import (
    AppState,
    ObservabilityResult,
    NightObservability,
    MultiNightObservability,
    PlanetParameters,
)

########################################################################################################################
# Transit helper
########################################################################################################################

def _has_transit_in_window(
    *,
    t0_jd: float,
    period_days: float,
    window_start: Time,
    window_end: Time,
) -> bool:
    """
    Return True if at least one transit midpoint falls within [window_start, window_end].
    """

    t0 = Time(t0_jd, format="jd", scale="utc")
    P = period_days

    n_min = np.floor((window_start.jd - t0.jd) / P)
    n_max = np.ceil((window_end.jd - t0.jd) / P)

    ns = np.arange(n_min, n_max + 1, dtype=int)
    transit_times = t0.jd + ns * P

    return np.any(
        (transit_times >= window_start.jd) & (transit_times <= window_end.jd)
    )


########################################################################################################################
# Core single-night computation
########################################################################################################################

def compute_single_night_observability(
    *,
    observer,
    target,
    ref_time: Time,
    conditions,
    night_definition: str,
    planet_params: PlanetParameters | None = None,
) -> ObservabilityResult:
    """
    Compute observability for a single night centered on ref_time.
    """

    # ----------------------------
    # Night bounds
    # ----------------------------

    def _night_bounds(observer, ref_time, night_def):
        if night_def == "Sunset to sunrise":
            is_night = observer.is_night(ref_time)
            if is_night:
                t_start = observer.sun_set_time(ref_time, which="previous")
                t_end = observer.sun_rise_time(ref_time, which="next")
            else:
                t_start = observer.sun_set_time(ref_time, which="next")
                t_end = observer.sun_rise_time(t_start, which="next")

        elif night_def == "Nautical twilight":
            is_night = observer.is_night(ref_time, horizon=-12 * u.deg)
            if is_night:
                t_start = observer.twilight_evening_nautical(ref_time, which="previous")
                t_end = observer.twilight_morning_nautical(ref_time, which="next")
            else:
                t_start = observer.twilight_evening_nautical(ref_time, which="next")
                t_end = observer.twilight_morning_nautical(t_start, which="next")

        elif night_def == "Astronomical twilight":
            is_night = observer.is_night(ref_time, horizon=-18 * u.deg)
            if is_night:
                t_start = observer.twilight_evening_astronomical(ref_time, which="previous")
                t_end = observer.twilight_morning_astronomical(ref_time, which="next")
            else:
                t_start = observer.twilight_evening_astronomical(ref_time, which="next")
                t_end = observer.twilight_morning_astronomical(t_start, which="next")

        else:
            raise ValueError(f"Unknown night definition: {night_def}")

        return t_start, t_end

    night_start, night_end = _night_bounds(observer, ref_time, night_definition)

    # ----------------------------
    # Time grid
    # ----------------------------

    t_start = night_start - DAYTIME_INTERVAL
    t_end = night_end + DAYTIME_INTERVAL

    times = t_start + np.linspace(
        0,
        (t_end - t_start).to(u.hour).value,
        DAY_OBS_NSAMPLES,
    ) * u.hour

    altaz = observer.altaz(times, target)
    altitude = altaz.alt.to(u.deg)

    min_altitude = np.arcsin(1.0 / conditions.max_airmass) * u.rad

    # ----------------------------
    # Night-time mask
    # ----------------------------

    night_mask = (times >= night_start) & (times <= night_end)

    # ----------------------------
    # Moon constraints
    # ----------------------------

    moon = get_moon(times, observer.location)
    moon_sep = target.separation(moon)
    fli = moon_illumination(times)

    moon_sep_mask = moon_sep >= conditions.min_moon_separation * u.deg

    if conditions.ignore_moon_if_fli_above < 1.0:
        moon_fli_mask = fli <= conditions.ignore_moon_if_fli_above
        moon_mask = moon_sep_mask | ~moon_fli_mask
    else:
        moon_mask = moon_sep_mask

    # ----------------------------
    # Global mask
    # ----------------------------

    mask = (
        night_mask
        & (altitude >= min_altitude)
        & moon_mask
        & np.isfinite(altitude)
    )

    dt = (times[1] - times[0]).to(u.minute)
    observable_time = mask.sum() * dt
    is_observable = observable_time >= conditions.min_duration

    # --------------------------------------------------
    # Transit constraint (optional, PURE)
    # --------------------------------------------------

    if (
        planet_params is not None
        and planet_params.include_transit_in_observability
    ):
        if planet_params.t0_jd is None or planet_params.orbital_period_days is None:
            is_observable = False
            mask[:] = False
            observable_time = 0 * dt
        else:
            has_transit = _has_transit_in_window(
                t0_jd=planet_params.t0_jd,
                period_days=planet_params.orbital_period_days,
                window_start=night_start,
                window_end=night_end,
            )

            if not has_transit:
                is_observable = False
                mask[:] = False
                observable_time = 0 * dt

    # ----------------------------
    # Summary metrics
    # ----------------------------

    min_airmass = (
        np.nanmin(1.0 / np.sin(altitude[mask].to_value(u.rad)))
        if np.any(mask) else np.nan
    )
    min_moon_sep = moon_sep[mask].min().to_value(u.deg) if np.any(mask) else np.nan
    mean_fli = np.mean(fli[mask]) if np.any(mask) else np.nan

    return ObservabilityResult(
        time_grid=times,
        altitude=altitude,
        mask=mask,
        observable_time=observable_time,
        night_start=night_start,
        night_end=night_end,
        night_duration=(night_end - night_start).to(u.hour),
        is_observable=bool(is_observable),
        min_airmass=min_airmass,
        min_moon_sep=min_moon_sep,
        mean_fli=mean_fli,
    )


########################################################################################################################
# Caching / orchestration layer (STATEFUL, NO AppState)
########################################################################################################################

def get_or_compute_night(
    *,
    observer,
    target,
    ref_time: Time,
    conditions,
    night_definition: str,
    planet_params: PlanetParameters | None,
    night_cache: dict[date, NightObservability],
) -> NightObservability:
    """
    Return cached NightObservability if available, otherwise compute and cache it.
    """

    result = compute_single_night_observability(
        observer=observer,
        target=target,
        ref_time=ref_time,
        conditions=conditions,
        night_definition=night_definition,
        planet_params=planet_params,
    )

    night_date = result.night_start.to_datetime().date()

    if night_date not in night_cache:
        night_cache[night_date] = NightObservability(
            date=night_date,
            result=result,
        )

    return night_cache[night_date]


def compute_night_observability(
    *,
    observer,
    target,
    ref_time: Time,
    conditions,
    night_definition: str,
    planet_params: PlanetParameters | None = None,
) -> NightObservability:
    """
    Compute observability for the night associated with ref_time (no cache).
    """

    result = compute_single_night_observability(
        observer=observer,
        target=target,
        ref_time=ref_time,
        conditions=conditions,
        night_definition=night_definition,
        planet_params=planet_params,
    )

    night_date = result.night_start.to_datetime().date()

    return NightObservability(
        date=night_date,
        result=result,
    )


def compute_multi_night_observability(
    *,
    observer,
    target,
    ref_times: Iterable[Time],
    conditions,
    night_definition: str,
    planet_params: PlanetParameters | None,
    night_cache: dict[date, NightObservability],
) -> MultiNightObservability:
    """
    Compute observability for multiple nights, using cache.
    """

    nights: list[NightObservability] = []

    for t_ref in ref_times:
        night_obs = get_or_compute_night(
            observer=observer,
            target=target,
            ref_time=t_ref,
            conditions=conditions,
            night_definition=night_definition,
            planet_params=planet_params,
            night_cache=night_cache,
        )
        nights.append(night_obs)

    return MultiNightObservability(nights=nights)


########################################################################################################################
# AppState drivers (UI orchestration only)
########################################################################################################################

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

    result = compute_single_night_observability(
        observer=observer,
        target=target,
        ref_time=app_state.reference_time,
        conditions=app_state.conditions,
        night_definition=app_state.night_definition,
        planet_params=app_state.planet_params,
    )

    app_state.observability = result
    return result


def recompute_multi_night_observability_driver(
    *,
    app_state: AppState,
    ref_times: Iterable[Time],
) -> MultiNightObservability | None:
    """
    Generic driver for any multi-night observability computation.
    """

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

    return compute_multi_night_observability(
        observer=observer,
        target=target,
        ref_times=ref_times,
        conditions=app_state.conditions,
        night_definition=app_state.night_definition,
        planet_params=app_state.planet_params,
        night_cache=app_state.night_cache,
    )


def recompute_monthly_observability(
    app_state: AppState,
) -> MultiNightObservability | None:

    ref_date = app_state.reference_time.to_datetime().date()

    ref_times = [
        Time(datetime(d.year, d.month, d.day, 12, 0, 0), scale="utc")
        for d in (
            ref_date + timedelta(days=i) for i in range(-15, 16)
        )
    ]

    result = recompute_multi_night_observability_driver(
        app_state=app_state,
        ref_times=ref_times,
    )

    app_state.monthly_observability = result
    return result


def recompute_yearly_observability(
    app_state: AppState,
) -> MultiNightObservability | None:

    def _yearly_reference_times(
        *,
        ref_time: Time,
        step_days: int,
        span_days: int = 365,
    ) -> list[Time]:

        ref_date = ref_time.to_datetime().date()
        half = span_days // 2
        days = range(-half, half + 1, step_days)

        return [
            Time(datetime(d.year, d.month, d.day, 12, 0, 0), scale="utc")
            for d in (ref_date + timedelta(days=i) for i in days)
        ]

    ref_times = _yearly_reference_times(
        ref_time=app_state.reference_time,
        step_days=YEAR_OBS_NIGHTSTEP,
    )

    result = recompute_multi_night_observability_driver(
        app_state=app_state,
        ref_times=ref_times,
    )

    app_state.yearly_observability = result
    return result
