# plot/summary export utilities

import panel as pn
from pathlib import Path


def _extract_header_text(layout):
    """
    Extract ONLY Markdown panes from header.
    """

    text = ""

    if isinstance(layout, pn.pane.Markdown):
        if layout.object:
            text += str(layout.object) + "\n"

    elif hasattr(layout, "objects"):
        for obj in layout.objects:
            text += _extract_header_text(obj)

    return text.strip()


def _format_markdown_as_report(md_text: str) -> str:
    import re

    lines = md_text.splitlines()
    out = []

    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()

        # ----------------------------
        # Empty line
        # ----------------------------
        if not line:
            out.append("")
            i += 1
            continue

        # ----------------------------
        # Remove HTML tags
        # ----------------------------
        line = re.sub(r"<.*?>", "", line)

        # ----------------------------
        # Headers
        # ----------------------------
        if line.startswith("###"):
            title = line.replace("#", "").strip().upper()
            sep = "=" * max(len(title), 50)

            out.append("")
            out.append(sep)
            out.append(title)
            out.append(sep)
            out.append("")
            i += 1
            continue

        # ----------------------------
        # Markdown table detection
        # ----------------------------
        if line.startswith("|") and i + 1 < n and lines[i + 1].strip().startswith("|:"):

            # collect table lines
            table_lines = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1

            # parse rows
            rows = []
            for tl in table_lines:
                cells = [re.sub(r"\*\*(.*?)\*\*", r"\1", c.strip()) for c in tl.strip("|").split("|")]
                rows.append(cells)

            header = rows[0]
            data = rows[2:] if len(rows) > 2 else []

            # column widths
            widths = [len(h) for h in header]
            for row in data:
                for j, cell in enumerate(row):
                    widths[j] = max(widths[j], len(cell))

            # build table
            def fmt_row(row):
                return " | ".join(f"{cell:<{widths[j]}}" for j, cell in enumerate(row))

            sep = " | ".join("-" * w for w in widths)

            out.append(fmt_row(header))
            out.append(sep)

            for row in data:
                out.append(fmt_row(row))

            out.append("")
            continue

        # ----------------------------
        # Bullet points
        # ----------------------------
        if line.startswith("- "):
            content = line[2:]
            content = re.sub(r"\*\*(.*?)\*\*", r"\1", content)

            if ":" in content:
                key, val = content.split(":", 1)
                out.append(f"{key.strip():<28} : {val.strip()}")
            else:
                out.append(content)

            i += 1
            continue

        # ----------------------------
        # Bold cleanup
        # ----------------------------
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)

        out.append(line)
        i += 1

    return "\n".join(out).strip()


def make_save_button(pane, filename, header_pane=None):

    # ----------------------------
    # Plot export (PDF / PNG)
    # ----------------------------
    if isinstance(pane, pn.pane.Matplotlib):

        base = Path(filename).stem

        format_select = pn.widgets.Select(
            options={"PDF": "pdf", "PNG": "png"},
            value="pdf",
            width=70,
        )

        export_btn = pn.widgets.Button(
            name="Export",
            button_type="default",
            width=70,
        )

        def _export(_):
            fig = pane.object
            if fig is None:
                return

            fmt = format_select.value
            fig.savefig(f"{base}.{fmt}", bbox_inches="tight", dpi=300)

        export_btn.on_click(_export)

        controls = pn.Row(format_select, export_btn)

        return pn.Column(
            pn.Row(
                pn.layout.HSpacer(),
                controls,
                sizing_mode="stretch_width",
            ),
            pn.Spacer(height=4),
            pane,
            sizing_mode="stretch_both",
        )

    # ----------------------------
    # Summary export (TXT only)
    # ----------------------------
    elif isinstance(pane, pn.pane.Markdown):

        include_conditions = pn.widgets.Switch(
            name="Conditions",
            value=True,
        )

        export_btn = pn.widgets.Button(
            name="Export TXT",
            button_type="default",
            width=90,
        )

        def _export(_):
            raw_text = pane.object or ""
            text = _format_markdown_as_report(raw_text)

            if include_conditions.value and header_pane is not None:
                header_text = _extract_header_text(header_pane)
                header_text = _format_markdown_as_report(header_text)

                if header_text:
                    text = header_text + "\n\n" + text

            Path(filename).write_text(text)

        export_btn.on_click(_export)

        return pn.Row(
            pane,
            pn.layout.HSpacer(),
            pn.Column(include_conditions, export_btn, align="start"),
            align="start",
            sizing_mode="stretch_width",
        )

