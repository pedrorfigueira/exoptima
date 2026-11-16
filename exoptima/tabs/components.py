# simple support tools and functions for use in tabs and diplay

import panel as pn
from pathlib import Path

from exoptima.config.layout import (
    HEADER_SPACING,
    CONTROLS_PANEL_FRACTION,
    BUTTON_WIDTH,
    BUTTON_HEIGHT,
)

########################################################################################################################
# Layout tools
########################################################################################################################

def load_svg(name: str) -> str:
    """Load an SVG asset as a string."""
    from importlib import resources
    logo_path = resources.files("exoptima").joinpath(f"assets/{name}")
    return logo_path.read_text(encoding="utf-8")

def make_app_title(mode: str):
    """Create the application logo and title for the selected mode."""

    if mode not in ("planning", "scheduling"):
        raise ValueError("mode must be 'planning' or 'scheduling'")

    icon_svg = load_svg("exoptima-alogo.svg")

    title = pn.Column(
        pn.pane.HTML(
            f"""
            <div style="line-height: 1.1;">
                <h2 style="margin: 0;">EXOPTIMA</h2>
                <div style="font-size: 0.85em; color: #666; margin-top: 2px;">
                    {mode.capitalize()} mode
                </div>
            </div>
            """
        )
    )

    return pn.Row(
        pn.pane.SVG(icon_svg, width=80, height=80),
        pn.Column(
            pn.Spacer(height=25),
            title,
        ),
    )

def make_divider():
    """Draw horizontal division bar."""
    return pn.Spacer(
        height=1,
        sizing_mode="stretch_width",
        styles={"background-color": "#e0e0e0"},
    )


def mark_section_recalculation_needed(app_state, section_key: str):
    """Mark one control section as the source of pending recalculation."""
    sections = getattr(app_state, "_recalculation_sections", set())
    sections.add(section_key)
    app_state._recalculation_sections = sections

    # This helper also sets the global flag, so callers do not need to
    # remember to do it separately.
    app_state.needs_recalculation = True

    # If the global flag was already True, its watcher will not fire again;
    # update this section's indicator explicitly as well.
    panes = getattr(app_state, "_recalculation_status_panes", {})
    pane = panes.get(section_key)
    if pane is not None:
        pane.visible = True


def make_recalculation_banner(app_state, section_key: str | None = None):
    """Create the standard recalculation banner.

    If section_key is provided, show it only when that section triggered the
    pending recalculation. Otherwise, show it for any pending recalculation.
    """
    status_pane = pn.pane.HTML(
        """
        <span style="
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            background-color: #f5a623;
            color: #382400;
            font-size: 0.78em;
            font-weight: 600;
            white-space: nowrap;
            margin-top: 6px;
        ">Recalculation needed</span>
        """,
        visible=(
            bool(app_state.needs_recalculation)
            and (
                section_key is None
                or section_key in getattr(app_state, "_recalculation_sections", set())
            )
        ),
    )

    if section_key is not None:
        panes = getattr(app_state, "_recalculation_status_panes", {})
        panes[section_key] = status_pane
        app_state._recalculation_status_panes = panes

    def update_status(event):
        sections = getattr(app_state, "_recalculation_sections", set())
        status_pane.visible = bool(
            event.new
            and (
                section_key is None
                or section_key in sections
            )
        )
        if not event.new:
            # A successful recalculation clears the pending section markers.
            app_state._recalculation_sections = set()

    app_state.param.watch(update_status, "needs_recalculation")
    return status_pane


def make_section_header(title: str, app_state, section_key: str):
    """Create a section title with its own recalculation-needed indicator."""
    title_pane = pn.pane.HTML(
        f"<div style='font-size: 1.3em;'>{title}</div>"
    )
    status_pane = make_recalculation_banner(app_state, section_key)
    status_pane.margin = (0, 0, 0, 10)

    return pn.Row(
        title_pane,
        status_pane,
        align="center",
        sizing_mode="stretch_width",
    )


def make_main_layout(header, left_tabs, right_tabs):
    """Build the main application layout from its components."""

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
            sizing_mode="stretch_both",
        ),
        sizing_mode="stretch_both",
    )


def format_field(step):
    """Return a numeric format string matching the precision of step."""
    decimals = len(str(step).partition(".")[2])
    return f"0.{decimals * '0'}" if decimals else "0"


