# Control tabs definition

import panel as pn
pn.extension()

from datetime import datetime
from zoneinfo import ZoneInfo

from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astroquery.simbad import Simbad

# Configure SIMBAD once
_CUSTOM_SIMBAD = Simbad()
_CUSTOM_SIMBAD.add_votable_fields("flux(V)", "sp")

from exoptima.config.layout import FORM_WIDGET_WIDTH, BUTTON_WIDTH, BUTTON_HEIGHT
from exoptima.config.instruments import INSTRUMENTS

from exoptima.core.state import AppState, Star
app_state = AppState()

# ----- helper functions -----

def map_simbad_sptype_to_model(sptype: str) -> str | None:
    """
    Map a SIMBAD spectral type string to the nearest available model SpType.

    Returns
    -------
    str or None
        One of ["G2", "K2", "K7", "M2"], or None if no match.
    """
    if not sptype:
        return None

    sptype = sptype.strip().upper()

    if sptype.startswith("G"):
        return "G2"

    if sptype.startswith("K"):
        # Try to extract subtype number
        for ch in sptype[1:]:
            if ch.isdigit():
                subtype = int(ch)
                break
        else:
            subtype = 2  # default K

        return "K2" if subtype <= 4 else "K7"

    if sptype.startswith("M"):
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


def parse_min_time(value: str) -> u.Quantity:
    """
    Parse a minimum observing time string into an astropy Quantity.

    Examples
    --------
    "1 min"  -> 1 * u.min
    "30 min" -> 30 * u.min
    "1 h"    -> 1 * u.hour
    """
    value = value.strip().lower()

    number_str, unit_str = value.split()
    number = float(number_str)

    if unit_str.startswith("min"):
        return number * u.min
    if unit_str.startswith("h"):
        return number * u.hour

    raise ValueError(f"Unsupported time format: '{value}'")

# Custom divider

divider_h = pn.Spacer(
    height=1,
    sizing_mode="stretch_width",
    styles={"background-color": "#e0e0e0"},
)

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
        step=0.1,
        width=FORM_WIDGET_WIDTH // 2,
    )

    sp_type = pn.widgets.Select(
        name="SpType (model)",
        options=["G2", "K2", "K7", "M2"],
        value="G2",
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
        name = star_name.value.strip()
        if not name:
            status.object = "⚠️ Please enter a star name."
            return

        try:
            result = _CUSTOM_SIMBAD.query_object(name)
            if result is None:
                status.object = f"⚠️ Object **{name}** not found in SIMBAD."
                return

            coord = SkyCoord(
                ra=result["ra"][0],
                dec=result["dec"][0],
                unit=(u.deg, u.deg),
            )

            ra.value = coord.ra.to_string(unit=u.hour, sep=":", pad=True, precision=0)
            dec.value = coord.dec.to_string(unit=u.deg, sep=":", alwayssign=True, precision=0)

            if "V" in result.colnames and result["V"][0] is not None:
                vmag.value = round(float(result["V"][0]), 2)

            if "sp_type" in result.colnames and result["sp_type"][0]:
                simbad_sp = result["sp_type"][0]
                sp_type_simbad.object = f"(Simbad: {simbad_sp})"
                mapped = map_simbad_sptype_to_model(simbad_sp)
                if mapped:
                    sp_type.value = mapped
            else:
                sp_type_simbad.object = ""

            _update_star_state()

            if app_state.star_coords_valid:
                app_state.star = Star(
                    name=star_name.value,
                    ra=ra.value,
                    dec=dec.value,
                    vmag=vmag.value,
                    sptype=sp_type.value,
                )

            status.object = f"✓ Resolved **{name}** via SIMBAD."

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
        pn.Row(vmag, pn.Row(sp_type, sp_type_simbad)),
        pn.Row(pn.Spacer(width=20),status),
        sizing_mode="stretch_width",
    )


