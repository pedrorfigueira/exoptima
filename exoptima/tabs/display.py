# Display section and tabs definitions

from datetime import datetime, timedelta

import numpy as np

import panel as pn
pn.extension()

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import astropy.units as u
from astropy.time import Time
from astropy.coordinates import SkyCoord

from exoptima.core.state import AppState, ObservabilityResult, MultiNightObservability
from exoptima.config.layout import DISPLAY_MAIN_FRACTION, MONTH_XLABEL_STEP
from exoptima.tabs.export import make_save_button

from exoptima.core.observability import compute_single_night_observability

# Custom divider

divider_h = pn.Spacer(
    height=1,
    sizing_mode="stretch_width",
    styles={"background-color": "#e0e0e0"},
)

def make_display_tab(plot_pane, stats_pane, plot_save_filename="plot.pdf", stats_save_filename="summary.txt"):

    plot_view = make_save_button(plot_pane, plot_save_filename)
    summary_view = make_save_button(stats_pane, stats_save_filename)

    return pn.Column(
        pn.Column(plot_view,
                  styles={"flex": f"0 0 {DISPLAY_MAIN_FRACTION * 100:.0f}%"},
                  ),
        divider_h,
        pn.Column(summary_view,
                  styles={"flex": f"0 0 {(1. - DISPLAY_MAIN_FRACTION) * 100:.0f}%"},
                  ),
        sizing_mode="stretch_both",
    )


#####

