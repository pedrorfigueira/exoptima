import param


class SchedulingState(param.Parameterized):
    """State of the Scheduling application."""

    # Queue-level configuration
    instrument = param.String(default=None, allow_None=True)
    telescope = param.String(default=None, allow_None=True)
    night = param.String(default=None, allow_None=True)
    night_definition = param.String(default=None, allow_None=True)
    observing_period = param.String(default="Full night")
    custom_start_hours = param.Number(default=0.0, bounds=(0, None))
    custom_duration_hours = param.Number(default=1.0, bounds=(0, None))
    queue_config = param.Dict(default={})

    # Observation queue: current user inputs
    queue = param.List(default=[])

    # Last successfully calculated queue
    calculated_queue = param.List(default=[])

    # Whether the current inputs require recalculation
    needs_recalculation = param.Boolean(default=False)

    # Parameters common to all targets currently in the queue
    common_parameters = param.Dict(default=None, allow_None=True)

    # Currently selected target in the queue
    selected_target = param.String(default=None, allow_None=True)

    # Header pane
    header_pane = param.Parameter(default=None, allow_None=True)
    header_context_pane = param.Parameter(default=None, allow_None=True)