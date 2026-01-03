
from pathlib import Path
import panel as pn
pn.extension()

from exoptima.core.state import AppState

from exoptima.config.layout import BUTTON_WIDTH, BUTTON_HEIGHT

from exoptima.tabs.controls import (
    make_star_tab, make_instrument_tab, make_observing_conditions_tab, make_time_tab, make_planet_rv_tab)
from exoptima.tabs.display import make_daily_observability_tab, make_output_tab

# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------

def load_svg(name: str) -> str:
    """Load an SVG asset as a string."""
    assets_dir = Path(__file__).parent / ".." / "assets"
    return (assets_dir / name).read_text(encoding="utf-8")


def make_header(app_state: AppState):
    OPT_ICON_SVG = load_svg("exoptima-alogo.svg")

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

    # ---------------------------------
    # Reactive enable/disable
    # ---------------------------------

    def _update_buttons(*_):
        compute_obs_button.disabled = not app_state.star_coords_valid
        compute_prec_button.disabled = not app_state.star_vmag_defined

    app_state.param.watch(_update_buttons, ["star_coords_valid", "star_vmag_defined"])

    title = pn.Column(
        pn.pane.HTML("<h2> EXOPTIMA <br> an <i>EXOTICA</i> tool </h2>"),
    )

    return pn.Row(
        pn.pane.SVG(OPT_ICON_SVG, width=80, height=80),
        title,
        pn.Spacer(width=20),
        pn.Column(pn.Spacer(height=20),
        pn.Row(compute_obs_button,compute_prec_button)),
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
        ("Daily Obs.", make_daily_observability_tab(app_state)),
        ("Monthly Obs.", make_output_tab("Monthly observations")),
        ("Yearly Obs.", make_output_tab("Yearly observations")),
        ("RV precision", make_output_tab("RV precision")),
        sizing_mode="stretch_both",
    )