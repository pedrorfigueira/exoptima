# Control (input) section and tab definitions

import math
import panel as pn
import numpy as np
import json

from pathlib import Path
from datetime import datetime

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astroquery.simbad import Simbad, conf as simbad_conf

from exoptima.config.layout import FORM_WIDGET_WIDTH, BUTTON_WIDTH, BUTTON_HEIGHT
from exoptima.config.computation import (
    DEFAULT_SPTYPE, VALID_SPTYPES, VALID_NIGHT_DEFINITIONS,
    STEP_VMAG, STEP_EXPOSURE_TIME,
    STEP_MAX_AIRMASS, STEP_MIN_DURATION_HOUR,
    STEP_MIN_MOON_SEP, STEP_IGNORE_MOON_FLI,
    STEP_SEEING_ARCSEC, STEP_AIRMASS_RV,
)
from exoptima.config.instruments import INSTRUMENTS
from exoptima.config.paths import DEFAULT_TARGETS_DIR

from exoptima.core.services import (
    create_simbad_client,
    get_simbad_url,
)

from exoptima.planning.state import (
    AppState, Star, PlanetParameters, ObservingConditions
)

from exoptima.tabs.components import make_divider, make_file_io_controls, format_field


# ----- helper functions -----

import re

def map_simbad_sptype_to_model(sptype: str) -> str | None:
    """
    Map a SIMBAD spectral type string to the nearest available RV mask.

    Available masks
    ---------------
    ["G2", "K2", "M2"]

    Rules
    -----
    - F, G  -> G2
    - K     -> K2
    - M     -> M2
    - A/B/O and non-stellar / unsupported -> None

    Parameters
    ----------
    sptype : str
        SIMBAD spectral type string, e.g. "G8V", "K7III", "M3", "F9V"

    Returns
    -------
    str or None
        One of ["G2", "K2", "M2"], or None if unsupported.
    """
    if not sptype:
        return None

    s = str(sptype).strip().upper()

    # Extract leading spectral class and optional subtype digit
    m = re.match(r"^([OBAFGKM])\s*([0-9]?)", s)
    if not m:
        return None

    spec_class = m.group(1)
    subtype = int(m.group(2)) if m.group(2).isdigit() else None

    # Unsupported hot stars for RV masks
    if spec_class in ("O", "B", "A"):
        return None

    # F stars are best approximated by G2
    if spec_class == "F":
        return "G2"

    if spec_class == "G":
        # Late G is closer to K2
        if subtype is not None and subtype >= 8:
            return "K2"
        return "G2"

    if spec_class == "K":
        return "K2"

    if spec_class == "M":
        return "M2"

    return None


def validate_coordinates(ra_str: str, dec_str: str) -> tuple[bool, str | None]:
    """
    Validate RA / Dec strings using astropy.

    Returns
    -------
    (is_valid, error_message)
    """
    try:
        SkyCoord(ra=ra_str, dec=dec_str, unit=(u.hourangle, u.deg))
        return True, None
    except Exception as e:
        return False, str(e)


# ----- Tabs -----

