import asyncio
import json
import panel as pn
import numpy as np

from astropy import units as u
from astropy.coordinates import SkyCoord

from exoptima.config.instruments import INSTRUMENTS, get_instrument_overheads
from exoptima.scheduling.obs_helpers import get_scheduling_night_boundaries

from pathlib import Path
from datetime import datetime

from exoptima.config.layout import BUTTON_WIDTH, BUTTON_HEIGHT, FORM_WIDGET_WIDTH, TARGET_FIELD_WIDTH
from exoptima.config.paths import DEFAULT_TARGETS_DIR, DEFAULT_QUEUES_DIR
from exoptima.config.computation import (
    NUMBER_CLASSES_SCHEDULING_PRIORITIES,
    STEP_MAX_AIRMASS, STEP_MIN_DURATION_HOUR,
    STEP_MIN_MOON_SEP, STEP_IGNORE_MOON_FLI,
    OFFSET_HA, DEFAULT_ZENITH_AVOIDANCE_DEG
)

from exoptima.tabs.components import (
    make_divider,
    make_file_io_controls,
    make_section_header,
    mark_section_recalculation_needed,
    format_field,
)

from exoptima.scheduling.targets import (
    add_target,
    set_target_priority,
    update_target_constraint,
    get_queue_target_labels,
    update_common_parameters,
    recalculate_queue,
)

# ------------------------------------------------------------------
# Targets Load
# ------------------------------------------------------------------

