import panel as pn
pn.extension()

from astropy import units as u

from exoptima.config.layout import HEADER_SPACING, CONTROLS_PANEL_FRACTION

from exoptima.tabs.interface import (
    make_header, make_control_tabs, make_output_tabs)

from exoptima.core.observability import (
    recompute_observability, recompute_monthly_observability, recompute_yearly_observability)

from exoptima.core.state import AppState
app_state = AppState()

from exoptima.config.instruments import INSTRUMENTS
instrument = INSTRUMENTS["HARPS"]

import warnings
from astropy.utils.exceptions import AstropyWarning
# to silence the warnings
# "Angular separation can depend on the direction of the transformation. [astropy.coordinates.baseframe]"
warnings.simplefilter("ignore", AstropyWarning)

# ------------------------------------------------------------------
# Main application
# ------------------------------------------------------------------

def create_app():
    header = make_header(app_state)

    left_tabs = make_control_tabs(app_state)
    right_tabs = make_output_tabs(app_state)

    left_panel = pn.Column(
        left_tabs,
        sizing_mode="stretch_both",
        styles={
            "flex": f"0 0 {CONTROLS_PANEL_FRACTION * 100:.0f}%",
        },
    )

    divider_v = pn.Spacer(
        width=1,
        sizing_mode="stretch_height",
        styles={
            "background-color": "#e0e0e0",
        },
    )

    right_panel = pn.Column(
        right_tabs,
        sizing_mode="stretch_both",
        styles={
            "flex": f"0 0 {(1. - CONTROLS_PANEL_FRACTION) * 100:.0f}%",
        },
    )

    return pn.Column(
        header,
        pn.Spacer(height=HEADER_SPACING),
        pn.Row(
            left_panel,
            divider_v,
            right_panel,
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_both",
    )

def _on_compute_obs(event=None):
    # Clear cached nights on compute, allowing parameter change
    app_state.night_cache.clear()

    app_state.is_computing_observability = True

    try:
        recompute_observability(app_state)

        if app_state.observability_scope in ("Month", "Year"):
            recompute_monthly_observability(app_state)

        if app_state.observability_scope == "Year":
            recompute_yearly_observability(app_state)
    finally:
        app_state.is_computing_observability = False

app_state.on_compute_observability = _on_compute_obs

# ------------------------------------------------------------------
# Panel entry point
# ------------------------------------------------------------------

app = create_app()
