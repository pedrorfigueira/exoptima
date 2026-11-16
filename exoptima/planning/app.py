import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for Panel/web rendering

import panel as pn

pn.config.respect_explicit_sizing = True

import warnings
from astropy.utils.exceptions import AstropyWarning
# Silence selected Astropy warnings
warnings.simplefilter("ignore", AstropyWarning)

from exoptima.planning.controls import make_control_tabs
from exoptima.planning.display import make_header, make_output_tabs
from exoptima.planning.state import AppState

from exoptima.core.observability import (
    recompute_observability,
    recompute_monthly_observability,
    recompute_yearly_observability,
)

from exoptima.core.precision import recompute_precision

from exoptima.tabs.components import make_main_layout

# ------------------------------------------------------------------
# Main application
# ------------------------------------------------------------------

def create_app():

    app_state = AppState()

    # --------------------------------------------------------------
    # Computation callbacks
    # --------------------------------------------------------------

    def _on_compute_obs(event=None):

        # Clear cached nights on compute, allowing parameter changes
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
    app_state.on_compute_precision = lambda: recompute_precision(app_state)

    # --------------------------------------------------------------
    # Interface
    # --------------------------------------------------------------

    header = make_header(app_state)
    app_state.header_pane = header

    left_tabs = make_control_tabs(app_state)
    right_tabs = make_output_tabs(app_state)

    main_layout = make_main_layout(
        header,
        left_tabs,
        right_tabs,
    )

    return main_layout


# ------------------------------------------------------------------
# Panel entry point
# ------------------------------------------------------------------

app = create_app()