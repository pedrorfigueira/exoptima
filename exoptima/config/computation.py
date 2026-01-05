# computation defaults

from astropy import units as u

# default observing constraints

DEFAULT_MAX_AIRMASS = 2.0
DEFAULT_MIN_DURATION = 1 * u.hour
DEFAULT_MIN_MOON_SEP = 30.0
DEFAULT_IGNORE_MOON_FLI = 0.05

# step in nights used in "Year" observability mode
YEAR_OBS_NIGHTSTEP = 7