def make_star_tab(app_state: AppState):
    # =================================================
    # Widgets
    # =================================================

    star_name = pn.widgets.TextInput(
        name="Star name",
        placeholder="Type for Simbad id query",
        width=FORM_WIDGET_WIDTH,
        styles={"font-size": "1.3em"},
    )

    resolve_button = pn.widgets.Button(
        name="Resolve",
        button_type="primary",
        styles={"margin-top": "24px"},
        width=BUTTON_WIDTH,
        height=BUTTON_HEIGHT,
    )

    ra = pn.widgets.TextInput(
        name="Alpha (RA)",
        placeholder="00:00:00",
        width=FORM_WIDGET_WIDTH // 2,
    )

    dec = pn.widgets.TextInput(
        name="Delta (Dec)",
        placeholder="+00:00:00",
        width=FORM_WIDGET_WIDTH // 2,
    )

    coord_status = pn.pane.Markdown(
        "",
        styles={"color": "#b00020"},
        margin=(4, 0, 0, 0),
    )

    vmag = pn.widgets.FloatInput(
        name="V mag",
        value=None,
        step=STEP_VMAG,
        format=format_field(STEP_VMAG),
        width=FORM_WIDGET_WIDTH // 2,
    )

    sp_type = pn.widgets.Select(
        name="SpType (model)",
        options=VALID_SPTYPES,
        value=DEFAULT_SPTYPE,
        width=FORM_WIDGET_WIDTH // 2,
    )

    sp_type_simbad = pn.pane.Markdown(
        "",
        margin=(22, 0, 0, 8),
        styles={"color": "#666"},
    )

    status = pn.pane.Markdown(
        "",
        styles={"color": "#666"},
        margin=(6, 0, 0, 0),
    )

    # =================================================
    # Helpers
    # =================================================

    def _update_star_state():
        valid_coords, _ = validate_coordinates(ra.value, dec.value)
        app_state.star_coords_valid = valid_coords
        app_state.star_vmag_defined = vmag.value is not None

        if valid_coords:
            app_state.star = Star(
                name=star_name.value,
                ra=ra.value,
                dec=dec.value,
                vmag=vmag.value,
                sptype=sp_type.value,
            )
        else:
            app_state.star = None

    # =================================================
    # SIMBAD resolve
    # =================================================

    def resolve_star(event=None):

        # Clear previous values to avoid stale data
        vmag.value = None
        sp_type.value = DEFAULT_SPTYPE
        sp_type_simbad.object = ""

        name = star_name.value.strip()
        if not name:
            status.object = "⚠️ Please enter a star name."
            return

        try:
            # ---------------------------
            # Step 1: basic query (coords only)
            # ---------------------------
            simbad = create_simbad_client()
            result = simbad.query_object(name)

            if result is None or len(result) == 0:
                status.object = f"⚠️ Object **{name}** not found in SIMBAD."
                return

            coord = SkyCoord(
                ra=result["ra"][0],
                dec=result["dec"][0],
                unit=(u.deg, u.deg),
            )

            ra.value = coord.ra.to_string(unit=u.hour, sep=":", pad=True, precision=0)
            dec.value = coord.dec.to_string(unit=u.deg, sep=":", alwayssign=True, precision=0)

            # ---------------------------
            # Step 2: optional photometry query
            # ---------------------------
            simbad_phot = create_simbad_client()
            simbad_phot.add_votable_fields("flux(V)", "flux(B)", "sp", "ids")
            phot = simbad_phot.query_object(name)

            vmag_msg = "⚠️ V mag not available"
            sp_msg = "⚠️ SpT not available"

            gaia_id_msg = "⚠️ Gaia DR3 ID not found"
            bv_msg = "⚠️ B–V not available"

            if phot is not None and len(phot) > 0:

                # ---------------------------
                # V magnitude
                # ---------------------------
                if "V" in phot.colnames:
                    vmag_value = phot["V"][0]

                    if (
                            vmag_value is not None
                            and not np.ma.is_masked(vmag_value)
                            and np.isfinite(float(vmag_value))
                    ):
                        vmag.value = round(float(vmag_value), 2)
                        vmag_msg = "V mag loaded"

                # ---------------------------
                # Spectral type
                # ---------------------------
                if "sp_type" in phot.colnames and phot["sp_type"][0]:
                    sp = str(phot["sp_type"][0]).strip()
                    mapped = map_simbad_sptype_to_model(sp)

                    if mapped:
                        sp_type.value = mapped
                        sp_msg = f"Simbad SpT: **{sp}** → Mask **{mapped}**"
                    else:
                        sp_msg = f"Simbad SpT: **{sp}** (no automatic mask mapping)"

                # ---------------------------
                # B–V color
                # ---------------------------
                if "B" in phot.colnames and "V" in phot.colnames:
                    bmag_value = phot["B"][0]
                    vmag_value = phot["V"][0]

                    if (
                            bmag_value is not None
                            and vmag_value is not None
                            and not np.ma.is_masked(bmag_value)
                            and not np.ma.is_masked(vmag_value)
                            and np.isfinite(float(bmag_value))
                            and np.isfinite(float(vmag_value))
                    ):
                        bmag = float(bmag_value)
                        vmag_val = float(vmag_value)
                        bv = bmag - vmag_val
                        bv_msg = f"B–V = **{bv:.2f}**"

                # ---------------------------
                # Gaia DR3 ID (from identifiers)
                # ---------------------------
                if "ids" in phot.colnames and phot["ids"][0]:
                    ids_str = phot["ids"][0]

                    for token in ids_str.split("|"):
                        token = token.strip()
                        if token.startswith("Gaia DR3"):
                            gaia_id = token.replace("Gaia DR3", "").strip()

                            gaia_url = (
                                "https://gea.esac.esa.int/archive/"
                                f"?target=Gaia+DR3+{gaia_id}"
                            )

                            gaia_id_msg = f'Gaia DR3 <a href="{gaia_url}" target="_blank"><b>{gaia_id}</b></a>'
                            break

            # ---------------------------
            # Update app state
            # ---------------------------
            _update_star_state()

            simbad_url = get_simbad_url(name)

            name_link = (
                f'<a href="{simbad_url}" target="_blank" '
                f'rel="noopener noreferrer"><b>{name}</b></a>'
            )

            status.object = (
                f"✓ Resolved {name_link}\n"
                f"- Coordinates loaded\n"
                f"- {vmag_msg}\n"
                f"- {sp_msg}\n"
                f"- {bv_msg}\n"
                f"- {gaia_id_msg}"
            )

        except Exception as e:
            status.object = f"❌ SIMBAD query failed: `{e}`"

    resolve_button.on_click(resolve_star)

    # =================================================
    # Manual edits update state
    # =================================================

    def _on_edit(event=None):
        _update_star_state()

    ra.param.watch(_on_edit, "value")
    dec.param.watch(_on_edit, "value")
    vmag.param.watch(_on_edit, "value")
    star_name.param.watch(_on_edit, "value")
    sp_type.param.watch(_on_edit, "value")

    # =================================================
    # Exposure time
    # =================================================

    exptime_title = pn.pane.HTML(
        "<div style='font-size: 1.3em; font-weight: normal;'>Exposure Time</div>"
    )

    exptime_widget = pn.widgets.FloatInput(
        name="Exposure time [s]",
        value=app_state.exposure_time,
        step=STEP_EXPOSURE_TIME,
        width=FORM_WIDGET_WIDTH // 2,
    )

    def _on_exptime_change(event):
        app_state.exposure_time = event.new

    exptime_widget.param.watch(_on_exptime_change, "value")

    # update values from input file
    app_state._input_widgets = getattr(app_state, "_input_widgets", {})
    app_state._input_widgets.update({
        "star_name": star_name,
        "ra": ra,
        "dec": dec,
        "vmag": vmag,
        "sp_type": sp_type,
        "exposure_time": exptime_widget,
    })

    # =================================================
    # Layout
    # =================================================

    return pn.Column(
        pn.Row(
            pn.Column(
                star_name,
                pn.Row(ra, dec),
            ),
            pn.Spacer(width=10),
            resolve_button,
        ),
        coord_status,
        pn.Row(vmag, sp_type),
        pn.Row(pn.Spacer(width=20),status),

        pn.Spacer(height=10),
        make_divider(),
        pn.Spacer(height=10),
        exptime_title,
        exptime_widget,

        sizing_mode="stretch_width",
    )


