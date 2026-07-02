
import swisseph as swe
import pytz
from datetime import datetime
from pytz import timezone

# Set sidereal mode using Lahiri ayanamsa
swe.set_sid_mode(swe.SIDM_LAHIRI)

planets = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO
}

def get_julian_day(date_str, time_str, tz_str):
    tz = timezone(tz_str)
    naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    local_dt = tz.localize(naive)
    utc_dt = local_dt.astimezone(pytz.utc)
    jd = swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60 + utc_dt.second / 3600
    )
    return jd

def get_planetary_positions(jd):
    positions = {}
    for name, pid in planets.items():
        tropical = swe.calc_ut(jd, pid)[0][0]
        ayanamsa = swe.get_ayanamsa_ut(jd)
        sidereal = (tropical - ayanamsa) % 360
        positions[name] = sidereal
    return positions
