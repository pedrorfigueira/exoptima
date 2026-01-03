# plot/summary export utilities

import panel as pn
from pathlib import Path

def export_matplotlib_button(
    plot_pane: pn.pane.Matplotlib,
    filename: str,
):
    btn = pn.widgets.Button(
        name="Export PDF",
        button_type="default",
        width=90,
    )

    def _export(_):
        fig = plot_pane.object
        if fig is None:
            return
        fig.savefig(filename, bbox_inches="tight")

    btn.on_click(_export)

    return btn

def export_markdown_button(
    md_pane: pn.pane.Markdown,
    filename: str,
):
    btn = pn.widgets.Button(
        name="Export TXT",
        button_type="default",
        width=90,
    )

    def _export(_):
        if not md_pane.object:
            return
        Path(filename).write_text(md_pane.object)

    btn.on_click(_export)

    return btn

def make_save_button(pane, filename):
    # slightly different orientations / page organization for the top and bottom buttons
    if filename.endswith(".pdf"):
        button = export_matplotlib_button(pane, filename)
        return pn.Column(
            pn.Row(
                pn.layout.HSpacer(),
                button,
                sizing_mode="stretch_width",
            ),
            pn.Spacer(height=4),  # to prevent compression artifacts
            pane,
            sizing_mode="stretch_both",
        )

    elif filename.endswith(".txt"):
        button = export_markdown_button(pane, filename)
        return pn.Row(
            pane,
            pn.layout.HSpacer(),
            pn.Column(
                button,
                align="start",          # top-align vertically
            ),
            align="start",              # top-align row contents
            sizing_mode="stretch_width",
        )
    else:
        raise ValueError("Unsupported export format")