def make_target_load_tab(app_state):

    file_io_layout, file_io = make_file_io_controls(
        directory_name="Working directory",
        default_directory=DEFAULT_TARGETS_DIR,
        show_save_button=False,
        show_load_all_button=True,
    )

    # Access to the controls for the loading implementation.
    app_state.target_file_io = file_io

    log_pane = pn.pane.Markdown(
        "No targets loaded yet.",
        sizing_mode="stretch_width",
    )

    log_entries = []

    def update_status(message: str):
        timestamp = datetime.now().astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        log_entries.insert(0, f"- `{timestamp}` — {message}")
        del log_entries[100:]

        log_pane.object = "\n".join(log_entries)

    def clear_history():
        """Clear the log and retain only the clearing action."""
        timestamp = datetime.now().astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        log_entries[:] = [f"- `{timestamp}` — History cleared."]
        log_pane.object = log_entries[0]

    app_state.clear_target_load_history = clear_history

    def load_file(filepath):
        """Load one target file and report the result."""

        if not filepath.is_file():
            update_status(f"❌ File not found: `{filepath}`")
            return False

        queue_size_before = len(app_state.queue)

        try:
            with filepath.open("r", encoding="utf-8") as f:
                data = json.load(f)

            result = add_target(app_state, data)

            if len(app_state.queue) > queue_size_before:
                star_name = data["inputs"]["star_name"]
                update_status(f"✔️ Loaded **{star_name}** from `{filepath.name}`")
                return True

            update_status(f"❌ Could not load `{filepath.name}`: {result}")

        except json.JSONDecodeError as exc:
            update_status(f"❌ Invalid JSON file `{filepath.name}`: {exc}")

        except Exception as exc:
            update_status(f"❌ Error loading `{filepath.name}`: {exc}")

        return False

    def load_selected(event=None):
        filename = file_io["file_name"].value.strip()

        if not filename:
            update_status("❌ Please select a target file.")
            return

        filepath = Path(file_io["working_dir"].value).expanduser() / filename
        load_file(filepath)

    async def load_all(event=None):
        """Load all displayed files sequentially, in their displayed order."""

        load_all_button = file_io["load_all_button"]
        load_all_button.disabled = True

        try:
            directory = Path(file_io["working_dir"].value).expanduser()

            # Use the displayed file buttons to preserve exactly the UI order.
            filenames = [
                widget.name
                for widget in file_io["file_list"].objects
                if isinstance(widget, pn.widgets.Button)
            ]

            if not filenames:
                update_status("❌ No files available to load.")
                return

            update_status(f"Starting bulk load of {len(filenames)} files.")

            loaded = 0
            failed = 0

            for filename in filenames:
                if load_file(directory / filename):
                    loaded += 1
                else:
                    failed += 1

                # Allow Panel to send status updates between files.
                await asyncio.sleep(0.05)

            update_status(
                f"Bulk load finished: **{loaded} loaded**, "
                f"**{failed} failed**, out of {len(filenames)} files."
            )

        finally:
            load_all_button.disabled = not bool(
                [
                    widget for widget in file_io["file_list"].objects
                    if isinstance(widget, pn.widgets.Button)
                ]
            )

    file_io["load_button"].on_click(load_selected)
    file_io["load_all_button"].on_click(load_all)

    return pn.Column(
        file_io_layout,
        pn.pane.HTML(
            "<div style='font-size: 1.2em;'>Load History</div>"
        ),
        pn.Column(
            log_pane,
            height=250,
            scroll=True,
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )

# ------------------------------------------------------------------
# Targets: Priorities / Constraints
# ------------------------------------------------------------------

def make_priorities_tab(app_state):

    rows = pn.Column(
        sizing_mode="stretch_width",
    )

    def refresh(*_):

        components = []
        target_labels = get_queue_target_labels(app_state.queue)

        for index, entry in enumerate(app_state.queue):
            star_name = target_labels[index]

            priority = pn.widgets.Select(
                options=list(
                    range(1, NUMBER_CLASSES_SCHEDULING_PRIORITIES + 1)
                ),
                value=entry.get("priority", 1),
                width=FORM_WIDGET_WIDTH // 4,
                styles={"margin-top": "10px"},

            )

            def update_priority(event, i=index):
                set_target_priority(app_state, i, event.new)
                mark_section_recalculation_needed(app_state, "priorities")

            priority.param.watch(update_priority, "value")

            components.append(
                pn.Row(
                    pn.pane.Markdown(
                        f"**{star_name}**",
                        width=TARGET_FIELD_WIDTH,
                    ),
                    priority,
                    sizing_mode="stretch_width",
                )
            )

        if not components:
            components.append(
                pn.pane.Markdown("Load targets to assign priorities.")
            )

        rows.objects = components

    app_state.param.watch(refresh, "queue")
    refresh()

    return pn.Column(
        make_section_header("Individual priorities", app_state, "priorities"),
        rows,
        sizing_mode="stretch_width",
    )


def make_individual_constraints_tab(app_state):

    rows = pn.Column(
        sizing_mode="stretch_width",
    )

    fields = {
        "max_airmass": {
            "name": "Max airmass",
            "step": STEP_MAX_AIRMASS,
            "format": format_field(STEP_MAX_AIRMASS),
        },
        "min_duration_hours": {
            "name": "Min duration [h]",
            "step": STEP_MIN_DURATION_HOUR,
            "format": format_field(STEP_MIN_DURATION_HOUR),
        },
        "min_moon_separation": {
            "name": "Moon sep. [deg]",
            "step": STEP_MIN_MOON_SEP,
            "format": format_field(STEP_MIN_MOON_SEP),
        },
        "ignore_moon_if_fli_below": {
            "name": "Ignore if FLI <",
            "step": STEP_IGNORE_MOON_FLI,
            "format": format_field(STEP_IGNORE_MOON_FLI),
        },
    }

    def refresh(*_):

        components = []
        target_labels = get_queue_target_labels(app_state.queue)

        for index, entry in enumerate(app_state.queue):
            star_name = target_labels[index]
            constraints = entry["constraints"]

            widgets = []

            for key, settings in fields.items():

                widget = pn.widgets.FloatInput(
                    name=settings["name"],
                    value=constraints[key],
                    step=settings["step"],
                    format=settings["format"],
                    width=int(FORM_WIDGET_WIDTH / 2.5),
                )

                def update_constraint(event, i=index, k=key):
                    update_target_constraint(app_state, i, k, event.new)
                    mark_section_recalculation_needed(app_state, "individual_constraints")

                widget.param.watch(update_constraint, "value")

                widgets.append(widget)

            components.append(
                pn.Column(
                    pn.Row(
                        pn.pane.Markdown(
                            f"**{star_name}**",
                            width=TARGET_FIELD_WIDTH,
                        ),
                        *widgets,
                        sizing_mode="stretch_width",
                    ),
                    sizing_mode="stretch_width",
                )
            )

        if not components:
            components.append(
                pn.pane.Markdown("Load targets to edit their constraints.")
            )

        rows.objects = components

    app_state.param.watch(refresh, "queue")
    refresh()

    return pn.Column(
        make_section_header("Individual constraints", app_state, "individual_constraints"),
        rows,
        sizing_mode="stretch_width",
    )


def make_priorities_constraints_tab(app_state):

    return pn.Column(
        make_priorities_tab(app_state),
        pn.Spacer(height=10),
        make_divider(),
        pn.Spacer(height=10),
        make_individual_constraints_tab(app_state),
        sizing_mode="stretch_width",
    )


# ------------------------------------------------------------------
# Queues Load / Save
# ------------------------------------------------------------------

def make_queue_load_save_tab(app_state):

    file_io_layout, file_io = make_file_io_controls(
        directory_name="Working directory",
        default_directory=DEFAULT_QUEUES_DIR,
        show_save_button=True,
    )

    app_state.queue_file_io = file_io

    log_pane = pn.pane.Markdown(
        "No queue operations yet.",
        sizing_mode="stretch_width",
    )
    log_entries = []

    def update_status(message: str):
        timestamp = datetime.now().astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        log_entries.insert(0, f"- `{timestamp}` — {message}")
        del log_entries[100:]
        log_pane.object = "\n".join(log_entries)

    def clear_history():
        """Clear the log and retain only the clearing action."""
        timestamp = datetime.now().astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        log_entries[:] = [f"- `{timestamp}` — History cleared."]
        log_pane.object = log_entries[0]

    app_state.clear_queue_history = clear_history

    def save_queue(event=None):
        """Save the current input queue and its queue-level settings."""

        try:
            if not app_state.queue:
                raise ValueError("There are no targets in the queue.")

            directory = Path(file_io["working_dir"].value).expanduser()
            filename = file_io["file_name"].value.strip()

            if not filename:
                raise ValueError("Please provide a filename.")

            filepath = Path(filename).expanduser()
            if not filepath.is_absolute():
                filepath = directory / filepath

            if filepath.suffix.lower() != ".json":
                filepath = filepath.with_suffix(".json")

            filepath.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "format_version": 1,
                "queue_config": app_state.queue_config,
                "night_definition": app_state.night_definition,
                "observing_period": app_state.observing_period,
                "custom_start_hours": app_state.custom_start_hours,
                "custom_duration_hours": app_state.custom_duration_hours,
                "queue": app_state.queue,
            }

            with filepath.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            update_status(
                f"✔️ Saved queue ({len(app_state.queue)} targets) to `{filepath}`."
            )
            file_io["refresh_file_list"]()

        except Exception as exc:
            update_status(
                f"❌ Queue save failed: `{type(exc).__name__}: {exc}`"
            )

    def load_queue(event=None):
        """Load a previously saved queue, replacing the current queue."""

        try:
            filename = file_io["file_name"].value.strip()
            if not filename:
                raise ValueError("Please select a queue file.")

            directory = Path(file_io["working_dir"].value).expanduser()
            filepath = Path(filename).expanduser()
            if not filepath.is_absolute():
                filepath = directory / filepath
            if filepath.suffix.lower() != ".json":
                filepath = filepath.with_suffix(".json")

            if not filepath.is_file():
                raise FileNotFoundError(f"Queue file not found: {filepath}")

            with filepath.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate the complete document before changing application state.
            if not isinstance(data, dict) or data.get("format_version") != 1:
                raise ValueError("Unsupported or missing queue file format version.")

            required_sections = {
                "queue_config", "night_definition", "observing_period", "queue",
            }
            # Accept legacy queue files, where custom_hours represented the
            # duration of a custom period starting at the beginning of the night.
            has_new_custom_period = {
                "custom_start_hours", "custom_duration_hours"
            }.issubset(data)
            has_legacy_custom_period = "custom_hours" in data
            if not (has_new_custom_period or has_legacy_custom_period):
                required_sections.add("custom_start_hours")
                required_sections.add("custom_duration_hours")
            missing = required_sections - data.keys()
            if missing:
                raise ValueError(
                    "Invalid queue file: missing sections "
                    + ", ".join(sorted(missing))
                )

            saved_queue = data["queue"]
            saved_config = data["queue_config"]

            if not isinstance(saved_queue, list) or not saved_queue:
                raise ValueError("The queue file does not contain any targets.")
            if not isinstance(saved_config, dict):
                raise ValueError("Invalid queue configuration.")

            instrument_name = saved_config.get("instrument")
            night = saved_config.get("night")
            if instrument_name not in INSTRUMENTS:
                raise ValueError(f"Unknown instrument in queue file: {instrument_name!r}.")
            if not isinstance(night, str) or not night:
                raise ValueError("The queue file has no valid observing night.")

            night_definition = data["night_definition"]
            if night_definition not in (
                "Sunset to sunrise", "Nautical twilight", "Astronomical twilight"
            ):
                raise ValueError(f"Invalid night definition: {night_definition!r}.")

            observing_period = data["observing_period"]
            if observing_period not in (
                "Full night", "First half", "Second half", "Custom"
            ):
                raise ValueError(f"Invalid observing period: {observing_period!r}.")

            if has_new_custom_period:
                custom_start_hours = float(data["custom_start_hours"])
                custom_duration_hours = float(data["custom_duration_hours"])
            else:
                custom_start_hours = 0.0
                custom_duration_hours = float(data["custom_hours"])

            # Custom-period parameters are only relevant when Custom is selected.
            # Older queue files stored custom_hours=0 for the other observing
            # periods, so do not reject those files on the basis of an unused value.
            if observing_period == "Custom":
                if (
                    not np.isfinite(custom_start_hours)
                    or custom_start_hours < 0
                ):
                    raise ValueError(
                        "Custom starting offset must be finite and non-negative."
                    )
                if (
                    not np.isfinite(custom_duration_hours)
                    or custom_duration_hours <= 0
                ):
                    raise ValueError(
                        "Custom duration must be a positive finite value."
                    )
            else:
                # Keep valid defaults in the application state when these
                # settings are inactive; their saved values are immaterial.
                if not np.isfinite(custom_start_hours) or custom_start_hours < 0:
                    custom_start_hours = 0.0
                if not np.isfinite(custom_duration_hours) or custom_duration_hours <= 0:
                    custom_duration_hours = 1.0

            # Check target records and ensure they belong to the same queue setup.
            for index, entry in enumerate(saved_queue, start=1):
                if not isinstance(entry, dict):
                    raise ValueError(f"Target entry {index} is not a valid object.")
                target = entry.get("target")
                constraints = entry.get("constraints")
                if not isinstance(target, dict) or not isinstance(constraints, dict):
                    raise ValueError(f"Target entry {index} is missing target or constraints.")
                for key in ("star_name", "ra", "dec", "exposure_time"):
                    if key not in target:
                        raise ValueError(f"Target entry {index} is missing target field '{key}'.")
                for key in (
                    "max_airmass", "min_duration_hours", "min_moon_separation",
                    "ignore_moon_if_fli_below", "night_definition",
                ):
                    if key not in constraints:
                        raise ValueError(f"Target entry {index} is missing constraint '{key}'.")
                if constraints["night_definition"] != night_definition:
                    raise ValueError(
                        f"Target entry {index} uses a different night definition."
                    )

            # Rebuild derived/shared settings instead of trusting serialized
            # overheads or common-parameter summaries.
            instrument = INSTRUMENTS[instrument_name]
            queue_config = {
                "instrument": instrument_name,
                "night": night,
                "overheads": get_instrument_overheads(instrument_name),
            }

            common_parameters = None
            for entry in saved_queue:
                common_parameters = update_common_parameters(
                    common_parameters,
                    entry["constraints"],
                )

            # Commit only after all validation has succeeded.
            app_state.queue_config = queue_config
            app_state.instrument = instrument_name
            app_state.night = night
            app_state.night_definition = night_definition
            app_state.observing_period = observing_period
            app_state.custom_start_hours = custom_start_hours
            app_state.custom_duration_hours = custom_duration_hours
            app_state.common_parameters = common_parameters
            app_state.queue = saved_queue

            # Recalculate observability immediately, as when an individual
            # observing block is loaded. Do not rely on the observability
            # values stored in the queue file, since they may be stale.
            recalculate_queue(app_state)

            update_status(
                f"✔️ Loaded queue ({len(saved_queue)} targets) from `{filepath}`. "
                "Observability recalculated."
            )

        except json.JSONDecodeError as exc:
            update_status(f"❌ Invalid queue JSON file: `{exc}`")
        except Exception as exc:
            update_status(
                f"❌ Queue load failed: `{type(exc).__name__}: {exc}`"
            )

    file_io["save_button"].on_click(save_queue)
    file_io["load_button"].on_click(load_queue)

    return pn.Column(
        file_io_layout,
        pn.pane.HTML(
            "<div style='font-size: 1.2em;'>Queue History</div>"
        ),
        pn.Column(
            log_pane,
            height=250,
            scroll=True,
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )


# ------------------------------------------------------------------
# Queues: Scheduling
# ------------------------------------------------------------------

def make_ordering_tab(app_state):
    """Display and edit the order of targets in the observing queue."""

    ordering_button_width = int(FORM_WIDGET_WIDTH * 1.2)
    ordering_button_height = BUTTON_HEIGHT

    order_by_ra_button = pn.widgets.Button(
        name="By right ascension",
        button_type="default",
        width=ordering_button_width,
        height=ordering_button_height,
        disabled=True,
    )

    starting_value = pn.widgets.FloatInput(
        name="Starting point rel to HA@night start [h]",
        value=OFFSET_HA,
        step=0.5,
        width=BUTTON_WIDTH // 3 ,
        disabled=True,
    )

    rows = pn.Column(
        sizing_mode="stretch_width",
    )

    status = pn.pane.Markdown(
        "Load targets to start building the observing queue."
    )

    def update_queue(queue, section_key="automatic_ordering"):
        """Commit a reordered queue without updating calculated results."""
        app_state.queue = list(queue)
        app_state.needs_recalculation = True
        mark_section_recalculation_needed(app_state, section_key)

    def order_by_ra(event=None):
        if not app_state.queue:
            return

        # Determine the local sidereal time at the beginning of the
        # configured observing night. The requested starting HA is used
        # to define the corresponding starting RA.
        instrument = INSTRUMENTS[app_state.queue_config["instrument"]]
        night_definition = app_state.queue[0]["constraints"]["night_definition"]
        night_start, _ = get_scheduling_night_boundaries(
            app_state.night,
            night_definition,
            instrument,
        )

        local_sidereal_time = night_start.sidereal_time(
            "apparent",
            longitude=instrument.observatory.longitude_deg * u.deg,
        )
        starting_ra = (
            local_sidereal_time - starting_value.value * u.hourangle
        ).wrap_at(360 * u.deg)

        def sort_key(entry):
            target = entry["target"]
            coordinates = SkyCoord(
                ra=target["ra"],
                dec=target["dec"],
                unit=(u.hourangle, u.deg),
            )
            return (
                (coordinates.ra - starting_ra).wrap_at(360 * u.deg)
                .to_value(u.deg)
            )

        ordered_queue = sorted(app_state.queue, key=sort_key)
        update_queue(ordered_queue)
        select_ordering_button(order_by_ra_button)
        status.object = (
            "Targets ordered by right ascension from the selected starting "
            "hour angle. Recalculate to update the schedule."
        )

    order_by_ra_button.on_click(order_by_ra)

    order_by_airmass_button = pn.widgets.Button(
        name="Minimize airmass",
        button_type="default",
        width=ordering_button_width,
        height=ordering_button_height,
        disabled=True,
    )

    def order_by_airmass(event=None):
        """Greedily order targets by airmass at their scheduled integrations."""
        if len(app_state.queue) < 2:
            return

        instrument = INSTRUMENTS[app_state.queue_config["instrument"]]
        observer = instrument.observatory.to_astroplan_observer()
        night_definition = app_state.queue[0]["constraints"]["night_definition"]
        night_start, night_end = get_scheduling_night_boundaries(
            app_state.night,
            night_definition,
            instrument,
        )

        # Start at the beginning of the selected observing period.
        period = app_state.observing_period
        if period == "First half":
            period_end = night_start + (night_end - night_start) / 2
        elif period == "Second half":
            night_start = night_start + (night_end - night_start) / 2
            period_end = night_end
        elif period == "Custom":
            night_start = min(
                night_start + float(app_state.custom_start_hours) * u.hour,
                night_end,
            )
            period_end = min(
                night_start + float(app_state.custom_duration_hours) * u.hour,
                night_end,
            )
        else:
            period_end = night_end

        overheads = app_state.queue_config["overheads"]
        preset_s = float(overheads["telescope_preset_s"])
        readout_s = float(overheads["readout_s"])

        remaining = list(enumerate(app_state.queue))
        ordered_queue = []
        current_time = night_start
        no_valid_airmass = False

        def integration_airmass(entry, start_time):
            target = entry["target"]
            coordinates = SkyCoord(
                ra=target["ra"],
                dec=target["dec"],
                unit=(u.hourangle, u.deg),
            )
            exposure_s = float(target["exposure_time"])
            sample_times = start_time + np.linspace(0, exposure_s, 5) * u.s
            altaz = observer.altaz(sample_times, coordinates)
            altitude = altaz.alt.to_value(u.deg)
            airmass = altaz.secz.value

            valid = (
                np.isfinite(airmass)
                & (altitude > 0.0)
                & (airmass <= float(entry["constraints"]["max_airmass"]))
            )
            if instrument.altaz_mount:
                valid &= altitude <= 90.0 - DEFAULT_ZENITH_AVOIDANCE_DEG

            # Require the complete integration to satisfy the airmass limits.
            if not np.all(valid):
                return np.inf
            return float(np.mean(airmass))

        for position in range(len(app_state.queue)):
            overhead_s = preset_s if position == 0 else readout_s + preset_s
            integration_start = current_time + overhead_s * u.s

            scored = [
                (
                    integration_airmass(entry, integration_start),
                    original_index,
                    entry,
                )
                for original_index, entry in remaining
            ]

            best_score, best_index, best_entry = min(
                scored,
                key=lambda item: (
                    not np.isfinite(item[0]),
                    item[0] if np.isfinite(item[0]) else item[1],
                    item[1],
                ),
            )
            if not np.isfinite(best_score):
                no_valid_airmass = True

            ordered_queue.append(best_entry)
            remaining = [
                item for item in remaining if item[0] != best_index
            ]
            current_time = (
                integration_start
                + float(best_entry["target"]["exposure_time"]) * u.s
            )

        update_queue(ordered_queue)
        select_ordering_button(order_by_airmass_button)

        status_message = (
            f"Targets ordered greedily to minimize airmass during the "
            f"**{period.lower()}** observing period, accounting for exposure "
            f"times and telescope overheads. Recalculate to update the schedule."
        )
        if no_valid_airmass:
            status_message += (
                " Some integrations had no valid airmass at their scheduled "
                "time; the original queue order was used as a fallback for "
                "those choices."
            )
        if current_time > period_end:
            status_message += (
                " **Warning:** the resulting queue extends beyond the "
                "selected observing period."
            )
        status.object = status_message

    order_by_airmass_button.on_click(order_by_airmass)

    order_by_airmass_spread_button = pn.widgets.Button(
        name="Minimize airmass & maximize target spread",
        button_type="default",
        width=ordering_button_width,
        height=ordering_button_height,
        disabled=True,
        styles={
            "white-space": "normal",
            "text-align": "left",
            "line-height": "1.2",
        },
    )

    ordering_buttons = (
        order_by_ra_button,
        order_by_airmass_button,
        order_by_airmass_spread_button,
    )

    def select_ordering_button(selected_button):
        """Visually mark the chosen ordering method and deactivate the others."""
        for button in ordering_buttons:
            button.button_type = (
                "primary" if button is selected_button else "default"
            )

    def order_by_airmass_and_spread(event=None):
        """Minimize airmass first, then spread repeat observations in time.

        A greedy airmass ordering provides the baseline. Pairwise swaps are
        then tested; a swap is retained only if every integration still
        satisfies its airmass/altitude constraints and the total airmass is
        not worse than the baseline. Among such schedules, swaps are chosen
        to maximize the smallest interval between consecutive observations
        of the same target.
        """
        if len(app_state.queue) < 2:
            return

        instrument = INSTRUMENTS[app_state.queue_config["instrument"]]
        observer = instrument.observatory.to_astroplan_observer()
        night_definition = app_state.queue[0]["constraints"]["night_definition"]
        night_start, night_end = get_scheduling_night_boundaries(
            app_state.night, night_definition, instrument
        )

        period = app_state.observing_period
        if period == "First half":
            period_end = night_start + (night_end - night_start) / 2
        elif period == "Second half":
            night_start = night_start + (night_end - night_start) / 2
            period_end = night_end
        elif period == "Custom":
            night_start = min(
                night_start + float(app_state.custom_start_hours) * u.hour,
                night_end,
            )
            period_end = min(
                night_start + float(app_state.custom_duration_hours) * u.hour,
                night_end,
            )
        else:
            period_end = night_end

        overheads = app_state.queue_config["overheads"]
        preset_s = float(overheads["telescope_preset_s"])
        readout_s = float(overheads["readout_s"])

        def integration_airmass(entry, start_time):
            target = entry["target"]
            coordinates = SkyCoord(
                ra=target["ra"], dec=target["dec"],
                unit=(u.hourangle, u.deg),
            )
            exposure_s = float(target["exposure_time"])
            sample_times = start_time + np.linspace(0, exposure_s, 5) * u.s
            altaz = observer.altaz(sample_times, coordinates)
            altitude = altaz.alt.to_value(u.deg)
            airmass = altaz.secz.value
            valid = (
                np.isfinite(airmass)
                & (altitude > 0.0)
                & (airmass <= float(entry["constraints"]["max_airmass"]))
            )
            if instrument.altaz_mount:
                valid &= altitude <= 90.0 - DEFAULT_ZENITH_AVOIDANCE_DEG
            if not np.all(valid):
                return np.inf
            return float(np.mean(airmass))

        def evaluate(queue):
            """Return total airmass, repeated-target gaps and validity."""
            current = night_start
            total_airmass = 0.0
            midpoints = {}
            for position, entry in enumerate(queue):
                overhead_s = preset_s if position == 0 else readout_s + preset_s
                start = current + overhead_s * u.s
                score = integration_airmass(entry, start)
                if not np.isfinite(score):
                    return np.inf, (0.0, 0.0), False, current
                total_airmass += score
                duration_s = float(entry["target"]["exposure_time"])
                midpoint = start + 0.5 * duration_s * u.s
                name = str(entry["target"]["star_name"]).casefold()
                midpoints.setdefault(name, []).append(midpoint)
                current = start + duration_s * u.s

            consecutive_gaps = []
            total_gap = 0.0
            for times in midpoints.values():
                times.sort(key=lambda value: value.unix)
                gaps = [
                    (times[i + 1] - times[i]).to_value(u.s)
                    for i in range(len(times) - 1)
                ]
                consecutive_gaps.extend(gaps)
                total_gap += sum(gaps)

            # Lexicographic spacing objective: maximize the smallest gap,
            # then the sum of all consecutive gaps.
            spacing = (min(consecutive_gaps), total_gap) if consecutive_gaps else (np.inf, 0.0)
            return total_airmass, spacing, True, current

        # Stage 1: the same greedy airmass minimization used by the existing
        # ordering button, preserving the original order as the tie-breaker.
        remaining = list(enumerate(app_state.queue))
        ordered = []
        current_time = night_start
        for position in range(len(app_state.queue)):
            overhead_s = preset_s if position == 0 else readout_s + preset_s
            integration_start = current_time + overhead_s * u.s
            scored = [
                (integration_airmass(entry, integration_start), original_index, entry)
                for original_index, entry in remaining
            ]
            best_score, best_index, best_entry = min(
                scored,
                key=lambda item: (
                    not np.isfinite(item[0]),
                    item[0] if np.isfinite(item[0]) else item[1],
                    item[1],
                ),
            )
            ordered.append(best_entry)
            remaining = [item for item in remaining if item[0] != best_index]
            current_time = integration_start + float(best_entry["target"]["exposure_time"]) * u.s

        baseline_airmass, baseline_spacing, baseline_valid, baseline_end = evaluate(ordered)
        if not baseline_valid:
            status.object = (
                "Could not find an ordering in which every integration satisfies "
                "its airmass and altitude constraints. No changes were made."
            )
            return

        # Stage 2: local pair-swap search. A swap can alter subsequent start
        # times, so the full schedule is reevaluated for every candidate.
        best_queue = list(ordered)
        best_airmass = baseline_airmass
        best_spacing = baseline_spacing
        tolerance = 1e-9
        improved = True
        while improved:
            improved = False
            candidate_choice = None
            for i in range(len(best_queue) - 1):
                for j in range(i + 1, len(best_queue)):
                    candidate = list(best_queue)
                    candidate[i], candidate[j] = candidate[j], candidate[i]
                    score, spacing, valid, _ = evaluate(candidate)
                    if not valid or score > baseline_airmass + tolerance:
                        continue
                    if spacing > best_spacing:
                        if candidate_choice is None or spacing > candidate_choice[0]:
                            candidate_choice = (spacing, score, candidate)
            if candidate_choice is not None:
                best_spacing, best_airmass, best_queue = candidate_choice
                improved = True

        update_queue(best_queue)
        select_ordering_button(order_by_airmass_spread_button)
        _, _, _, queue_end = evaluate(best_queue)
        repeated = sum(
            1 for count in __import__("collections").Counter(
                str(entry["target"]["star_name"]).casefold()
                for entry in best_queue
            ).values() if count > 1
        )
        status_message = (
            "Queue ordered in two stages: **(1)** greedy airmass minimization; "
            "**(2)** maximize the minimum time separation between consecutive "
            "observations of repeated targets, using swaps that preserve all "
            "airmass/altitude constraints and do not worsen the baseline total "
            "airmass. Recalculate to update the schedule."
        )
        if repeated == 0:
            status_message += " No target is repeated, so the spacing stage had no effect."
        if queue_end > period_end:
            status_message += " **Warning:** the resulting queue extends beyond the selected observing period."
        status.object = status_message

    order_by_airmass_spread_button.on_click(order_by_airmass_and_spread)

    def move_target(index, destination):
        """Move one target to a new queue position."""
        queue = list(app_state.queue)

        if not 0 <= index < len(queue):
            return

        entry = queue.pop(index)
        queue.insert(destination, entry)

        update_queue(queue, section_key="manual_ordering")

    def refresh(*_):
        components = []
        target_labels = get_queue_target_labels(app_state.queue)
        n_targets = len(app_state.queue)

        order_by_ra_button.disabled = n_targets < 2
        order_by_airmass_button.disabled = n_targets < 2
        order_by_airmass_spread_button.disabled = n_targets < 2
        starting_value.disabled = n_targets < 2

        for index, star_name in enumerate(target_labels):
            buttons = []

            button_specs = [
                ("Up", index - 1, index == 0),
                ("Down", index + 1, index == n_targets - 1),
                ("Top", 0, index == 0),
                ("Bottom", n_targets - 1, index == n_targets - 1),
            ]

            for label, destination, disabled in button_specs:
                button = pn.widgets.Button(
                    name=label,
                    button_type="primary",
                    width=BUTTON_WIDTH // 5,
                    height=BUTTON_HEIGHT,
                    disabled=disabled,
                )
                button.on_click(
                    lambda event, i=index, d=destination: move_target(i, d)
                )
                buttons.append(button)

            components.append(
                pn.Row(
                    pn.pane.Markdown(
                        f"**{index + 1}. {star_name}**",
                        width=int(TARGET_FIELD_WIDTH * 1.2),
                    ),
                    *buttons,
                    sizing_mode="stretch_width",
                )
            )

        if not components:
            components.append(
                pn.pane.Markdown("Load targets to define their scheduling order.")
            )

        rows.objects = components

    app_state.param.watch(refresh, "queue")
    refresh()

    return pn.Column(
        make_section_header("Automatic ordering", app_state, "automatic_ordering"),
        pn.Row(
            pn.Column(
                pn.Row(
                    order_by_ra_button,
                    starting_value,
                    sizing_mode="stretch_width",
                    styles={"align-items": "end"},
                ),
                order_by_airmass_button,
                order_by_airmass_spread_button,
                sizing_mode="stretch_width",
                styles={"gap": "6px"},
            ),
            sizing_mode="stretch_width",
        ),
        pn.Spacer(height=10),
        make_divider(),
        pn.Spacer(height=10),
        make_section_header("Manual ordering", app_state, "manual_ordering"),
        rows,
        status,
        sizing_mode="stretch_width",
    )


# ------------------------------------------------------------------
# General control tabs
# ------------------------------------------------------------------

def make_control_tabs(app_state):

    return pn.Tabs(
        ("Load targets", make_target_load_tab(app_state)),
        ("Priorities / Constraints", make_priorities_constraints_tab(app_state)),
        ("Scheduling", make_ordering_tab(app_state)),
        ("Queues Load / Save", make_queue_load_save_tab(app_state)),
        sizing_mode="stretch_width",
    )