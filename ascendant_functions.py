
import swisseph as swe
import math

def get_ascendant(jd, lat, lon):
    # Convert longitude to East-positive if needed
    if lon < 0:
        lon = 360 + lon

    # Calculate sidereal time and local sidereal time
    sidereal_time = swe.sidtime(jd)
    lst_deg = (sidereal_time * 15 + lon) % 360

    # Calculate ayanamsa
    ayanamsa = swe.get_ayanamsa_ut(jd)

    # Get Placidus house system ascendant in sidereal mode
    flags = swe.FLG_SIDEREAL
    ascmc = swe.houses_ex(jd, lat, lon, b'A', flags)[0]
    asc_deg = ascmc[0]

    return asc_deg