def make_instrument_tab(app_state: AppState):

    # --------------------------------------------------
    # Instrument selector
    # --------------------------------------------------

    instrument_select = pn.widgets.Select(
        name="Instrument",
        options=list(INSTRUMENTS.keys()),
        value=app_state.instrument.name,
        width=int(FORM_WIDGET_WIDTH * 0.6),
        styles={"font-size": "1.3em"},
    )

    # --------------------------------------------------
    # Instrument summary table (read-only)
    # --------------------------------------------------

    instrument_info = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
    )

    def _fmt_seconds(x: float) -> str:
        return f"{int(x)} s" if float(x).is_integer() else f"{x:.1f} s"

    def update_instrument_info():
        inst = INSTRUMENTS[instrument_select.value]

        altaz = "Yes" if inst.altaz_mount else "No"

        instrument_info.object = (
            "| Observatory | Tel. Diameter | Alt-Az | Fiber | Resolution | λ_eff | Preset | Readout |\n"
            "|:-----------:|:-------------:|:------:|:-----:|:----------:|:-----:|:------:|:-------:|\n"
            f"| {inst.observatory.name} | "
            f"{inst.telescope_diameter:.1f} m | "
            f"{altaz} | "
            f"{inst.fiber_diameter_arcsec:.2f}\" | "
            f"{inst.resolution:,}".replace(",", " ") + " | "
            f"{inst.central_wavelength_um:.2f} µm | "
            f"{_fmt_seconds(inst.telescope_preset)} | "
            f"{_fmt_seconds(inst.readout)} |"
        )

    # --------------------------------------------------
    # Weather losses
    # --------------------------------------------------

    weather_title = pn.pane.HTML("<div style='font-size: 1.3em; font-weight: normal;'>Weather Losses (for Statistics)</div>")

    weather_losses_mode = pn.widgets.RadioButtonGroup(
        options=["None", "Yearly average", "Monthly average"],
        value="None",
        width=FORM_WIDGET_WIDTH,
    )

    # Two-way binding
    weather_losses_mode.link(app_state, value="weather_losses_mode")


    info_box = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
    )

    table_box = pn.Column()

    # --------------------------------------------------
    # State updates
    # --------------------------------------------------

    def _on_instrument_change(event):
        inst = INSTRUMENTS[event.new]
        app_state.instrument = inst
        update_instrument_info()

    instrument_select.param.watch(_on_instrument_change, "value")
    app_state.instrument = INSTRUMENTS[instrument_select.value]

    # --------------------------------------------------
    # Weather info logic (unchanged, lightly reorganized)
    # --------------------------------------------------

    def update_weather_info(*_):
        instrument = INSTRUMENTS[instrument_select.value]
        stats = instrument.observatory.weather_statistics

        table_box.clear()

        if weather_losses_mode.value == "None" or stats is None:
            info_box.object = "Statistics computed without weather losses."
            return

        if weather_losses_mode.value == "Yearly average":
            loss = 1.0 - stats.yearly_usable_fraction
            info_box.object = (
                f"Statistics computed with **{loss:.0%} weather losses**.<br><br>"
                f"{stats.description}<br><br>"
                f'<a href="{stats.reference_url}" target="_blank" '
                f'rel="noopener noreferrer">Reference</a>'
            )
            return

        if weather_losses_mode.value == "Monthly average":
            if stats.monthly_usable_fraction is None:
                info_box.object = (
                    "No information available. "
                    "Monthly statistics computed with **no weather losses**."
                )
                return

            info_box.object = (
                f"Statistics computed with **monthly weather losses**.<br><br>"
                f"{stats.description}<br><br>"
                f'<a href="{stats.reference_url}" target="_blank" '
                f'rel="noopener noreferrer">Reference</a>'
            )

            rows = [
                f"| {m} | {1.0 - f:.0%} |"
                for m, f in stats.monthly_usable_fraction.items()
            ]

            table_md = (
                "| Month | Lost fraction |\n"
                "|:-----:|:-------------:|\n"
                + "\n".join(rows)
            )

            table_box.append(pn.pane.Markdown(table_md))

    instrument_select.param.watch(update_weather_info, "value")
    weather_losses_mode.param.watch(update_weather_info, "value")

    # Initial population
    update_instrument_info()
    update_weather_info()

    # Update values from file
    app_state._input_widgets.update({
        "instrument": instrument_select,
        "weather_losses_mode": weather_losses_mode,
    })

    # --------------------------------------------------
    # Layout
    # --------------------------------------------------

    return pn.Column(
        instrument_select,
        instrument_info,
        pn.Spacer(height=10), make_divider(), pn.Spacer(height=10),
        weather_title,
        weather_losses_mode,
        info_box,
        table_box,
        sizing_mode="stretch_width",
    )


