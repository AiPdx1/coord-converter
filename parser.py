"""Parse various lat/lon formats into decimal degrees with auto-detection."""

import re
from dataclasses import dataclass, field
from converter import validate_lat, validate_lon


@dataclass
class ParseResult:
    success: bool
    format_detected: str = "unknown"
    lat: float | None = None
    lon: float | None = None
    pairs: list[tuple[float | None, float | None]] = field(default_factory=list)
    error_message: str = ""


# ── Normalization ──────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Replace Unicode variants and normalize separators."""
    text = text.strip()
    # Unicode degree marks -> standard degree symbol
    text = re.sub(r'[˚º]', '°', text)
    # Unicode minute/second marks -> ASCII
    text = text.replace('′', "'")   # ′ prime
    text = text.replace('″', '"')   # ″ double prime
    text = text.replace('‘', "'")   # ' left single quote
    text = text.replace('’', "'")   # ' right single quote
    text = text.replace('“', '"')   # " left double quote
    text = text.replace('”', '"')   # " right double quote
    # Non-breaking space -> regular space
    text = text.replace(' ', ' ')
    # Fullwidth characters
    text = text.replace('，', ',')   # fullwidth comma
    text = text.replace('；', ';')   # fullwidth semicolon
    text = text.replace('－', '-')   # fullwidth minus
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ── Individual token parsing ───────────────────────────────────

# Pattern 1: DMS with symbols  e.g. 40°26'46"N, 40°26'46"
_DMS_SYMBOL_RE = re.compile(
    r'(-?\d{1,3})\s*[°d]\s*(\d{1,2})\s*[\'′]\s*(\d{1,2}(?:\.\d+)?)\s*["″]?\s*([NSEWnsew])?',
    re.IGNORECASE
)

# Pattern 2: DMS with spaces or colons  e.g. 40 26 46 N, 40:26:46N
_DMS_SPACE_RE = re.compile(
    r'(-?\d{1,3})\s*[:\s]\s*(\d{1,2})\s*[:\s]\s*(\d{1,2}(?:\.\d+)?)\s*([NSEWnsew])?',
    re.IGNORECASE
)

# Pattern 3: DDM  e.g. 40°26.767'N, 40 26.767 N
# Requires a separator (°, d, or whitespace) between degree and decimal minute parts
# to avoid false match on plain decimal degrees like 40.44611
_DDM_RE = re.compile(
    r'(-?\d{1,3})\s*(?:[°d]|\s)\s*(\d{1,2}\.\d+)\s*[\'′]?\s*([NSEWnsew])?',
    re.IGNORECASE
)

# Pattern 4: DD  e.g. 40.44611°N, 40.44611, -79.94889
_DD_RE = re.compile(
    r'(-?\d{1,3}\.\d+)\s*[°˚º]?\s*([NSEWnsew])?',
    re.IGNORECASE
)


def _classify_hemisphere(hem: str | None, is_lat: bool) -> str | None:
    """Determine if a hemisphere letter indicates lat or lon, return 'lat'/'lon' or None."""
    if hem is None:
        return None
    h = hem.upper()
    if h in ("N", "S"):
        return "lat"
    if h in ("E", "W"):
        return "lon"
    return None


def _apply_sign(value: float, hem: str | None, is_lat: bool) -> tuple[float, str | None]:
    """Apply hemisphere/sign and return (signed_dd, inferred_type)."""
    inferred = _classify_hemisphere(hem, is_lat)
    if hem is not None:
        h = hem.upper()
        if h in ("S", "W"):
            value = -abs(value)
        elif h in ("N", "E"):
            value = abs(value)
    return value, inferred


def _parse_single_token(token: str) -> tuple[float | None, str | None, str | None]:
    """Try to parse one token. Returns (dd_value, lat/lon type, format_name) or (None, None, None)."""
    token = token.strip()
    if not token:
        return None, None, None

    # Try DMS with symbols
    m = _DMS_SYMBOL_RE.fullmatch(token)
    if m:
        deg, min_val, sec, hem = float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(4)
        dd = abs(deg) + min_val / 60 + sec / 3600
        dd, inferred = _apply_sign(dd if deg >= 0 else -dd, hem, True)
        # If no hemisphere and negative sign present, infer from sign
        if inferred is None and deg < 0:
            inferred = "lon"  # negative -> likely longitude
        return dd, inferred, "DMS"

    # Try DMS with spaces/colons (only if not already matched by symbols pattern)
    m = _DMS_SPACE_RE.fullmatch(token)
    if m:
        deg, min_val, sec, hem = float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(4)
        dd = abs(deg) + min_val / 60 + sec / 3600
        dd, inferred = _apply_sign(dd if deg >= 0 else -dd, hem, True)
        if inferred is None and deg < 0:
            inferred = "lon"
        return dd, inferred, "DMS"

    # Try DD (before DDM to avoid false DDM match on plain decimals)
    m = _DD_RE.fullmatch(token)
    if m:
        val, hem = float(m.group(1)), m.group(2)
        dd = abs(val)
        dd, inferred = _apply_sign(dd if val >= 0 else -dd, hem, True)
        if inferred is None and val < 0:
            inferred = "lon"
        return dd, inferred, "DD"

    # Try DDM
    m = _DDM_RE.fullmatch(token)
    if m:
        deg, dec_min, hem = float(m.group(1)), float(m.group(2)), m.group(3)
        dd = abs(deg) + dec_min / 60
        dd, inferred = _apply_sign(dd if deg >= 0 else -dd, hem, True)
        if inferred is None and deg < 0:
            inferred = "lon"
        return dd, inferred, "DDM"

    return None, None, None