def make_daily_observability_tab(app_state: AppState):

    plot_pane = pn.pane.Matplotlib(min_height=300, sizing_mode="stretch_both")
    stats_md = pn.pane.Markdown("### Summary\nNo data yet.")

    def update_daily_observability(*_):
        obs = getattr(app_state, "observability", None)
        if obs is None:
            return

        times = obs.time_grid
        mask = obs.mask

        night_start = obs.night_start
        night_end = obs.night_end

        alt = obs.altitude.to_value(u.deg)

        # ----------------------------
        # Plot
        # ----------------------------

        t_ref = app_state.reference_time

        # Find closest time index
        idx_ref = int(np.argmin(np.abs(times - t_ref)))

        t_ref_dt = times[idx_ref].datetime
        alt_ref = alt[idx_ref]
        is_observable_now = bool(mask[idx_ref])

        # Instantaneous airmass from altitude
        airmass_ref = 1.0 / np.sin(np.deg2rad(alt_ref))

        fig, ax_alt = plt.subplots(figsize=(8, 4), tight_layout=True)

        # --- Daytime shading ---
        ax_alt.axvspan(times[0].datetime, night_start.datetime, color="lightgrey", alpha=0.4)
        ax_alt.axvspan(night_end.datetime, times[-1].datetime, color="lightgrey", alpha=0.4)

        # --- Altitude (left axis) ---
        # Observable (green)
        ax_alt.plot(
            times.datetime, np.where(mask, alt, np.nan),
            color="#2e7d32",  # green
            lw=2.0, label="Observable",
        )

        # Not observable (red)
        ax_alt.plot(
            times.datetime, np.where(~mask, alt, np.nan),
            color="#b00020",  # red
            lw=1.0, ls="--", label="Not observable",
        )

        # --- Reference time vertical line ---
        ax_alt.axvline(
            t_ref_dt,
            color="black", lw=1.0, ls=":", alpha=0.8, zorder=3,
        )

        if is_observable_now:
            ax_alt.scatter(
                t_ref_dt,
                alt_ref,
                s=80, color="#2e7d32", zorder=5,
            )

            ax_alt.annotate(
                f"Airmass = {airmass_ref:.2f}",
                xy=(t_ref_dt, alt_ref),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=7,
                color="#2e7d32",
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor="white",
                    edgecolor="#2e7d32",
                    alpha=0.9,
                ),
            )

        ax_alt.set_ylabel("Altitude [deg]", fontsize=9)
        ax_alt.set_ylim(0, 90)
        ax_alt.set_xlim(times.datetime[0], times.datetime[-1])

        # --- Airmass (right axis) ---
        ax_airmass = ax_alt.twinx()

        def alt_from_airmass(x):
            return np.degrees(np.arcsin(1.0 / x))

        airmass_ticks = np.array([1.0, 1.5, 2.0, 3.0, 5.0])
        airmass_tick_alts = alt_from_airmass(airmass_ticks)

        ax_airmass.set_ylim(ax_alt.get_ylim())
        ax_airmass.set_yticks(airmass_tick_alts)
        ax_airmass.set_yticklabels([f"{x:g}" for x in airmass_ticks])
        ax_airmass.set_ylabel("Airmass", fontsize=9)

        # --- Cosmetics ---
        ax_alt.set_xlabel("Time (UT) [h]", fontsize=9)
        ax_alt.tick_params(axis="both", labelsize=8)
        ax_airmass.tick_params(axis="y", labelsize=8)

        ax_alt.legend(fontsize=8, loc="upper left")

        # Night date: use sunset date
        night_date = night_start.to_datetime().date().isoformat()

        # ----------------------------
        # Night label
        # ----------------------------
        ref_time_label = app_state.reference_time.iso[:16] + " UTC"

        ax_alt.text(
            0.98,
            0.95,
            f"Night: {night_date}\nRef: {ref_time_label}",
            transform=ax_alt.transAxes,
            ha="right",
            va="top",
            fontsize=7,
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor="white",
                edgecolor="lightgrey",
                alpha=0.9,
            ),
        )

        # Time axis formatting: Major ticks: hours
        ax_alt.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax_alt.xaxis.set_major_formatter(mdates.DateFormatter("%H"))

        # Keep hour labels horizontal
        plt.setp(ax_alt.get_xticklabels(which="major"), rotation=0, ha="center")

        plot_pane.object = fig
        plt.close(fig)

        def _instant_badge(is_ok: bool, t_ref: Time) -> tuple[str, str]:
            dt_str = t_ref.iso[:16]  # YYYY-MM-DD HH:MM
            if is_ok:
                return (
                    f"✔ Observable at {dt_str} UTC",
                    "#2e7d32",
                )
            else:
                return (
                    f"✖ Not observable at {dt_str} UTC",
                    "#b00020",
                )

        def _make_daily_stats_table(app_state: AppState, hours: int, minutes: int) -> str:
            obs = app_state.observability
            verdict_text, verdict_color = _instant_badge(is_observable_now, t_ref)

            color = "#2e7d32" if obs.is_observable else "#b00020"

            # Indices where target is observable
            idx = np.where(mask)[0]

            if len(idx) > 0:
                t_start_obs = times[idx[0]].to_datetime()
                t_end_obs = times[idx[-1]].to_datetime()

                start_str = t_start_obs.strftime("%H:%M")
                end_str = t_end_obs.strftime("%H:%M")

                time_window_str = f"(from {start_str} to {end_str} UT)"
            else:
                time_window_str = "(not observable)"

            return f"""
        ### Summary for Night Observability
        <span style="color:{verdict_color}; font-weight:bold;"> {verdict_text} </span>
        (altitude: **{alt_ref:.1f}°**, airmass: **{airmass_ref:.2f}**)
   
        **Total observable time:** **{hours} h {minutes} min** {time_window_str}

        During the night, the target reaches a **minimum airmass of {obs.min_airmass:.2f}**,  a **minimum Moon separation of {obs.min_moon_sep:.1f}°**,  with an **average Moon illumination of {obs.mean_fli:.2f}**

        **Night:**  
        Beginning: **{obs.night_start.iso[11:16]} UT**; End: **{obs.night_end.iso[11:16]} UT**  Total night duration: **{obs.night_duration.to_value(u.hour):.2f} h**
        """

        # ----------------------------
        # Statistics
        # ----------------------------
        total = obs.observable_time.to(u.minute)
        hours = int(total.to(u.hour).value)
        minutes = int((total - hours * u.hour).to(u.minute).value)

        stats_md.object = _make_daily_stats_table(app_state, hours, minutes)

    #note this does not update when refreence time is changed. For that to happen wt would have to be:
    # app_state.param.watch(
    #     update_daily_observability,
    #     ["observability", "reference_time"],
    # )
    app_state.param.watch(update_daily_observability, ["observability"])

    return make_display_tab(plot_pane, stats_md, "NightObs_plot.pdf", "NightObs_summary.txt")