def make_observing_conditions_tab(app_state: AppState):

    # --------------------------------------------------
    # Observability constraints
    # --------------------------------------------------

    # ---- Airmass constraints ----

    airmass_title = pn.pane.HTML("<div style='font-size: 1.3em; font-weight: normal;'>Airmass Constraints</div>")

    max_airmass = pn.widgets.FloatInput(
        name="Maximum airmass",
        value=app_state.conditions.max_airmass,
        start=1.0,
        end=3.0,
        step=STEP_MAX_AIRMASS,
        format=format_field(STEP_MAX_AIRMASS),
        width=FORM_WIDGET_WIDTH // 2,
    )

    min_time = pn.widgets.FloatInput(
        name="Minimum time [h]",
        value=app_state.conditions.min_duration.to_value(u.hour),
        start=0.0,
        step=STEP_MIN_DURATION_HOUR,
        format=format_field(STEP_MIN_DURATION_HOUR),
        width=FORM_WIDGET_WIDTH // 2,
    )

    # ---- Moon constraints ----

    moon_title =  pn.pane.HTML("<div style='font-size: 1.3em; font-weight: normal;'>Moon Constraints</div>")

    moon_separation = pn.widgets.FloatInput(
        name="Moon sep. [deg]",
        value=app_state.conditions.min_moon_separation,
        start=0.0,
        end=180.0,
        step=STEP_MIN_MOON_SEP,
        format=format_field(STEP_MIN_MOON_SEP),
        width=FORM_WIDGET_WIDTH // 2,
    )

    ignore_if_fli = pn.widgets.FloatInput(
        name="Ignore if FLI < ",
        value=app_state.conditions.ignore_moon_if_fli_below,
        start=0.0,
        end=1.0,
        step=STEP_IGNORE_MOON_FLI,
        format=format_field(STEP_IGNORE_MOON_FLI),
        width=FORM_WIDGET_WIDTH // 2,
    )

    # Instantaneous conditions

    title_precision = pn.pane.HTML(
        "<div style='font-size: 1.3em; font-weight: normal;'>RV Precision Conditions</div>"
        "</strong>",
    )

    seeing = pn.widgets.FloatSlider(
        name="Seeing @ 550 nm [arcsec]",
        value=app_state.conditions.seeing_arcsec,
        start=0.3,
        end=3.0,
        step=STEP_SEEING_ARCSEC,
        format=format_field(STEP_SEEING_ARCSEC),
        width=FORM_WIDGET_WIDTH,
    )

    airmass_inst = pn.widgets.FloatSlider(
        name="Airmass [ ]",
        value=app_state.conditions.airmass_rv,
        start=1.0,
        end=3.0,
        step=STEP_AIRMASS_RV,
        format=format_field(STEP_AIRMASS_RV),
        width=FORM_WIDGET_WIDTH ,
    )

    # --------------------------------------------------
    # State wiring
    # --------------------------------------------------

    def _update_conditions(*_):
        app_state.conditions = ObservingConditions(
            max_airmass=max_airmass.value,
            min_duration=min_time.value * u.hour,
            min_moon_separation=moon_separation.value,
            ignore_moon_if_fli_below=ignore_if_fli.value,
            seeing_arcsec=seeing.value,
            airmass_rv=airmass_inst.value,
        )

    for w in (
        max_airmass,
        min_time,
        moon_separation,
        ignore_if_fli,
        seeing,
        airmass_inst,
    ):
        w.param.watch(_update_conditions, "value")

    _update_conditions()

    # update values from input file
    app_state._input_widgets.update({
        "max_airmass": max_airmass,
        "min_duration_hours": min_time,
        "min_moon_separation": moon_separation,
        "ignore_moon_if_fli_below": ignore_if_fli,
        "seeing_arcsec": seeing,
        "airmass_rv": airmass_inst,
    })

    # --------------------------------------------------
    # Layout
    # --------------------------------------------------

    return pn.Column(
        airmass_title,
        pn.Row(
            max_airmass,
            min_time,
            sizing_mode="stretch_width",
        ),
        moon_title,
        pn.Row(
            moon_separation,
            ignore_if_fli,
            sizing_mode="stretch_width",
        ),

        title_precision,
        seeing,
        airmass_inst,
        sizing_mode="stretch_width",
    )


