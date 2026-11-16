# computation defaults

# SIMBAD server configuration

SIMBAD_SERVERS = {
    "CDS": {
        "host": "simbad.cds.unistra.fr",
        "url": "https://simbad.cds.unistra.fr",
    },
    "Harvard": {
        "host": "simbad.harvard.edu",
        "url": "https://simbad.harvard.edu",
    },
    "IDIA": {
        "host": "simbad.idia.ac.za",
        "url": "https://simbad.idia.ac.za",
    },
}

SIMBAD_SERVER = "Harvard"
SIMBAD_TIMEOUT = 30

# default sp type from the drop_down
DEFAULT_SPTYPE = "G2"

# valid spectral types for calculazions
VALID_SPTYPES = ["G2", "K2", "M2"]

# valid options for night definition
VALID_NIGHT_DEFINITIONS = [
    "Sunset to sunrise",
    "Nautical twilight",
    "Astronomical twilight",
]

STEP_VMAG = 0.01

DEFAULT_EXPOSURE_TIME = 60.0
STEP_EXPOSURE_TIME = 1.0

# default instrument
DEFAULT_INSTRUMENT = "ESPRESSO"

# default observing constraints
DEFAULT_MAX_AIRMASS = 2.0
DEFAULT_MIN_DURATION_HOUR = 1
DEFAULT_MIN_MOON_SEP = 30.0
DEFAULT_IGNORE_MOON_FLI = 0.05
DEFAULT_SEEING_ARCSEC = 0.8
DEFAULT_AIRMASS_RV = 1.2

# default control steps
STEP_MAX_AIRMASS = 0.1
STEP_MIN_DURATION_HOUR = 0.5
STEP_MIN_MOON_SEP = 1.0
STEP_IGNORE_MOON_FLI = 0.01
STEP_SEEING_ARCSEC = 0.1
STEP_AIRMASS_RV = 0.1

# default night limit definition
DEFAULT_NIGHT_DEFINITION = "Nautical twilight"

# default zenithal avoidance zone for alt-az telescopes
DEFAULT_ZENITH_AVOIDANCE_DEG = 3

# step in nights used in "Year" observability mode
YEAR_OBS_NIGHTSTEP = 7

# Time resolution for target observability calculations.
OBSERVABILITY_CADENCE_MINUTES = 5.0

# Number of classes used for scheduling priorities
NUMBER_CLASSES_SCHEDULING_PRIORITIES = 3

# Offset in hour angle to apply to the starting of the night
OFFSET_HA = -2.0