#####

def make_monthly_observability_tab(app_state: AppState):

    plot_pane = pn.pane.Matplotlib(sizing_mode="stretch_both")
    stats_md = pn.pane.Markdown("### Monthly summary\nNo data yet.")

    def hours_since_night_start(times: Time, night_start: Time) -> np.ndarray:
        return (times - night_start).to_value(u.hour)

    def night_duration_hours(obs: ObservabilityResult) -> float:
        return obs.night_duration.to_value(u.hour)

    def update_monthly_observability(*_):
        multi = app_state.multi_night_observability
        if multi is None or not multi.nights:
            return

        ref_date = app_state.reference_time.to_datetime().date()

        ref_index = next(
            (
                i for i, n in enumerate(multi.nights)
                if n.date == ref_date
            ),
            None,
        )

        max_night = max(night_duration_hours(n.result) for n in multi.nights)

        fig, ax = plt.subplots(figsize=(9, 5), tight_layout=True)

        for x, night in enumerate(multi.nights):
            obs = night.result

            # Time grid relative to night start
            y = hours_since_night_start(obs.time_grid, obs.night_start)

            # Night shading (entire night)
            ax.vlines(
                x,
                0,
                night_duration_hours(obs),
                color="lightgrey",
                linewidth=10,
                alpha=0.4,
                zorder=1,
            )

            # Observable segments plotting
            night_len = night_duration_hours(obs)

            for j in range(len(y) - 1):
                if not obs.mask[j]:
                    continue

                y0 = y[j]
                y1 = y[j + 1]

                # Skip anything fully outside the night
                if y1 <= 0 or y0 >= night_len:
                    continue

                # Clip to night boundaries
                y0c = max(y0, 0.0)
                y1c = min(y1, night_len)

                ax.vlines(
                    x,
                    y0c,
                    y1c,
                    color="#2e7d32",
                    linewidth=6,
                    zorder=3,
                )


        ax.set_ylim(0, max_night)

        # X-axis: nights and their labeling
        x_positions = np.arange(len(multi.nights))
        label_positions = x_positions[::MONTH_XLABEL_STEP]

        ax.set_xticks(label_positions)
        ax.set_xticklabels(
            [multi.nights[i].date.isoformat() for i in label_positions],
            rotation=45,
            ha="right",
            fontsize=8,
        )

        # labeling tonight
        if ref_index is not None:
            ax.text(
                ref_index,
                0.5 * max_night,
                "Tonight",
                rotation=90,
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold",
                color="#1565c0",
                alpha=0.9,
                zorder=5,
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor="white",
                    edgecolor="#1565c0",
                    alpha=0.8,
                ),
            )

        ax.set_ylabel("Hours since night start", fontsize=9)
        ax.set_xlabel("Night", fontsize=9)

        plot_pane.object = fig
        plt.close(fig)

        def _make_monthly_stats_table(multi: MultiNightObservability) -> str:
            """
            Create a short textual summary for monthly observability.
            """

            nights = multi.nights

            # Nights with any observability
            observable_nights = [
                n for n in nights if n.result.observable_time > 0 * u.hour
            ]

            n_obs = len(observable_nights)
            n_total = len(nights)

            first_date = nights[0].date.isoformat()
            last_date = nights[-1].date.isoformat()

            if n_obs == 0:
                return f"""
        ### Summary for Monthly Observability

        - Observable nights: **0 / {n_total}**
        - The target is not observable on any night in this period.
        """

            # Extract observable hours per night
            obs_hours = np.array([
                n.result.observable_time.to_value(u.hour)
                for n in observable_nights
            ])

            mean_hours = obs_hours.mean()
            total_hours = obs_hours.sum()

            dates = [n.date for n in observable_nights]

            idx_min = int(np.argmin(obs_hours))
            idx_max = int(np.argmax(obs_hours))

            min_hours = obs_hours[idx_min]
            max_hours = obs_hours[idx_max]

            min_date = dates[idx_min].isoformat()
            max_date = dates[idx_max].isoformat()

            # Weather-loss statistics: Yearly average

            weather_line = ""

            inst = app_state.instrument
            weather_losses_mode = getattr(app_state, "weather_losses_mode", None)

            if (
                    weather_losses_mode == "Yearly average"
                    and inst is not None
                    and inst.weather_statistics is not None
            ):
                p = inst.weather_statistics.yearly_usable_fraction

                effective_nights = n_obs * p
                effective_hours = obs_hours.sum() * p

                weather_line = f"""
                
        - **Considering yearly-averaged weather losses:**  
        **{effective_nights:.1f} effective nights**, **{effective_hours:.1f} h total observable time**
        """

            return f"""
        ### Summary for Monthly Observability
        
        - **Observable nights:** **{n_obs} / {n_total}**  
          **Mean observable time per night:** **{mean_hours:.2f} h**  
          **Total observable time:** **{total_hours:.2f} h**  
          ({first_date} → {last_date})
        
        - **Maximum observable time:**  
          **{max_hours:.2f} h** on **{max_date}**
        
        - **Minimum observable time:**  
          **{min_hours:.2f} h** on **{min_date}**
        {weather_line}
        """

        stats_md.object = _make_monthly_stats_table(multi)

    app_state.param.watch(update_monthly_observability, ["multi_night_observability"])

    return make_display_tab(plot_pane, stats_md, "NightObs_plot.pdf", "NightObs_summary.txt")