def make_time_tab(app_state):

    night_duration_title = pn.pane.HTML(
        "<div style='font-size: 1.3em; font-weight: normal;'>Night limits</div>"
    )

    night_duration_select = pn.widgets.Select(
        name="Night limits",
        options=VALID_NIGHT_DEFINITIONS,
        value=app_state.night_definition,
        width=FORM_WIDGET_WIDTH,
    )

    time_title = pn.pane.HTML(
        "<div style='font-size: 1.3em; font-weight: normal;'>Reference Time (UTC)</div>"
    )

    # Keep the reference time as separate calendar and UT-clock inputs.
    reference_datetime = app_state.reference_time.utc.to_datetime()
    mode_select = pn.widgets.RadioButtonGroup(
        options=["Now", "Set Time in UTC"],
        value="Now",
    )

    date_input = pn.widgets.DatePicker(
        name="Date",
        value=reference_datetime.date(),
        width=FORM_WIDGET_WIDTH // 2,
        disabled=True,
    )

    time_input = pn.widgets.TimePicker(
        name="UT time",
        value=reference_datetime.time().replace(second=0, microsecond=0),
        width=FORM_WIDGET_WIDTH // 2,
        disabled=True,
    )

    # Time offset controls
    offset_value = pn.widgets.FloatInput(
        name="Offset",
        value=1.0,
        width=FORM_WIDGET_WIDTH // 3,
    )

    offset_unit = pn.widgets.Select(
        name="Unit",
        options=["day", "week", "month", "year"],
        value="day",
        width=FORM_WIDGET_WIDTH // 2,
    )

    update_btn = pn.widgets.Button(
        name="Update time",
        button_type="primary",
        styles={"margin-top": "22px"},
        width=FORM_WIDGET_WIDTH // 2,
    )

    status = pn.pane.Markdown("Using current UTC time.")
    updating_time_widgets = False

    def _sync_time_widgets():
        nonlocal updating_time_widgets
        reference_datetime = app_state.reference_time.utc.to_datetime()
        updating_time_widgets = True
        date_input.value = reference_datetime.date()
        time_input.value = reference_datetime.time().replace(
            second=0, microsecond=0
        )
        updating_time_widgets = False

    def _apply_offset():
        delta = {
            "day": offset_value.value * u.day,
            "week": offset_value.value * u.week,
            "month": offset_value.value * 30 * u.day,
            "year": offset_value.value * 365 * u.day,
        }[offset_unit.value]

        app_state.reference_time += delta
        mode_select.value = "Set Time in UTC"
        _sync_time_widgets()
        status.object = (
            f"Reference time set to **{app_state.reference_time.iso[:16]} UTC**"
        )

    # ----------------------------
    # Callbacks
    # ----------------------------
    def _on_night_duration_change(event):
        app_state.night_definition = event.new

    def _on_mode_change(event):
        is_now = event.new == "Now"
        date_input.disabled = is_now
        time_input.disabled = is_now

        if is_now:
            app_state.reference_time = Time.now()
            status.object = "Using current UTC time."
        else:
            _sync_time_widgets()
            status.object = "Select a date and UT time."

    def _on_time_edit(event=None):
        if updating_time_widgets or mode_select.value != "Set Time in UTC":
            return
        if date_input.value is None or time_input.value is None:
            return

        try:
            reference_datetime = datetime.combine(
                date_input.value,
                time_input.value,
            )
            app_state.reference_time = Time(reference_datetime, scale="utc")
            status.object = (
                f"Reference time set to **{app_state.reference_time.iso[:16]} UTC**"
            )
        except Exception as exc:
            status.object = f"❌ Invalid reference date/time: {exc}"

    # ----------------------------
    # Wiring
    # ----------------------------
    night_duration_select.param.watch(_on_night_duration_change, "value")
    mode_select.param.watch(_on_mode_change, "value")
    date_input.param.watch(_on_time_edit, "value")
    time_input.param.watch(_on_time_edit, "value")
    update_btn.on_click(lambda *_: _apply_offset())

    time_input_row = pn.Row(
        date_input,
        time_input,
        sizing_mode="stretch_width",
    )

    time_offset_row = pn.Row(
        offset_value,
        offset_unit,
        update_btn,
    )

    # Register the widgets used by input save/load.
    app_state._input_widgets.update({
        "night_definition": night_duration_select,
        "time_mode": mode_select,
        "time_date": date_input,
        "time_input": time_input,
        "time_offset": offset_value,
        "time_offset_unit": offset_unit,
    })

    return pn.Column(
        night_duration_title,
        night_duration_select,
        pn.Spacer(height=10),
        time_title,
        mode_select,
        pn.Spacer(height=8),
        time_input_row,
        pn.Spacer(height=10),
        time_offset_row,
        pn.Spacer(height=3),
        status,
        sizing_mode="stretch_width",
    )