def make_instrument_tab(app_state: AppState):

    # --------------------------------------------------
    # Instrument selector
    # --------------------------------------------------

    instrument_select = pn.widgets.Select(
        name="Instrument",
        options=list(INSTRUMENTS.keys()),
        value="EXOTICA",
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

    def update_instrument_info():
        inst = INSTRUMENTS[instrument_select.value]
        instrument_info.object = (
            "| Observatory | Tel. Diameter | Resolution |\n"
            "|:-----------:|:-------------:|:----------:|\n"
            f"| {inst.observatory.name} | "
            f"{inst.telescope_diameter:.1f} m | "
            f"{inst.resolution:,}".replace(",", " ")
        )

    # --------------------------------------------------
    # Weather losses
    # --------------------------------------------------

    weather_title = pn.pane.HTML("<div style='font-size: 1.3em; font-weight: normal;'>Weather Losses (for Statistics)</div>")

    weather_mode = pn.widgets.RadioButtonGroup(
        options=["None", "Yearly average", "Monthly average"],
        value="None",
        width=FORM_WIDGET_WIDTH,
    )

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
        stats = instrument.weather_statistics

        table_box.clear()

        if weather_mode.value == "None" or stats is None:
            info_box.object = "Statistics computed without weather losses."
            return

        if weather_mode.value == "Yearly average":
            loss = 1.0 - stats.yearly_usable_fraction
            info_box.object = (
                f"Statistics computed with **{loss:.0%} weather losses**.<br><br>"
                f"{stats.description}<br><br>"
                f'<a href="{stats.reference_url}" target="_blank" '
                f'rel="noopener noreferrer">Reference</a>'
            )
            return

        if weather_mode.value == "Monthly average":
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
    weather_mode.param.watch(update_weather_info, "value")

    # Initial population
    update_instrument_info()
    update_weather_info()

    # --------------------------------------------------
    # Layout
    # --------------------------------------------------

    return pn.Column(
        instrument_select,
        instrument_info,
        pn.Spacer(height=10), divider_h, pn.Spacer(height=10),
        weather_title,
        weather_mode,
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
        value=2.0,
        start=1.0,
        end=3.0,
        step=0.1,
        width=FORM_WIDGET_WIDTH // 2,
    )

    min_time = pn.widgets.Select(
        name="Minimum time",
        options=[
            "1 min",
            "30 min",
            "1 h",
            "2 h",
            "3 h",
            "5 h",
        ],
        value="1 h",
        width=FORM_WIDGET_WIDTH // 2,
    )

    # ---- Moon constraints ----

    moon_title =  pn.pane.HTML("<div style='font-size: 1.3em; font-weight: normal;'>Moon Constraints</div>")

    moon_separation = pn.widgets.FloatInput(
        name="Moon sep. [deg]",
        value=30.0,
        start=0.0,
        end=180.0,
        step=5.0,
        width=FORM_WIDGET_WIDTH // 2,
    )

    ignore_if_fli = pn.widgets.FloatInput(
        name="Ignore if FLI < ",
        value=0.5,
        start=0.0,
        end=1.0,
        step=0.05,
        width=FORM_WIDGET_WIDTH // 2,
    )

    # --------------------------------------------------
    # State wiring
    # --------------------------------------------------

    def _update_conditions(*_):
        app_state.conditions.max_airmass = max_airmass.value
        app_state.conditions.min_duration = parse_min_time(min_time.value)
        app_state.conditions.moon_separation = moon_separation.value
        app_state.conditions.ignore_moon_if_fli = ignore_if_fli.value

    for w in (max_airmass, min_time, moon_separation, ignore_if_fli):
        w.param.watch(_update_conditions, "value")

    _update_conditions()

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
        sizing_mode="stretch_width",
    )