#####

def make_planet_tab():
    return pn.Column(
        pn.widgets.FloatInput(name="Mass [MJup]"),
        pn.widgets.FloatInput(name="Orbital period []"),
    )

def make_rv_precision_tab():
    rv_output = pn.Column(
        pn.pane.Markdown(
            "### RV precision results\n(plots / tables will go here)",
        ),
        sizing_mode="stretch_both",
        styles={
            "flex": f"0 0 {DISPLAY_MAIN_FRACTION * 100:.0f}%",
        },
    )

    planet_controls = pn.Column(
        pn.pane.Markdown(
            "## Planet parameters",
        ),
        make_planet_tab(),
        sizing_mode="stretch_both",
        styles={
            "flex": f"0 0 {(1. - DISPLAY_MAIN_FRACTION) * 100:.0f}%",
        },
    )
    return pn.Column(
        rv_output,
        divider_h,
        planet_controls,
        sizing_mode="stretch_both",
    )


def make_output_dummy_tab(title: str):
    """Create a vertically split output tab with main view and statistics."""
    main_view = pn.Column(
        pn.pane.Markdown(f"### {title}\nMain results go here"),
        sizing_mode="stretch_both",
        styles={
            "flex": f"0 0 {DISPLAY_MAIN_FRACTION * 100:.0f}%",
        },
    )

    stats_view = pn.Column(
        pn.pane.Markdown(
            "### Statistics",
        ),
        pn.pane.Markdown("Statistics and summary metrics go here"),
        sizing_mode="stretch_both",
        styles={
            "flex": f"0 0 {(1. - DISPLAY_MAIN_FRACTION) * 100:.0f}%",
        },
    )

    return pn.Column(
        main_view,
        divider_h,
        stats_view,
        sizing_mode="stretch_both",
    )