# ── Main parse function ────────────────────────────────────────

def parse(text: str) -> ParseResult:
    """Parse a coordinate string and return a ParseResult."""
    text = _normalize(text)
    if not text:
        return ParseResult(success=False, error_message="输入为空")

    # Split into tokens by common separators
    tokens = re.split(r'[,;，；\n]+', text)
    tokens = [t.strip() for t in tokens if t.strip()]

    # Split tokens at hemisphere boundaries (N/S/E/W followed by a digit)
    # e.g. "40 26 46 N 79 56 56 W" -> "40 26 46 N", "79 56 56 W"
    _HEM_BOUNDARY = re.compile(r'([NSEWnsew])\s+(?=\d)', re.IGNORECASE)
    expanded = []
    for t in tokens:
        parts = _HEM_BOUNDARY.sub(r'\1|', t).split('|')
        expanded.extend(parts)
    tokens = [t.strip() for t in expanded if t.strip()]

    # Step 1: try each token as a complete coordinate
    parsed_items: list[tuple[float, str | None, str]] = []  # (dd, type, format)
    for token in tokens:
        dd, inferred, fmt = _parse_single_token(token)
        if dd is not None and fmt is not None:
            parsed_items.append((dd, inferred, fmt))
        else:
            # Step 2: sub-split by spaces and try each sub-token
            sub_tokens = token.split()
            for st in sub_tokens:
                dd2, inf2, fmt2 = _parse_single_token(st)
                if dd2 is not None and fmt2 is not None:
                    parsed_items.append((dd2, inf2, fmt2))

    if not parsed_items:
        return ParseResult(
            success=False,
            error_message="无法识别坐标格式。支持格式: DD, DMS, DDM"
        )

    # Step 3: pair lat/lon
    pairs: list[tuple[float | None, float | None]] = []
    i = 0
    while i < len(parsed_items):
        dd, inferred, fmt = parsed_items[i]

        if i + 1 < len(parsed_items):
            dd2, inf2, fmt2 = parsed_items[i + 1]

            # If types are compatible (one lat one lon, or one typed and one not, or both untyped)
            type1 = inferred
            type2 = inf2

            can_pair = False
            if type1 == "lat" and type2 == "lon":
                can_pair = True
                lat_val, lon_val = dd, dd2
            elif type1 == "lon" and type2 == "lat":
                can_pair = True
                lat_val, lon_val = dd2, dd
            elif type1 == "lat" and type2 is None:
                can_pair = True
                lat_val, lon_val = dd, dd2
            elif type1 == "lon" and type2 is None:
                can_pair = True
                lat_val, lon_val = dd2, dd
            elif type2 == "lat" and type1 is None:
                can_pair = True
                lat_val, lon_val = dd2, dd
            elif type2 == "lon" and type1 is None:
                can_pair = True
                lat_val, lon_val = dd, dd2
            elif type1 is None and type2 is None:
                # Assume first is lat, second is lon
                can_pair = True
                lat_val, lon_val = dd, dd2
            elif type1 == "lat" and type2 == "lat":
                # Two lats: put each as single
                pairs.append((dd, None))
                pairs.append((dd2, None))
                i += 2
                continue
            elif type1 == "lon" and type2 == "lon":
                # Two lons: put each as single
                pairs.append((None, dd))
                pairs.append((None, dd2))
                i += 2
                continue

            if can_pair:
                pairs.append((lat_val, lon_val))
                i += 2
                continue

        # Can't pair, treat as single
        if inferred == "lat":
            pairs.append((dd, None))
        elif inferred == "lon":
            pairs.append((None, dd))
        else:
            # Untyped single value: could be lat or lon, assume lat
            pairs.append((dd, None))
        i += 1

    # Build result
    if not pairs:
        return ParseResult(
            success=False,
            error_message="无法解析坐标对"
        )

    # Validate
    for lat, lon in pairs:
        if lat is not None and not validate_lat(lat):
            return ParseResult(
                success=False,
                error_message=f"纬度值 {lat} 超出范围 (-90 到 90)"
            )
        if lon is not None and not validate_lon(lon):
            return ParseResult(
                success=False,
                error_message=f"经度值 {lon} 超出范围 (-180 到 180)"
            )

    first = pairs[0]
    detected_format = parsed_items[0][2] if parsed_items else "unknown"

    return ParseResult(
        success=True,
        format_detected=detected_format,
        lat=first[0],
        lon=first[1],
        pairs=pairs
    )