def make_planet_rv_tab(app_state: AppState):
    # ----------------------------
    # Planet parameters tab
    # ----------------------------

    planet_title =  pn.pane.HTML("<div style='font-size: 1.3em; font-weight: normal;'>Planet Parameters</div>")

    planet_mass = pn.widgets.FloatInput(
                name="Mass [MJup]",
                value= None,
                format="0.00",
                width=FORM_WIDGET_WIDTH // 2,
    )
    orbital_period = pn.widgets.FloatInput(
                name="Orbital period [days]",
                value= None,
                format="0.00",
                width=FORM_WIDGET_WIDTH // 2,
    )

    stellar_mass = pn.widgets.FloatInput(
                name="Stellar Mass [MSun]",
                value=1.0,
                format="0.00",
                width=FORM_WIDGET_WIDTH // 2,
                )

    t0_input = pn.widgets.FloatInput(
        name="T0 [JD]",
        value=None,
        step=0.0001,
        format="0.0000",
        width=FORM_WIDGET_WIDTH,
    )

    total_duration_input = pn.widgets.FloatInput(
        name="Obs. duration [h]",
        value=None,
        step=0.5,
        format="0.0",
        width=FORM_WIDGET_WIDTH // 2,
    )

    include_transit_switch = pn.widgets.Switch(
        name="Observability of Transit",
        value=False,
    )

    def _optional_float(value):
        """Convert NaN or None to None, keeping valid numerical values."""
        if value is None or math.isnan(value):
            return None
        return value

    def _update_planet_params(*_):
        app_state.planet_params = PlanetParameters(
            planet_mass_mjup=_optional_float(planet_mass.value),
            orbital_period_days=_optional_float(orbital_period.value),
            stellar_mass_msun=stellar_mass.value,
            t0_jd=_optional_float(t0_input.value),
            total_observation_duration=_optional_float(total_duration_input.value),
            include_transit_in_observability=include_transit_switch.value,
        )

        app_state.param.trigger("planet_params")

    for w in (
            planet_mass,
            orbital_period,
            stellar_mass,
            t0_input,
            total_duration_input,
            include_transit_switch,
    ):
        w.param.watch(_update_planet_params, "value")

    # update values from input file
    app_state._input_widgets.update({
        "planet_mass_mjup": planet_mass,
        "orbital_period_days": orbital_period,
        "stellar_mass_msun": stellar_mass,
        "t0_jd": t0_input,
        "total_observation_duration_hours": total_duration_input,
        "include_transit_in_observability": include_transit_switch,
    })

    return pn.Column(
        planet_title,
        pn.Row(planet_mass, orbital_period, stellar_mass),
        pn.Spacer(height=8),
        pn.Row(t0_input, total_duration_input, pn.Column(pn.Spacer(height=20), include_transit_switch)),

        pn.Spacer(height=10), make_divider(),

        sizing_mode="stretch_width",
    )


