import asyncio
from datetime import datetime
import panel as pn
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from astropy.time import Time
from astropy import units as u

from exoptima.tabs.components import (
    make_app_title,
    make_recalculation_banner,
)
from exoptima.config.instruments import INSTRUMENTS, get_instrument_overheads
from exoptima.config.layout import BUTTON_WIDTH, BUTTON_HEIGHT, FORM_WIDGET_WIDTH
from exoptima.scheduling.obs_helpers import get_scheduling_night_boundaries
from exoptima.scheduling.targets import get_queue_target_labels, clear_queue

# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------

def make_header(app_state, on_recalculate):

    context_md = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
    )

    # Queue configuration controls are placed directly in the header.
    instrument = pn.widgets.Select(
        name="Instrument",
        options=list(INSTRUMENTS.keys()),
        value=None,
        width=FORM_WIDGET_WIDTH,
        disabled=True,
    )
    night = pn.widgets.DatePicker(
        name="Night",
        value=None,
        width=FORM_WIDGET_WIDTH // 2,
        disabled=True,
    )
    night_definition = pn.widgets.Select(
        name="Night definition",
        options=[
            "Sunset to sunrise",
            "Nautical twilight",
            "Astronomical twilight",
        ],
        value="Nautical twilight",
        width=FORM_WIDGET_WIDTH,
        disabled=True,
    )
    observing_period = pn.widgets.Select(
        name="Observing period",
        options=["Full night", "First half", "Second half", "Custom"],
        value="Full night",
        width=int(FORM_WIDGET_WIDTH / 1.5),
        disabled=True,
    )
    custom_start_hours = pn.widgets.FloatInput(
        name="Starting time [h]",
        value=0.0,
        start=0.0,
        step=0.5,
        width=int(FORM_WIDGET_WIDTH / 3),
        disabled=True,
    )
    custom_duration_hours = pn.widgets.FloatInput(
        name="Duration [h]",
        value=1.0,
        start=0.5,
        step=0.5,
        width=int(FORM_WIDGET_WIDTH / 3),
        disabled=True,
    )

    updating_configuration = False

    configuration_status_pane = make_recalculation_banner(app_state)

    def sync_configuration(*_):
        nonlocal updating_configuration
        updating_configuration = True
        has_queue = bool(app_state.queue)

        for widget in (instrument, night, night_definition, observing_period):
            widget.disabled = not has_queue
        custom_enabled = has_queue and app_state.observing_period == "Custom"
        custom_start_hours.disabled = not custom_enabled
        custom_duration_hours.disabled = not custom_enabled

        if has_queue:
            instrument.value = app_state.queue_config.get("instrument")
            night.value = datetime.strptime(app_state.night, "%Y-%m-%d").date()
            night_definition.value = app_state.night_definition
            observing_period.value = app_state.observing_period
            custom_start_hours.value = app_state.custom_start_hours
            custom_duration_hours.value = app_state.custom_duration_hours or 1.0
        else:
            instrument.value = None
            night.value = None

        updating_configuration = False

    def update_configuration(event=None):
        if updating_configuration or not app_state.queue:
            return

        app_state.queue_config = {
            **app_state.queue_config,
            "instrument": instrument.value,
            "night": night.value.isoformat() if night.value else None,
            "overheads": get_instrument_overheads(instrument.value),
        }
        app_state.instrument = instrument.value
        app_state.night = night.value.isoformat() if night.value else None
        app_state.night_definition = night_definition.value
        app_state.observing_period = observing_period.value
        app_state.custom_start_hours = custom_start_hours.value
        app_state.custom_duration_hours = custom_duration_hours.value
        custom_start_hours.disabled = observing_period.value != "Custom"
        custom_duration_hours.disabled = observing_period.value != "Custom"
        app_state.needs_recalculation = True

    for widget in (
        instrument, night, night_definition, observing_period,
        custom_start_hours, custom_duration_hours,
    ):
        widget.param.watch(update_configuration, "value")

    app_state.param.watch(sync_configuration, "queue")
    app_state.param.watch(sync_configuration, "night")
    app_state.param.watch(sync_configuration, "night_definition")
    app_state.param.watch(sync_configuration, "observing_period")
    app_state.param.watch(sync_configuration, "custom_start_hours")
    app_state.param.watch(sync_configuration, "custom_duration_hours")
    sync_configuration()

    recalculate_button = pn.widgets.Button(
        name="Recalculate",
        button_type="success",
        disabled=True,
        width=BUTTON_WIDTH // 2 ,
        height=BUTTON_HEIGHT,
        styles={"margin-top": "20px"},
    )

    status_md = pn.pane.Markdown(
        "",
        styles={
            "color": "#1565c0",
            "font-weight": "bold",
            "font-size": "11px",
            "margin-top": "6px",
        },
        width=FORM_WIDGET_WIDTH,
        height=BUTTON_HEIGHT,
    )

    async def _on_recalculate_click(event=None):
        recalculate_button.disabled = True
        status_md.object = "🔭 Calculating queue observability…"

        # Give Panel's event loop time to send the status update to the browser
        # before starting the synchronous calculation.
        await asyncio.sleep(0.1)

        try:
            on_recalculate(event)
        finally:
            status_md.object = ""
            recalculate_button.disabled = not app_state.needs_recalculation

    recalculate_button.on_click(_on_recalculate_click)

    clear_button = pn.widgets.Button(
        name="Clear",
        button_type="danger",
        disabled=True,
        width=BUTTON_WIDTH // 2,
        height=BUTTON_HEIGHT,
        styles={"margin-top": "20px"},
    )

    def _on_clear_click(event=None):
        # Reset the queue and all queue-level configuration to startup values.
        clear_queue(app_state)

        # Clear both operation histories, retaining the clearing action itself.
        if hasattr(app_state, "clear_target_load_history"):
            app_state.clear_target_load_history()
        if hasattr(app_state, "clear_queue_history"):
            app_state.clear_queue_history()

        app_state.night_definition = "Nautical twilight"
        app_state.observing_period = "Full night"
        app_state.custom_start_hours = 0.0
        app_state.custom_duration_hours = 1.0

        status_md.object = ""
        recalculate_button.disabled = True

    clear_button.on_click(_on_clear_click)

    def update_clear_button(event):
        clear_button.disabled = not bool(event.new)

    app_state.param.watch(update_clear_button, "queue")

    def update_recalculate_button(event):
        recalculate_button.disabled = not event.new

    app_state.param.watch(update_recalculate_button, "needs_recalculation")

    def _update_context(*_):

        common = app_state.common_parameters or {}

        if not app_state.queue:
            context_md.object = ""
            return

        headers = []
        values = []

        remaining = dict(common)
        remaining.pop("night_definition", None)

        # Airmass constraint
        if {"max_airmass", "min_duration_hours"}.issubset(remaining):
            headers.append("Airmass (max value, min dur.)")
            values.append(
                f"< {remaining['max_airmass']:.1f} for "
                f"{remaining['min_duration_hours']:.1f} h"
            )
            remaining.pop("max_airmass")
            remaining.pop("min_duration_hours")

        # Moon constraint
        if {
            "min_moon_separation",
            "ignore_moon_if_fli_below",
        }.issubset(remaining):
            headers.append("Moon (sep, Min FLI)")
            values.append(
                f"{remaining['min_moon_separation']:.1f}° if > "
                f"{remaining['ignore_moon_if_fli_below']:.2f}"
            )
            remaining.pop("min_moon_separation")
            remaining.pop("ignore_moon_if_fli_below")

        # Display all remaining common parameters individually.
        labels = {
            "max_airmass": "Maximum airmass",
            "min_duration_hours": "Minimum duration [h]",
            "min_moon_separation": "Moon separation [deg]",
            "ignore_moon_if_fli_below": "Minimum FLI",
        }

        for key, value in remaining.items():
            headers.append(labels.get(
                key,
                key.replace("_", " ").capitalize(),
            ))
            values.append(str(value))

        if not headers:
            context_md.object = "### Common constraints"
            return

        header_row = "| " + " | ".join(f"**{h}**" for h in headers) + " |"
        separator = "| " + " | ".join(":---:" for _ in headers) + " |"
        value_row = "| " + " | ".join(values) + " |"

        context_md.object = "\n".join([
            "### Common constraints",
            "",
            header_row,
            separator,
            value_row,
        ])

    app_state.param.watch(
        _update_context,
        ["instrument", "night", "common_parameters", "queue"],
    )

    # Populate the header immediately (also handles an initially empty queue).
    _update_context()

    app_state.header_context_pane = context_md

    configuration_controls = pn.Row(
        pn.Column(
            instrument,
            configuration_status_pane,
            width=FORM_WIDGET_WIDTH,
            height=BUTTON_HEIGHT + 22,
            sizing_mode="fixed",
        ),
        pn.Spacer(width=15),
        pn.Column(
            pn.Row(
                night,
                night_definition,
                width=2 * FORM_WIDGET_WIDTH,
                height=48,
                sizing_mode="fixed",
                styles={"align-items": "end"},
            ),
            pn.Spacer(height=10),
            pn.Row(
                observing_period,
                custom_start_hours,
                pn.Spacer(width=10),
                custom_duration_hours,
                width=2 * FORM_WIDGET_WIDTH,
                height=48,
                sizing_mode="fixed",
                styles={"align-items": "end"},
            ),
            width=2 * FORM_WIDGET_WIDTH,
            height=105,
            sizing_mode="fixed",
        ),
        width=3 * FORM_WIDGET_WIDTH,
        height=105,
        sizing_mode="fixed",
        styles={"align-items": "start"},
    )

    return pn.Row(
        make_app_title("scheduling"),
        pn.Spacer(width=15),
        pn.Column(
            pn.Row(
                recalculate_button,
                clear_button,
            ),
            status_md,
            width=2 * BUTTON_WIDTH + 10,
            height=75,
            sizing_mode="fixed",
        ),
        pn.Spacer(width=15),
        configuration_controls,
        pn.Spacer(width=15),
        pn.Column(
            context_md,
            sizing_mode="stretch_width",
        ),
    )


