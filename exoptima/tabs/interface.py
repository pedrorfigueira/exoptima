# full interface, putting together the header, control, and display
import panel as pn

from exoptima.core.state import AppState

from exoptima.config.layout import BUTTON_WIDTH, BUTTON_HEIGHT

from exoptima.tabs.controls import (
    make_star_tab, make_instrument_tab, make_observing_conditions_tab, make_planet_rv_tab, make_time_integration_tab)
from exoptima.tabs.display import (
    make_daily_observability_tab, make_monthly_observability_tab, make_yearly_observability_tab,
    make_precision_tab)

# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------

def load_svg(name: str) -> str:
    """Load an SVG asset as a string."""
    from importlib import resources
    logo_path = resources.files("exoptima").joinpath(f"assets/{name}")
    return logo_path.read_text(encoding="utf-8")


def make_header(app_state: AppState):
    OPT_ICON_SVG = load_svg("exoptima-alogo.svg")

    # ---------------------------------
    # Scope selector
    # ---------------------------------
    scope_select = pn.widgets.RadioButtonGroup(
        name="Observability scope",
        options=["Night", "Month", "Year"],
        value="Night",
        button_type="default",
    )

    # Store selection in state
    def _on_scope_change(event):
        app_state.observability_scope = event.new

    scope_select.param.watch(_on_scope_change, "value")

    # ---------------------------------
    # Buttons
    # ---------------------------------
    compute_obs_button = pn.widgets.Button(
        name="Compute Observability",
        button_type="success",
        width=BUTTON_WIDTH,
        height=BUTTON_HEIGHT,
        disabled=True,
    )

    def _on_click_compobs(event=None):
        if app_state.on_compute_observability is not None:
            app_state.on_compute_observability()

    compute_obs_button.on_click(_on_click_compobs)

    compute_prec_button = pn.widgets.Button(
        name="Compute Precision",
        button_type="warning",
        width=BUTTON_WIDTH,
        height=BUTTON_HEIGHT,
        disabled=True,
    )

    def _on_click_compprec(event=None):
        if app_state.on_compute_precision is not None:
            app_state.on_compute_precision()

    compute_prec_button.on_click(_on_click_compprec)

    # ----------------------------------
    # Observability computing status bar
    # ----------------------------------

    status_md = pn.pane.Markdown(
        "",
        styles={
            "color": "#1565c0",
            "font-weight": "bold",
            "font-size": "11px",
            "margin-top": "6px",
        },
        width=BUTTON_WIDTH,
        height=BUTTON_HEIGHT,
    )

    def _update_status(*_):
        if app_state.is_computing_observability:
            status_md.object = "🔭 Computing observability…"
        elif app_state.is_computing_precision:
            status_md.object = "🎯 Computing precision…"
        else:
            status_md.object = ""

    app_state.param.watch(_update_status, ["is_computing_observability", "is_computing_precision"])

    # ------------------------------------------
    # Display Observability / Precision  params
    # ------------------------------------------
    def _make_observability_context_md(app_state: AppState) -> str:
        if app_state.observability is None:
            return ""  # empty until Compute Observability is run

        star = app_state.star
        inst = app_state.instrument
        c = app_state.conditions
        pp = app_state.planet_params

        ref_time_str = app_state.reference_time.iso[:16] + " UTC"

        # --------------------------------------------------
        # Transit column logic
        # --------------------------------------------------

        include_transit = (
                pp is not None and getattr(pp, "include_transit_in_observability", False)
        )

        if include_transit:
            # T0
            if pp.t0_jd is not None:
                t0_str = f"{pp.t0_jd:.5f}"
            else:
                t0_str = "--"

            # Period
            if pp.orbital_period_days is not None:
                period_str = f"{pp.orbital_period_days:.3g} d"
            else:
                period_str = "--"

            # Duration
            if pp.total_observation_duration is not None:
                dur_str = f"{pp.total_observation_duration:.2f} h"
            else:
                dur_str = "--"

            transit_cell = f"T0={t0_str}<br>P={period_str}<br>Dur={dur_str}"

            header_extra = " | Transit constraint |"
            sep_extra = " |:-----------------:|"
            row_extra = f" | {transit_cell} |"
        else:
            header_extra = ""
            sep_extra = ""
            row_extra = ""

        # --------------------------------------------------
        # Build table
        # --------------------------------------------------

        return f"""
    | Target | RA (α) | Dec (δ) | Observatory | Weather losses | Airmass (max value, min dur.) | Moon (sep, Min FLI) | Night def. | Reference time{header_extra}
    |:------:|:------:|:-------:|:-----------:|:--------------:|:-----------------------------:|:-------------------:|:----------:|:--------------:{sep_extra}
    | **{star.name}** | {star.ra} | {star.dec} | {inst.observatory.name} | {app_state.weather_losses_mode} | < {c.max_airmass} for {c.min_duration} | {c.min_moon_separation}° if > {c.ignore_moon_if_fli_above} | {app_state.night_definition} | {ref_time_str}{row_extra}
    """

    context_md = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
    )

    def _make_precision_context_md(app_state: AppState) -> str:
        if app_state.star is None or app_state.instrument is None:
            return ""

        star = app_state.star
        inst = app_state.instrument
        exptime = app_state.exposure_time
        pp = app_state.planet_params

        # ---------------------------------
        # Exposure time
        # ---------------------------------
        exptime_str = f"{exptime:.0f} s" if exptime is not None else "--"

        # ---------------------------------
        # Planet parameters (with fallback)
        # ---------------------------------
        if pp is not None and pp.planet_mass_mjup is not None:
            planet_mass_str = f"{pp.planet_mass_mjup:.3g}"
        else:
            planet_mass_str = "--"

        if pp is not None and pp.orbital_period_days is not None:
            period_str = f"{pp.orbital_period_days:.3g}"
        else:
            period_str = "--"

        if pp is not None and pp.stellar_mass_msun is not None:
            stellar_mass_str = f"{pp.stellar_mass_msun:.3g}"
        else:
            stellar_mass_str = "--"

        # ---------------------------------
        # Build Markdown table
        # ---------------------------------
        return f"""
    | V mag | SpTp | Instrument | Exp. time | Mp [MJup] | P [days] | M⋆ [MSun] |
    |:-----:|:----:|:----------:|:---------:|:---------:|:--------:|:---------:|
    | **{star.vmag:.2f}** | **{star.sptype}** | **{inst.name}** | **{exptime_str}** | **{planet_mass_str}** | **{period_str}** | **{stellar_mass_str}** |
    """

    # ---------------------------------
    # enable/disable compute buttons
    # ---------------------------------
    def _update_buttons(*_):
        compute_obs_button.disabled = (
                not app_state.star_coords_valid
                or app_state.is_computing_observability
        )

        compute_prec_button.disabled = (
                not app_state.star_vmag_defined
                or app_state.is_computing_precision
        )

    app_state.param.watch(
        _update_buttons,
        ["star_coords_valid", "star_vmag_defined", "is_computing_observability", "is_computing_precision"],
    )

    def _update_context(event):
        if event.name == "observability":
            context_md.object = _make_observability_context_md(app_state)

        elif event.name == "precision_result":
            context_md.object = _make_precision_context_md(app_state)

    app_state.param.watch(_update_context, ["observability", "precision_result"])

    # ---------------------------------
    # Layout
    # ---------------------------------
    title = pn.Column(
        pn.pane.HTML("<h2> EXOPTIMA <br> an <i>EXOTICA</i> tool </h2>"),
    )

    return pn.Row(
        pn.pane.SVG(OPT_ICON_SVG, width=80, height=80),
        title,
        pn.Spacer(width=20),
        pn.Column(
            pn.Spacer(height=10),
            pn.Row(compute_obs_button, compute_prec_button),
            pn.Spacer(height=8),
            pn.Row(scope_select, status_md),
        ),
        pn.Spacer(width=30),
        pn.Column(
            pn.Spacer(height=20),
            context_md,
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )

def make_control_tabs(app_state: AppState):
    return pn.Tabs(
        ("Star", make_star_tab(app_state)),
        ("Instrument", make_instrument_tab(app_state)),
        ("Conditions", make_observing_conditions_tab(app_state)),
        ("Time & Integration", make_time_integration_tab(app_state)),
        ("Planet parameters", make_planet_rv_tab(app_state)),
        sizing_mode="stretch_width",
    )


def make_output_tabs(app_state: AppState):
    daily = make_daily_observability_tab(app_state)
    monthly = make_monthly_observability_tab(app_state)
    yearly = make_yearly_observability_tab(app_state)
    precision = make_precision_tab(app_state)

    tabs = pn.Tabs(
        ("Daily Observability", daily),
        ("Monthly Observability", monthly),
        ("Yearly Observability", yearly),
        ("RV precision", precision),
        sizing_mode="stretch_both",
    )

    return tabs
