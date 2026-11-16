from copy import deepcopy
from datetime import timezone
from zoneinfo import ZoneInfo

from astropy import units as u
from astropy.time import Time

from exoptima.config.instruments import INSTRUMENTS, get_instrument_overheads

from exoptima.scheduling.obs_helpers import get_scheduling_night_boundaries, calculate_target_observability


# ------------------------------------------------------------------
# Fields retained from the Planning input
# ------------------------------------------------------------------

TARGET_FIELDS = {
    "star_name",
    "ra",
    "dec",
    "vmag",
    "exposure_time",
}

CONSTRAINT_FIELDS = {
    "max_airmass",
    "min_duration_hours",
    "min_moon_separation",
    "ignore_moon_if_fli_below",
    "night_definition",
}


# ------------------------------------------------------------------
# Night calculation
# ------------------------------------------------------------------

def calculate_night(data, observatory_longitude_deg):
    """Calculate the local calendar date after applying the time offset.

    Parameters
    ----------
    data : dict
        Complete Planning JSON document.
    observatory_longitude_deg : float
        Longitude of the instrument's observatory, in degrees.

    Returns
    -------
    str
        Local calendar date in ISO format (YYYY-MM-DD).
    """

    reference_time = Time(
        data["reference_time_utc"],
        format="isot",
        scale="utc",
    )

    inputs = data["inputs"]

    offset = inputs["time_offset"]
    unit = inputs["time_offset_unit"]

    delta = {
        "day": offset * u.day,
        "week": offset * u.week,
        "month": offset * 30 * u.day,
        "year": offset * 365 * u.day,
    }[unit]

    shifted_time = reference_time + delta

    timezone_name = inputs["timezone"]

    if timezone_name == "Local Time of Observatory":
        # Follow the same fixed-offset approximation as Planning.
        timezone_name = "Etc/GMT%+d" % int(
            round(-observatory_longitude_deg / 15)
        )

    dt_utc = shifted_time.to_datetime().replace(
        tzinfo=timezone.utc
    )

    dt_local = dt_utc.astimezone(
        ZoneInfo(timezone_name)
    )

    return dt_local.date().isoformat()


# ------------------------------------------------------------------
# Transit observing window
# ------------------------------------------------------------------

def calculate_transit_window(inputs, night_start, night_end):
    """Calculate the transit observing window within an observing night.

    The observing window is centred on the predicted mid-transit time
    and clipped to the boundaries of the observing night.

    Parameters
    ----------
    inputs : dict
        Planning input parameters.
    night_start, night_end : astropy.time.Time
        UTC boundaries of the observing night.

    Returns
    -------
    dict
        Dictionary with UTC ISO strings for 'start' and 'end'.
        Both values are None if no transit window is available.
    """

    empty_window = {
        "start": None,
        "end": None,
    }

    if not inputs.get("include_transit_in_observability", False):
        return empty_window

    period = inputs.get("orbital_period_days")
    t0 = inputs.get("t0_jd")
    duration = inputs.get("total_observation_duration_hours")

    if period is None or t0 is None or duration is None:
        return empty_window

    if period <= 0 or duration <= 0:
        return empty_window

    # Mid-transit times are T0 + nP.
    t0 = Time(t0, format="jd", scale="utc")

    # Find the first transit whose observing window could overlap
    # the start of the night.
    half_duration = duration / 2 * u.hour

    n = int(
        (
            (night_start - half_duration - t0).to_value(u.day)
        ) // period
    )

    transit_time = t0 + n * period * u.day

    while transit_time + half_duration < night_start:
        transit_time += period * u.day

    window_start = transit_time - half_duration
    window_end = transit_time + half_duration

    if window_start >= night_end or window_end <= night_start:
        return empty_window

    start = max(window_start, night_start)
    end = min(window_end, night_end)

    return {
        "start": start.utc.isot,
        "end": end.utc.isot,
    }


# ------------------------------------------------------------------
# Target extraction
# ------------------------------------------------------------------

def make_target_entry(data, night_start, night_end):
    """Extract target information from a Planning JSON document.

    Instrument and night are intentionally not stored in the target
    entry: they belong to the queue-level configuration.
    """
    inputs = data["inputs"]

    target = {
        key: inputs[key]
        for key in TARGET_FIELDS
    }

    constraints = {
        key: inputs[key]
        for key in CONSTRAINT_FIELDS
    }

    transit_window = calculate_transit_window(
        inputs,
        night_start,
        night_end,
    )

    return {
        "target": target,
        "constraints": constraints,
        "transit_window": transit_window,
        "include_transit": inputs.get(
            "include_transit_in_observability",
            False,
        ),
        "priority": 1,
    }

