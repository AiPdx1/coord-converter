"""Coordinate conversion: DD <-> DMS <-> DDM (pure math, no I/O)."""


def dd_to_dms(dd: float, is_lat: bool) -> tuple[int, int, float, str]:
    """Convert decimal degrees to (degrees, minutes, seconds, hemisphere)."""
    hem = _hemisphere(dd, is_lat)
    dd_abs = abs(dd)
    deg = int(dd_abs)
    min_float = (dd_abs - deg) * 60
    min_val = int(min_float)
    sec = (min_float - min_val) * 60
    # Handle rounding to 60.0
    if sec >= 59.9995:
        sec = 0.0
        min_val += 1
        if min_val >= 60:
            min_val = 0
            deg += 1
    sec = round(sec, 2)
    return (deg, min_val, sec, hem)


def dd_to_ddm(dd: float, is_lat: bool) -> tuple[int, float, str]:
    """Convert decimal degrees to (degrees, decimal_minutes, hemisphere)."""
    hem = _hemisphere(dd, is_lat)
    dd_abs = abs(dd)
    deg = int(dd_abs)
    dec_min = (dd_abs - deg) * 60
    # Handle rounding to 60.0
    if dec_min >= 59.99995:
        dec_min = 0.0
        deg += 1
    dec_min = round(dec_min, 4)
    return (deg, dec_min, hem)


def _hemisphere(dd: float, is_lat: bool) -> str:
    if is_lat:
        return "N" if dd >= 0 else "S"
    else:
        return "E" if dd >= 0 else "W"


def format_dd(lat: float | None, lon: float | None, precision: int = 5) -> str:
    """Format as decimal degrees: '40.44611, -79.94889'."""
    parts = []
    if lat is not None:
        parts.append(f"{lat:.{precision}f}")
    if lon is not None:
        parts.append(f"{lon:.{precision}f}")
    return ", ".join(parts)


def format_dms(lat: float | None, lon: float | None) -> str:
    """Format as DMS: '40°26'46\"N 79°56'56\"W'."""
    parts = []
    if lat is not None:
        d, m, s, h = dd_to_dms(lat, True)
        parts.append(f'{d}°{m:02d}\'{s:05.2f}"{h}')
    if lon is not None:
        d, m, s, h = dd_to_dms(lon, False)
        parts.append(f'{d}°{m:02d}\'{s:05.2f}"{h}')
    return " ".join(parts)


def format_ddm(lat: float | None, lon: float | None, precision: int = 4) -> str:
    """Format as DDM: '40°26.7670'N 79°56.9330'W'."""
    parts = []
    if lat is not None:
        d, dm, h = dd_to_ddm(lat, True)
        parts.append(f"{d}°{dm:.{precision}f}'{h}")
    if lon is not None:
        d, dm, h = dd_to_ddm(lon, False)
        parts.append(f"{d}°{dm:.{precision}f}'{h}")
    return " ".join(parts)


def validate_lat(value: float) -> bool:
    return -90.0 <= value <= 90.0


def validate_lon(value: float) -> bool:
    return -180.0 <= value <= 180.0