def make_output_tabs(app_state):

    def get_selected_observing_period():
        """Return the selected observing interval within the full night."""
        instrument = INSTRUMENTS[app_state.queue_config["instrument"]]
        night_start, night_end = get_scheduling_night_boundaries(
            app_state.night,
            app_state.night_definition,
            instrument,
        )

        full_night_start = night_start
        full_night_end = night_end
        full_duration = full_night_end - full_night_start

        if app_state.observing_period == "First half":
            night_end = full_night_start + full_duration / 2
        elif app_state.observing_period == "Second half":
            night_start = full_night_start + full_duration / 2
        elif app_state.observing_period == "Custom":
            night_start = min(
                full_night_start + float(app_state.custom_start_hours) * u.hour,
                full_night_end,
            )
            custom_end = (
                night_start + float(app_state.custom_duration_hours) * u.hour
            )
            night_end = min(custom_end, full_night_end)

        return full_night_start, full_night_end, night_start, night_end

    queue_plot = pn.pane.Matplotlib(
        sizing_mode="stretch_both",
        visible=False,
    )

    queue_summary = pn.pane.Markdown(
        "",
        width=280,
        sizing_mode="stretch_height",
    )

    queue_content = pn.Row(
        queue_plot,
        queue_summary,
        sizing_mode="stretch_both",
    )

    queue_empty = pn.pane.Markdown(
        "**No targets loaded.** Load a target to start building the observing queue.",
        sizing_mode="stretch_both",
    )

    queue_display = pn.Column(
        queue_empty,
        queue_content,
        sizing_mode="stretch_both",
    )

    def format_duration(seconds):
        total_minutes = round(seconds / 60)
        hours, minutes = divmod(total_minutes, 60)

        if hours:
            return f"{hours} h {minutes:02d} min"

        return f"{minutes} min"

    def update_queue(*_):

        queue = app_state.calculated_queue

        if not queue:
            queue_plot.object = None
            queue_plot.visible = False
            queue_summary.object = ""
            queue_content.visible = False
            queue_empty.visible = True
            return

        queue_empty.visible = False
        queue_content.visible = True
        queue_plot.visible = True

        overheads = app_state.queue_config["overheads"]

        preset = overheads["telescope_preset_s"]
        readout = overheads["readout_s"]

        full_night_start, full_night_end, period_start, period_end = (
            get_selected_observing_period()
        )
        y_min = (period_start - full_night_start).to_value("hour")
        y_max = (period_end - full_night_start).to_value("hour")

        # Calculate queue statistics.
        n_targets = len(queue)

        distinct_targets = {
            entry["target"]["star_name"].strip().casefold()
            for entry in queue
        }
        n_distinct = len(distinct_targets)

        integration_time = sum(
            entry["target"]["exposure_time"]
            for entry in queue
        )

        overhead_time = preset + (n_targets - 1) * (readout + preset)

        total_time = integration_time + overhead_time

        queue_summary.object = f"""
### Queue summary

**Targets loaded:** {n_targets} ({n_distinct} different)

**Total queue time:** {format_duration(total_time)}

- Integrations: {format_duration(integration_time)}
- Overheads: {format_duration(overhead_time)}
"""

        # Build observing queue plot.
        preset_hours = preset / 3600
        readout_hours = readout / 3600

        fig, ax = plt.subplots(
            figsize=(5, 8),
            tight_layout=True,
        )

        current_time = y_min

        target_labels = get_queue_target_labels(queue)
        integration_labels = []

        for i, entry in enumerate(queue):

            target = entry["target"]
            name = target_labels[i]
            exposure = target["exposure_time"] / 3600

            overhead = (
                preset_hours
                if i == 0
                else readout_hours + preset_hours
            )

            ax.bar(
                0,
                overhead,
                bottom=current_time,
                width=0.65,
                color="lightgrey",
                edgecolor="none",
                align="center",
            )

            current_time += overhead

            integration_bar = ax.bar(
                0,
                exposure,
                bottom=current_time,
                width=0.65,
                color="tab:blue",
                alpha=0.3,
                edgecolor="tab:blue",
                linewidth=1.2,
                align="center",
            )

            label = ax.text(
                0,
                current_time + exposure / 2,
                name,
                ha="center",
                va="center",
            )
            integration_labels.append(
                (label, integration_bar.patches[0], name,
                 current_time + exposure / 2)
            )

            current_time += exposure

        ax.set_xlim(-0.6, 0.6)
        ax.set_ylim(y_min, y_max)
        ax.invert_yaxis()

        # Decide from the rendered dimensions whether each label fits inside
        # its integration bar. Labels that do not fit are moved outside left.
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        short_labels = []

        for label, bar, name, centre in integration_labels:
            label_height_px = label.get_window_extent(renderer).height
            bar_height_px = bar.get_window_extent(renderer).height

            if label_height_px + 4 > bar_height_px:
                label.remove()
                short_labels.append((centre, name))

        if short_labels:
            # Keep external labels separated vertically, even when integrations
            # are very short and their original centres are almost coincident.
            short_labels.sort(key=lambda item: item[0])
            pixels_per_hour = abs(
                ax.transData.transform((0, 1))[1]
                - ax.transData.transform((0, 0))[1]
            )
            min_separation = 1.25 * plt.rcParams["font.size"] * fig.dpi / 72
            min_separation_hours = min_separation / max(pixels_per_hour, 1e-12)

            label_positions = []
            for centre, name in short_labels:
                position = centre
                if label_positions:
                    position = max(position, label_positions[-1] + min_separation_hours)
                label_positions.append(position)

            # Expand the left margin of the data area to make room for names.
            ax.set_xlim(-1.8, 0.6)

            for (centre, name), label_y in zip(short_labels, label_positions):
                ax.annotate(
                    name,
                    xy=(-0.36, centre),
                    xytext=(-0.48, label_y),
                    ha="right",
                    va="center",
                    arrowprops={
                        "arrowstyle": "->",
                        "color": "0.35",
                        "linewidth": 0.8,
                        "shrinkA": 2,
                        "shrinkB": 2,
                    },
                    fontsize=plt.rcParams["font.size"],
                    annotation_clip=False,
                )

        ax.set_xticks([])
        ax.set_ylabel("Time since beginning of night [h]")

        ax.grid(axis="y", alpha=0.3)

        queue_plot.object = fig

    app_state.param.watch(update_queue, "calculated_queue")
    update_queue()

    observability_plot = pn.pane.Matplotlib(
        sizing_mode="stretch_both",
    )

    observability_empty = pn.pane.Markdown(
        "**No targets loaded.** Load a target to display its observability windows.",
        sizing_mode="stretch_width",
    )

    observability_content = pn.Column(
        observability_empty,
        observability_plot,
        sizing_mode="stretch_both",
        scroll=True,
    )

    def update_observability(*_):

        queue = app_state.calculated_queue

        if not queue:
            observability_plot.object = None
            observability_plot.visible = False
            observability_empty.visible = True
            return

        observability_empty.visible = False
        observability_plot.visible = True

        full_night_start, full_night_end, period_start, period_end = (
            get_selected_observing_period()
        )
        y_min = (period_start - full_night_start).to_value("hour")
        y_max = (period_end - full_night_start).to_value("hour")
        target_labels = get_queue_target_labels(queue)

        # Keep a minimum width per target so the columns remain legible.
        fig_width = max(7, 1.25 * len(queue) + 2)

        fig, ax = plt.subplots(
            figsize=(fig_width, 8),
            tight_layout=True,
        )

        # Reconstruct the queue timing from the beginning of the night.
        # This uses the same overhead convention as the Observing queue plot.
        overheads = app_state.queue_config["overheads"]
        preset_hours = overheads["telescope_preset_s"] / 3600
        readout_hours = overheads["readout_s"] / 3600
        current_time = y_min

        for index, entry in enumerate(queue):

            overhead = (
                preset_hours
                if index == 0
                else readout_hours + preset_hours
            )
            integration_start = current_time + overhead
            exposure_hours = entry["target"]["exposure_time"] / 3600
            integration_end = integration_start + exposure_hours

            observability = entry.get("observability", {})
            windows = observability.get("windows", [])
            observable_intervals = []

            for window in windows:
                window_start = (
                    Time(
                        window["start"],
                        format="isot",
                        scale="utc",
                    ) - full_night_start
                ).to_value("hour")

                window_end = (
                    Time(
                        window["end"],
                        format="isot",
                        scale="utc",
                    ) - full_night_start
                ).to_value("hour")

                ax.bar(
                    index,
                    window_end - window_start,
                    bottom=window_start,
                    width=0.58,
                    color="tab:blue",
                    alpha=0.35,
                    edgecolor="tab:blue",
                    linewidth=1.2,
                    align="center",
                )

                observable_intervals.append((window_start, window_end))

            # Merge overlapping/touching windows before measuring coverage.
            merged_intervals = []
            for start, end in sorted(observable_intervals):
                if merged_intervals and start <= merged_intervals[-1][1]:
                    merged_intervals[-1] = (
                        merged_intervals[-1][0],
                        max(merged_intervals[-1][1], end),
                    )
                else:
                    merged_intervals.append((start, end))

            covered_hours = sum(
                max(
                    0.0,
                    min(integration_end, end)
                    - max(integration_start, start),
                )
                for start, end in merged_intervals
            )
            integration_is_fully_observable = (
                covered_hours >= exposure_hours - 1e-9
            )

            integration_color = (
                "tab:green" if integration_is_fully_observable else "tab:red"
            )
            ax.bar(
                index,
                exposure_hours,
                bottom=integration_start,
                width=0.72,
                facecolor=integration_color,
                edgecolor=integration_color,
                alpha=0.35,
                linewidth=2.0,
                align="center",
                zorder=5,
            )

            if not windows:
                ax.text(
                    index,
                    (y_min + y_max) / 2,
                    "Not observable",
                    ha="center",
                    va="center",
                    color="0.4",
                    fontsize=9,
                    bbox={
                        "boxstyle": "round,pad=0.45",
                        "facecolor": "white",
                        "edgecolor": "0.6",
                        "linewidth": 1.0,
                    },
                )

            current_time = integration_end

        # Queue order is represented from left to right.
        ax.set_xticks(range(len(queue)))
        ax.set_xticklabels(
            [
                f"{index + 1}. {name}"
                for index, name in enumerate(target_labels)
            ],
            rotation=0,
            ha="center",
        )

        ax.set_xlim(-0.6, len(queue) - 0.4)
        ax.set_ylim(y_min, y_max)
        ax.invert_yaxis()

        ax.set_ylabel("Time since beginning of night [h]")
        ax.set_xlabel("Queue position / target")
        ax.grid(axis="y", alpha=0.3)
        ax.legend(
            handles=[
                Patch(
                    facecolor="tab:blue",
                    edgecolor="tab:blue",
                    alpha=0.35,
                    label="Observable window",
                ),
                Patch(
                    facecolor="tab:green",
                    edgecolor="tab:green",
                    alpha=0.35,
                    linewidth=2.0,
                    label="Queue position: observable",
                ),
                Patch(
                    facecolor="tab:red",
                    edgecolor="tab:red",
                    alpha=0.35,
                    linewidth=2.0,
                    label="Queue position: not observable",
                ),
            ],
            loc="lower left",
            fontsize=8,
        )

        observability_plot.object = fig

    app_state.param.watch(update_observability, "calculated_queue")
    update_observability()

    return pn.Tabs(
        ("Observing queue", queue_display),
        ("Target Observability", observability_content),
        sizing_mode="stretch_both",
    )