def add_observability(entry, night_start, night_end, instrument):
    """Calculate and attach target observability to a queue entry."""

    target = entry["target"]
    constraints = entry["constraints"]
    transit_window = entry["transit_window"] if entry["include_transit"] else None

    entry["observability"] = calculate_target_observability(
        ra=target["ra"],
        dec=target["dec"],
        start=night_start,
        end=night_end,
        instrument=instrument,
        max_airmass=constraints["max_airmass"],
        min_moon_separation=constraints["min_moon_separation"],
        ignore_moon_if_fli_below=constraints["ignore_moon_if_fli_below"],
        min_duration_hours=constraints["min_duration_hours"],
        transit_window=transit_window,
    )

    return entry


def calculate_queue_observability(
    queue,
    night,
    instrument,
    night_definition=None,
    observing_period="Full night",
    custom_start_hours=0.0,
    custom_duration_hours=1.0,
):
    """Calculate observability over the selected portion of the night."""

    if night_definition is None:
        night_definition = queue[0]["constraints"]["night_definition"]

    night_start, night_end = get_scheduling_night_boundaries(
        night,
        night_definition,
        instrument,
    )

    full_duration = (night_end - night_start).to_value(u.hour)

    if observing_period == "First half":
        night_end = night_start + (full_duration / 2) * u.hour
    elif observing_period == "Second half":
        night_start = night_start + (full_duration / 2) * u.hour
    elif observing_period == "Custom":
        if custom_start_hours < 0 or custom_duration_hours <= 0:
            raise ValueError(
                "Custom observing period requires a non-negative starting offset "
                "and a positive duration."
            )
        full_night_start = night_start
        full_night_end = night_end
        night_start = min(
            full_night_start + custom_start_hours * u.hour,
            full_night_end,
        )
        night_end = min(
            night_start + custom_duration_hours * u.hour,
            full_night_end,
        )

    calculated_queue = []

    for source_entry in queue:
        entry = deepcopy(source_entry)
        entry = add_observability(
            entry,
            night_start,
            night_end,
            instrument,
        )
        calculated_queue.append(entry)

    return calculated_queue


# ------------------------------------------------------------------
# Common parameters
# ------------------------------------------------------------------

def update_common_parameters(current, constraints):
    """Keep only parameters with identical values for all targets."""

    if current is None:
        return deepcopy(constraints)

    return {
        key: value
        for key, value in current.items()
        if key in constraints and constraints[key] == value
    }


# ------------------------------------------------------------------
# Target manipulation
# ------------------------------------------------------------------

def add_target(app_state, data):
    """Validate and add a target from a Planning JSON document."""

    # Validate the basic document structure.
    if data.get("format_version") != 1:
        return "Unsupported or missing target file format version"

    if "reference_time_utc" not in data or "inputs" not in data:
        return "Invalid target file: missing required sections"

    inputs = data["inputs"]

    required_fields = (
        TARGET_FIELDS
        | CONSTRAINT_FIELDS
        | {
            "instrument",
            "timezone",
            "time_offset",
            "time_offset_unit",
        }
    )

    missing = required_fields - inputs.keys()
    if missing:
        return "Invalid target file: missing fields " + ", ".join(sorted(missing))

    instrument_name = inputs["instrument"]

    if instrument_name not in INSTRUMENTS:
        return f"Unknown instrument: {instrument_name}"

    instrument = INSTRUMENTS[instrument_name]

    # Determine the candidate observing night.
    candidate_night = calculate_night(data, instrument.observatory.longitude_deg)

    # Validate against the existing queue.
    if app_state.queue:

        if instrument_name != app_state.queue_config["instrument"]:
            return "Instrument not matching."

        queue_night_definition = app_state.common_parameters["night_definition"]

        if inputs["night_definition"] != queue_night_definition:
            return (
                f"Night definition not matching. "
                f"All targets must use '{queue_night_definition}'."
            )

        effective_night = app_state.queue_config["night"]
        first_target = False

        if candidate_night != effective_night:
            status = (
                "Night not matching — target assigned to queue night."
            )
        else:
            status = "Target loaded."

    else:
        effective_night = candidate_night
        first_target = True
        status = "Target loaded."

    # Calculate night boundaries.
    night_start, night_end = get_scheduling_night_boundaries(
        effective_night,
        inputs["night_definition"],
        instrument,
    )

    # Extract target information and calculate its transit window.
    entry = make_target_entry(data, night_start, night_end)

    # Prepare the candidate queue.
    candidate_queue = [*app_state.queue, entry]

    # Calculate observability for the entire candidate queue.
    # This also refreshes any previously loaded targets.
    calculated_queue = calculate_queue_observability(
        candidate_queue,
        effective_night,
        instrument,
        night_definition=(
            inputs["night_definition"]
            if first_target
            else app_state.night_definition
        ),
        observing_period=(
            "Full night"
            if first_target
            else app_state.observing_period
        ),
        custom_start_hours=app_state.custom_start_hours,
        custom_duration_hours=app_state.custom_duration_hours,
    )

    # Prepare queue configuration if this is the first target.
    if first_target:
        queue_config = {
            "instrument": instrument_name,
            "night": effective_night,
            "overheads": get_instrument_overheads(instrument_name),
        }

    # Commit changes to application state.
    if first_target:
        app_state.queue_config = queue_config
        app_state.instrument = instrument_name
        app_state.night = effective_night
        app_state.night_definition = inputs["night_definition"]
        app_state.observing_period = "Full night"
        app_state.custom_start_hours = 0.0
        app_state.custom_duration_hours = 1.0

    app_state.queue = candidate_queue
    app_state.calculated_queue = calculated_queue

    app_state.common_parameters = update_common_parameters(
        app_state.common_parameters,
        entry["constraints"],
    )

    app_state.needs_recalculation = False

    return status