def make_time_tab(app_state):

    night_duration_title =  pn.pane.HTML("<div style='font-size: 1.3em; font-weight: normal;'>Night limits</div>")

    # night duration
    night_duration_select = pn.widgets.Select(
        options={
            "sunset_sunrise": "Sunset to sunrise",
            "nautical": "Nautical twilight",
            "astronomical": "Astronomical twilight",
        },
        value=app_state.night_definition,
        width=FORM_WIDGET_WIDTH,
    )

    time_title =  pn.pane.HTML("<div style='font-size: 1.3em; font-weight: normal;'>Reference Time</div>")

    # Mode selection
    mode_select = pn.widgets.RadioButtonGroup(
        options=["Now", "Set Time in UTC", "Set Time in Local Time"],
        value="Now",
    )

    time_input = pn.widgets.TextInput(
        placeholder="YYYY-MM-DD HH:MM",
        disabled=True,
    )

    timezone_select = pn.widgets.Select(
        name="Time zone",
        options=[
            "Local Time of Observatory",
            "UTC",
            "Europe/Paris",
            "Europe/London",
            "America/Santiago",
            "America/New_York",
            "Asia/Tokyo",
        ],
        value="Local Time of Observatory",
        disabled=True,
    )

    convert_btn = pn.widgets.Button(
        name="Convert to UT",
        button_type="primary",
        disabled=True,
    )

    # Increment controls
    increment = pn.widgets.Select(options=["+", "-"], value="+", width=FORM_WIDGET_WIDTH // 4)
    step = pn.widgets.Select(options=["1h", "1day", "1month", "1year"], value="1day", width=FORM_WIDGET_WIDTH // 2)

    update_btn = pn.widgets.Button(
        name="Update time",
        button_type="primary",
        width = FORM_WIDGET_WIDTH // 2
    )

    status = pn.pane.Markdown("")

    # ----------------------------
    # Helpers
    # ----------------------------
    def _parse_time(text: str) -> Time:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        return Time(dt, scale="utc")

    def _parse_naive_time(text: str) -> datetime:
        return datetime.strptime(text, "%Y-%m-%d %H:%M")

    def _observatory_timezone():
        lon = app_state.instrument.observatory.longitude_deg
        return "Etc/GMT%+d" % int(round(-lon / 15))

    def _apply_offset():
        delta = {
            "1h": 1 * u.hour,
            "1day": 1 * u.day,
            "1month": 30 * u.day,
            "1year": 365 * u.day,
        }[step.value]

        if increment.value == "-":
            delta = -delta

        app_state.reference_time += delta
        time_input.value = app_state.reference_time.to_datetime().strftime(
            "%Y-%m-%d %H:%M"
        )

        status.object = f"Reference time set to **{app_state.reference_time.iso[:16]} UTC**"

    # ----------------------------
    # Callbacks
    # ----------------------------
    def _on_night_duration_change(event):
        app_state.night_definition = event.new


    def _on_mode_change(event):
        mode = event.new

        if mode == "Now":
            time_input.disabled = True
            timezone_select.disabled = True
            convert_btn.disabled = True

            local_time_row.visible = False

            app_state.reference_time = Time.now()
            status.object = "Using current UTC time."

        elif mode == "Set Time in UTC":
            time_input.disabled = False
            timezone_select.disabled = True
            convert_btn.disabled = True

            local_time_row.visible = False

            time_input.value = app_state.reference_time.to_datetime().strftime(
                "%Y-%m-%d %H:%M"
            )
            status.object = "Enter a UTC time."

        elif mode == "Set Time in Local Time":
            time_input.disabled = False
            timezone_select.disabled = False
            convert_btn.disabled = False

            local_time_row.visible = True

            status.object = (
                "Enter a local time, select the time zone, then press "
                "**Convert to UT**."
            )

    def _on_time_edit(event):
        if mode_select.value != "Set Time in UTC":
            return
        try:
            app_state.reference_time = _parse_time(time_input.value.strip())
            status.object = f"Reference time set to **{app_state.reference_time.iso[:16]} UTC**"
        except Exception:
            status.object = (
                "❌ Invalid format. Use **YYYY-MM-DD HH:MM**, e.g. `2026-01-15 22:30`"
            )

    def _on_convert_to_utc(event=None):
        try:
            dt_naive = _parse_naive_time(time_input.value.strip())

            if timezone_select.value == "Local Time of Observatory":
                tz_name = _observatory_timezone()
            else:
                tz_name = timezone_select.value

            dt_local = dt_naive.replace(tzinfo=ZoneInfo(tz_name))
            dt_utc = dt_local.astimezone(ZoneInfo("UTC"))

            app_state.reference_time = Time(dt_utc)
            status.object = (
                f"Converted to UTC: **{app_state.reference_time.iso[:16]} UTC**"
            )

        except Exception as e:
            status.object = f"❌ Conversion failed: {e}"

    # ----------------------------
    # Wiring
    # ----------------------------

    status.object = "Using current UTC time."

    night_duration_select.param.watch(_on_night_duration_change, "value")
    mode_select.param.watch(_on_mode_change, "value")
    time_input.param.watch(_on_time_edit, "value")
    update_btn.on_click(lambda *_: _apply_offset())
    convert_btn.on_click(_on_convert_to_utc)

    # ----------------------------
    # Layout
    # ----------------------------

    utc_time_row = pn.Row(
        time_input,
        sizing_mode="stretch_width",
    )

    local_time_row = pn.Row(
        timezone_select,
        convert_btn,
        sizing_mode="stretch_width",
    )

    # Hide local-time controls by default
    local_time_row.visible = False

    increment_row = pn.Row(
        increment,
        step,
        update_btn,
        sizing_mode="stretch_width",
    )

    return pn.Column(

        night_duration_title,
        night_duration_select,
        pn.Spacer(height=10),

        time_title,
        mode_select,
        pn.Spacer(height=8),

        utc_time_row,
        local_time_row,
        pn.Spacer(height=10),

        increment_row,
        pn.Spacer(height=3),

        status,

        sizing_mode="stretch_width",
    )

def make_planet_rv_tab(app_state: AppState):
    # ----------------------------
    # Planet & RV precision tabs
    # ----------------------------

    def make_planet_controls():
        return pn.Column(
            pn.pane.Markdown("### Planet parameters"),
            pn.Row(
                pn.widgets.FloatInput(
                    name="Mass [MJup]",
                    width=FORM_WIDGET_WIDTH // 2,
                    disabled=True),
                pn.widgets.FloatInput(
                    name="Orbital period [days]",
                    width=FORM_WIDGET_WIDTH // 2,
                    disabled=True),
                pn.widgets.FloatInput(
                    name="Stellar Mass [MSun]",
                    width=FORM_WIDGET_WIDTH // 2,
                    disabled=True),
            ),
            sizing_mode="stretch_width",
        )

    def make_rv_precision_controls():
        return pn.Column(
            pn.pane.Markdown(
                "### RV precision (not implemented yet)\n"
                "<span style='color:#b00020; font-style:italic;'>Disabled</span>",
            ),
            pn.Row(
                pn.widgets.FloatInput(
                    name="Exposure time [s]",
                    width=FORM_WIDGET_WIDTH // 2,
                    disabled=True),
                pn.widgets.FloatInput(
                    name="Target S/N",
                    width=FORM_WIDGET_WIDTH // 2,
                    disabled=True),
                pn.widgets.Select(
                    name="RV model",
                    options=["Photon-limited", "Instrument-limited"],
                    width=FORM_WIDGET_WIDTH // 2,
                    disabled=True,
                ),
            ),
            sizing_mode="stretch_width",
        )

    # --------------------------------------------------
    # Instantaneous conditions (disabled)
    # --------------------------------------------------

    title_precision = pn.pane.HTML(
        "<div style='font-size: 1.3em; font-weight: normal;'>RV Precision Conditions</div>"
        "<span style='color:#b00020; font-style:italic;'>"
        "(Not implemented yet)"
        "</span></strong>",
    )

    seeing = pn.widgets.FloatSlider(
        name="Seeing (arcsec)",
        start=0.3,
        end=3.0,
        value=1.0,
        step=0.1,
        width=int(FORM_WIDGET_WIDTH * 0.6),
    )

    airmass_inst = pn.widgets.FloatInput(
        name="Airmass [ ]",
        value=1.5,
        start=1.0,
        end=3.0,
        step=0.1,
        width=FORM_WIDGET_WIDTH // 2,
    )

    sky_condition = pn.widgets.Select(
        name="Sky condition",
        options=["Clear", "Thin clouds", "Cloudy"],
        value="Clear",
        width=FORM_WIDGET_WIDTH // 2,
    )

    for widget in (seeing, airmass_inst, sky_condition):
        widget.disabled = True

    return pn.Column(
        make_planet_controls(),
        pn.Spacer(height=10),
        make_rv_precision_controls(),

        pn.Spacer(height=10), divider_h, pn.Spacer(height=10),

        title_precision,
        pn.Row(seeing, airmass_inst, sky_condition),
        sizing_mode="stretch_width",
    )
