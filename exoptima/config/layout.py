"""
Application-wide configuration for EXOPTIMA
"""

from astropy import units as u

# ------------------------------------------------------------------
# General interface configuration
# ------------------------------------------------------------------

# Fraction of horizontal space taken by the left (controls) panel
CONTROLS_PANEL_FRACTION = 0.3       # left section

# Vertical spacing
HEADER_SPACING = 10

# Output tabs: fraction for plots vs statistics
DISPLAY_MAIN_FRACTION = 0.7

# RV precision tab: fraction of space for output vs planet controls
RV_OUTPUT_FRACTION = 0.7            # upper section

# ------------------------------------------------------------------
# Button, Form, and widget sizing
# ------------------------------------------------------------------

FORM_WIDGET_WIDTH = 200  # pixels

# Button sizing
BUTTON_WIDTH = 160
BUTTON_HEIGHT = 36

# ------------------------------------------------------------------
# Observability plots
# ------------------------------------------------------------------

# Daytime period shown before sunset and after sunrise
DAYTIME_INTERVAL = 0.5*u.hour
# number of points in UT time in daily observability plots
DAY_OBS_NSAMPLES = 300
