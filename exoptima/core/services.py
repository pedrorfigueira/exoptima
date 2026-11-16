"""
External services used by EXOPTIMA.
"""

from astroquery.simbad import Simbad, conf as simbad_conf
from urllib.parse import quote_plus

from exoptima.config.computation import (
    SIMBAD_SERVERS,
    SIMBAD_SERVER,
    SIMBAD_TIMEOUT,
)


def create_simbad_client():
    """Create a SIMBAD client using the configured server."""

    server = SIMBAD_SERVERS[SIMBAD_SERVER]["host"]

    # Register alternative mirrors if necessary.
    if server not in simbad_conf.servers_list:
        simbad_conf.servers_list.append(server)

    simbad = Simbad()
    simbad.server = server
    simbad.TIMEOUT = SIMBAD_TIMEOUT

    return simbad


def get_simbad_url(name: str) -> str:
    """Return the SIMBAD web interface URL for an object."""

    base_url = SIMBAD_SERVERS[SIMBAD_SERVER]["url"]
    return f"{base_url}/simbad/sim-id?Ident={quote_plus(name)}"