def make_file_io_controls(
    directory_name: str,
    default_directory: Path,
    show_save_button: bool = True,
    show_load_all_button: bool = False,
):
    """Create reusable file input/output controls."""

    working_dir = pn.widgets.TextInput(
        name=directory_name,
        value=str(default_directory),
        sizing_mode="stretch_width",
    )

    file_filter = pn.widgets.TextInput(
        name="File filter",
        value="*.json",
        width=BUTTON_WIDTH,
    )

    refresh_button = pn.widgets.Button(
        name="Refresh",
        button_type="default",
        styles={"margin-top": "20px"},
        width=BUTTON_WIDTH // 2,
        height=BUTTON_HEIGHT,
    )

    file_list = pn.GridBox(
        ncols=3,
        sizing_mode="stretch_width",
        styles={"gap": "3px"},
    )

    file_list_frame = pn.Column(
        pn.pane.HTML(
            "<div style='font-weight: normal; padding-bottom: 5px;'>"
            "Available files"
            "</div>"
        ),
        file_list,
        sizing_mode="stretch_width",
        styles={
            "border": "1px solid #cccccc",
            "border-radius": "5px",
            "padding": "8px",
            "background": "white",
        },
    )

    file_name = pn.widgets.TextInput(
        name="File name",
        value="example_input.json",
        sizing_mode="stretch_width",
    )

    save_button = pn.widgets.Button(
        name="Save",
        button_type="primary",
        width=BUTTON_WIDTH // 2,
        height=BUTTON_HEIGHT,
    )

    load_button = pn.widgets.Button(
        name="Load",
        button_type="success",
        width=BUTTON_WIDTH // 2,
        height=BUTTON_HEIGHT,
    )

    load_all_button = pn.widgets.Button(
        name="Load all",
        button_type="warning",
        width=BUTTON_WIDTH // 2,
        height=BUTTON_HEIGHT,
        disabled=True,
    )

    # --------------------------------------------------
    # File list
    # --------------------------------------------------

    def refresh_file_list(event=None):
        """Refresh the list of files matching the current filter."""

        file_list.objects = []

        try:
            directory = Path(working_dir.value).expanduser()

            if not directory.is_dir():
                file_list.objects = [
                    pn.pane.Markdown("Directory does not exist.")
                ]
                load_all_button.disabled = True
                return

            pattern = file_filter.value.strip() or "*.json"

            files = sorted(
                path for path in directory.glob(pattern)
                if path.is_file()
            )

            if not files:
                file_list.objects = [
                    pn.pane.Markdown("No matching files found.")
                ]
                load_all_button.disabled = True
                return

            buttons = []

            for path in files:
                button = pn.widgets.Button(
                    name=path.name,
                    button_type="light",
                    sizing_mode="stretch_width",
                    height=BUTTON_HEIGHT,
                    styles={
                        "font-size": "11px",
                        "text-align": "left",
                    },
                )

                button.on_click(
                    lambda event, filename=path.name:
                        setattr(file_name, "value", filename)
                )

                buttons.append(button)

            file_list.objects = buttons
            load_all_button.disabled = not show_load_all_button

        except Exception as exc:
            file_list.objects = [
                pn.pane.Markdown(f"Could not list files: `{exc}`")
            ]
            load_all_button.disabled = True

    refresh_button.on_click(refresh_file_list)
    refresh_file_list()

    # --------------------------------------------------
    # Layout
    # --------------------------------------------------

    buttons = [load_button]

    if show_load_all_button:
        buttons.append(load_all_button)

    if show_save_button:
        buttons.insert(0, save_button)

    layout = pn.Column(
        working_dir,
        pn.Row(
            file_filter,
            refresh_button,
            sizing_mode="stretch_width",
        ),
        file_list_frame,
        pn.Spacer(height=10),
        file_name,
        pn.Row(*buttons),
        sizing_mode="stretch_width",
    )

    widgets = {
        "working_dir": working_dir,
        "file_filter": file_filter,
        "refresh_button": refresh_button,
        "file_list": file_list,
        "file_name": file_name,
        "save_button": save_button,
        "load_button": load_button,
        "load_all_button": load_all_button,
        "refresh_file_list": refresh_file_list,
    }

    return layout, widgets