def make_input_output_tab(app_state: AppState):
    """Create a tab for saving and loading input configurations."""

    # --------------------------------------------------
    # File controls
    # --------------------------------------------------

    file_io_layout, file_io = make_file_io_controls(
        directory_name="Targets working Dir",
        default_directory=DEFAULT_TARGETS_DIR,
    )

    working_dir = file_io["working_dir"]
    file_name = file_io["file_name"]
    save_button = file_io["save_button"]
    load_button = file_io["load_button"]
    refresh_file_list = file_io["refresh_file_list"]

    # --------------------------------------------------
    # Log
    # --------------------------------------------------

    log_pane = pn.pane.Markdown(
        "No file operations yet.",
        sizing_mode="stretch_width",
    )

    log_entries = []

    def add_log(message: str):
        """Add a timestamped entry to the log."""

        timestamp = datetime.now().astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        log_entries.insert(0, f"- `{timestamp}` — {message}")
        del log_entries[100:]

        log_pane.object = "\n".join(log_entries)

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def get_file_path() -> Path:
        """Resolve the configuration file path."""

        directory = Path(working_dir.value).expanduser()

        filename = file_name.value.strip()
        if not filename:
            raise ValueError("Please provide a filename.")

        path = Path(filename).expanduser()

        # If a relative filename includes a directory, preserve it.
        if not path.is_absolute():
            path = directory / path

        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")

        return path

    def get_widget_values() -> dict:
        """Collect the current input values from the registered widgets."""

        widgets = getattr(app_state, "_input_widgets", {})

        # The reference time is stored separately in UTC.
        excluded = {"time_mode", "time_date", "time_input"}

        values = {
            key: widget.value
            for key, widget in widgets.items()
            if key not in excluded
        }

        return values

    # --------------------------------------------------
    # Save
    # --------------------------------------------------

    def save_input(event=None):
        try:
            path = get_file_path()
            path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "format_version": 1,
                "reference_time_utc": app_state.reference_time.utc.isot,
                "inputs": get_widget_values(),
            }

            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            add_log(f"✅ Saved input to `{path}`")
            refresh_file_list()

        except Exception as exc:
            add_log(
                f"❌ Save failed: `{type(exc).__name__}: {exc}`"
            )

    # --------------------------------------------------
    # Load
    # --------------------------------------------------

    def load_input(event=None):
        try:
            path = get_file_path()

            if not path.is_file():
                raise FileNotFoundError(f"File not found: {path}")

            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "inputs" not in data:
                raise ValueError(
                    "Invalid configuration file: missing 'inputs'."
                )

            widgets = getattr(app_state, "_input_widgets", {})
            values = data["inputs"]

            if not isinstance(values, dict):
                raise ValueError("'inputs' must be a JSON object.")

            # Restore the reference time before switching the mode to UTC.
            # Switching to "Now" would otherwise replace the loaded time.
            if "reference_time_utc" in data:
                app_state.reference_time = Time(
                    data["reference_time_utc"],
                    format="isot",
                    scale="utc",
                )

            # Update regular controls first. Their existing callbacks
            # propagate the new values into AppState.
            for key, value in values.items():
                if key in widgets and key not in {"time_mode", "time_date", "time_input"}:
                    widgets[key].value = value

            # Restore the displayed time and use UTC mode so the loaded
            # reference time is preserved instead of reset to the current time.
            if "reference_time_utc" in data:
                reference_datetime = app_state.reference_time.utc.to_datetime()
                date_widget = widgets.get("time_date")
                time_widget = widgets.get("time_input")
                mode_select = widgets.get("time_mode")

                if date_widget is not None:
                    date_widget.value = reference_datetime.date()
                if time_widget is not None:
                    time_widget.value = reference_datetime.time().replace(
                        second=0, microsecond=0
                    )
                if mode_select is not None:
                    mode_select.value = "Set Time in UTC"

            # Refresh the state flags used to enable the compute buttons.
            ra_widget = widgets.get("ra")
            dec_widget = widgets.get("dec")
            vmag_widget = widgets.get("vmag")

            if ra_widget is not None and dec_widget is not None:
                valid, _ = validate_coordinates(
                    ra_widget.value,
                    dec_widget.value,
                )
                app_state.star_coords_valid = valid

            if vmag_widget is not None:
                app_state.star_vmag_defined = vmag_widget.value is not None

            add_log(f"✅ Loaded input from `{path}`")

            working_dir.value = str(path.parent.resolve())
            file_name.value = path.name

        except Exception as exc:
            add_log(
                f"❌ Load failed: `{type(exc).__name__}: {exc}`"
            )

    # --------------------------------------------------
    # Wiring
    # --------------------------------------------------

    save_button.on_click(save_input)
    load_button.on_click(load_input)

    # --------------------------------------------------
    # Layout
    # --------------------------------------------------

    return pn.Column(
        pn.pane.HTML(
            "<div style='font-size: 1.3em; font-weight: normal;'>"
            "Load / Save"
            "</div>"
        ),

        file_io_layout,

        pn.Spacer(height=10),
        make_divider(),
        pn.Spacer(height=10),

        pn.pane.HTML(
            "<div style='font-size: 1.2em; font-weight: normal;'>"
            "Log"
            "</div>"
        ),

        pn.Column(
            log_pane,
            height=250,
            scroll=True,
            sizing_mode="stretch_width",
        ),

        sizing_mode="stretch_width",
    )

# general control tabs

def make_control_tabs(app_state: AppState):
    return pn.Tabs(
        ("Star & Exptime", make_star_tab(app_state)),
        ("Instrument", make_instrument_tab(app_state)),
        ("Conditions", make_observing_conditions_tab(app_state)),
        ("Obs. Time", make_time_tab(app_state)),
        ("Planet Params", make_planet_rv_tab(app_state)),
        ("Load / Save", make_input_output_tab(app_state)),
        sizing_mode="stretch_width",
    )