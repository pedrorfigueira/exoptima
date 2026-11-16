import panel as pn

from exoptima.scheduling.controls import make_control_tabs
from exoptima.scheduling.display import make_header, make_output_tabs
from exoptima.scheduling.state import SchedulingState

from exoptima.tabs.components import make_main_layout

from exoptima.scheduling.targets import recalculate_queue


# ------------------------------------------------------------------
# Main application
# ------------------------------------------------------------------

def create_app():

    app_state = SchedulingState()

    # --------------------------------------------------------------
    # Interface
    # --------------------------------------------------------------

    header = make_header(
        app_state,
        on_recalculate=lambda event: recalculate_queue(app_state),
    )
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