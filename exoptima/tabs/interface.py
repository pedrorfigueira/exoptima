
from pathlib import Path
import panel as pn
pn.extension()

from exoptima.core.state import AppState

from exoptima.config.layout import BUTTON_WIDTH, BUTTON_HEIGHT

from exoptima.tabs.controls import (
    make_star_tab, make_instrument_tab, make_observing_conditions_tab, make_planet_rv_tab)
from exoptima.tabs.display import (
    make_daily_observability_tab, make_monthly_observability_tab, make_yearly_observability_tab, make_output_dummy_tab)

# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------

def load_svg(name: str) -> str:
    """Load an SVG asset as a string."""
    assets_dir = Path(__file__).parent / ".." / "assets"
    return (assets_dir / name).read_text(encoding="utf-8")


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

    def _on_click(event=None):
        if app_state.on_compute_observability is not None:
            app_state.on_compute_observability()

    compute_obs_button.on_click(_on_click)

    compute_prec_button = pn.widgets.Button(
        name="Compute Precision",
        button_type="warning",
        width=BUTTON_WIDTH,
        height=BUTTON_HEIGHT,
        disabled=True,
    )

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
            status_md.object = "🔄 Computing observability…"
        else:
            status_md.object = ""

    app_state.param.watch(_update_status, ["is_computing_observability"])

    # ---------------------------------
    # Display Obs. params
    # ---------------------------------
    def _make_observability_context_md(app_state: AppState) -> str:
        if app_state.observability is None:
            return ""  # empty until Compute Observability is run

        star = app_state.star
        inst = app_state.instrument
        c = app_state.conditions

        ref_time_str = app_state.reference_time.iso[:16] + " UTC"

        return f"""
        | Target | RA (α) | Dec (δ) | Observatory | Weather losses | Airmass (max value, min dur.) | Moon (sep, Min FLI) | Night def. | Reference time |
        |:------:|:------:|:-------:|:-----------:|:--------------:|:-----------------------------:|:-------------------:|:----------:|:--------------:|
        | **{star.name}** | {star.ra} | {star.dec} | {inst.observatory.name} | {app_state.weather_losses_mode} | < {c.max_airmass} for {c.min_duration} | {c.min_moon_separation}° if > {c.ignore_moon_if_fli_above} | {app_state.night_definition} | {ref_time_str} |
        """

    context_md = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
    )

    # ---------------------------------
    # Reactive enable/disable
    # ---------------------------------
    def _update_buttons(*_):
        compute_obs_button.disabled = not app_state.star_coords_valid
        compute_prec_button.disabled = not app_state.star_vmag_defined

    app_state.param.watch(_update_buttons, ["star_coords_valid", "star_vmag_defined"])

    def _update_context(*_):
        context_md.object = _make_observability_context_md(app_state)

    app_state.param.watch(
        _update_context,
        ["observability"],  # ← only after a computation is requested, not after parameter changes
    )

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


# Custom divider

divider_h = pn.Spacer(
    height=1,
    sizing_mode="stretch_width",
    styles={"background-color": "#e0e0e0"},
)

def make_control_tabs(app_state: AppState):
    return pn.Tabs(
        ("Star", make_star_tab(app_state)),
        ("Instrument", make_instrument_tab(app_state)),
        ("Conditions", make_observing_conditions_tab(app_state)),
        ("Planet & RVs", make_planet_rv_tab(app_state)),
        sizing_mode="stretch_width",
    )



def make_output_tabs(app_state: AppState):
    return pn.Tabs(
        ("Daily Observability", make_daily_observability_tab(app_state)),
        ("Monthly Observability", make_monthly_observability_tab(app_state)),
        ("Yearly Observability", make_yearly_observability_tab(app_state)),
        ("RV precision", make_output_dummy_tab("RV precision")),
        sizing_mode="stretch_both",
    )