def set_target_priority(app_state, index, priority):
    """Set the scheduling priority of a queue target."""

    entry = deepcopy(app_state.queue[index])
    entry["priority"] = priority

    queue = list(app_state.queue)
    queue[index] = entry
    app_state.queue = queue

    app_state.needs_recalculation = True


def update_target_constraint(app_state, index, key, value):
    """Update an individual constraint without recalculating observability."""

    if key == "night_definition":
        current = app_state.common_parameters["night_definition"]

        if value != current:
            raise ValueError(
                f"Night definition is a queue-level parameter. "
                f"All targets must use '{current}'."
            )

        return

    entry = deepcopy(app_state.queue[index])
    entry["constraints"][key] = value

    queue = list(app_state.queue)
    queue[index] = entry
    app_state.queue = queue

    # Recalculate parameters common to all targets.
    common = None
    for target_entry in queue:
        common = update_common_parameters(
            common,
            target_entry["constraints"],
        )

    app_state.common_parameters = common
    app_state.needs_recalculation = True


# ------------------------------------------------------------------
# Queue management
# ------------------------------------------------------------------

def get_queue_target_labels(queue):
    """Return display labels, numbering repeated targets as position/total."""

    names = [
        entry["target"]["star_name"].strip()
        for entry in queue
    ]

    counts = {}
    for name in names:
        key = name.casefold()
        counts[key] = counts.get(key, 0) + 1

    indices = {}

    labels = []

    for name in names:
        key = name.casefold()

        if counts[key] > 1:
            indices[key] = indices.get(key, 0) + 1
            labels.append(f"{name} ({indices[key]}/{counts[key]})")
        else:
            labels.append(name)

    return labels

def clear_queue(app_state):
    """Reset the queue and its associated configuration."""

    app_state.queue = []
    app_state.queue_config = {}
    app_state.calculated_queue = []
    app_state.needs_recalculation = False

    app_state.common_parameters = None

    app_state.instrument = None
    app_state.telescope = None
    app_state.night = None
    app_state.night_definition = None
    app_state.observing_period = "Full night"
    app_state.custom_start_hours = 0.0
    app_state.custom_duration_hours = 1.0
    app_state.selected_target = None


def recalculate_queue(app_state):
    """Recalculate observability and scheduling for the current queue."""

    if not app_state.queue:
        app_state.calculated_queue = []
        app_state.needs_recalculation = False
        return

    instrument = INSTRUMENTS[app_state.queue_config["instrument"]]

    calculated_queue = calculate_queue_observability(
        app_state.queue,
        app_state.night,
        instrument,
        night_definition=app_state.night_definition,
        observing_period=app_state.observing_period,
        custom_start_hours=app_state.custom_start_hours,
        custom_duration_hours=app_state.custom_duration_hours,
    )

    app_state.calculated_queue = calculated_queue
    app_state.needs_recalculation = False