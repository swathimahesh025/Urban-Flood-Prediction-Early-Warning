import logging
import requests
from services.weather import KARNATAKA_MONITORED_ZONES, match_karnataka_zone, haversine_km

logger = logging.getLogger(__name__)

# Spatial reference catalog of non-monitored Karnataka districts, taluks, and Indian metro centers
KNOWN_SPATIAL_LOCATIONS = [
    # Karnataka Districts & Taluks
    ("Mysuru", 12.3156, 76.6172),   # GSSSIETW KRS Road, Mysuru
    ("Mandya", 12.5238, 76.8971),
    ("Hassan", 13.0072, 76.1030),
    ("Belagavi", 15.8497, 74.4977),
    ("Hubballi", 15.3647, 75.1240),
    ("Dharwad", 15.4589, 75.0078),
    ("Davanagere", 14.4644, 75.9218),
    ("Ballari", 15.1394, 76.9214),
    ("Tumakuru", 13.3392, 77.1017),
    ("Kalaburagi (Gulbarga)", 17.3297, 76.8343),
    ("Raichur", 16.2076, 77.3463),
    ("Bidar", 17.9104, 77.5199),
    ("Bagalkote", 16.1875, 75.6980),
    ("Vijayapura", 16.8302, 75.7100),
    ("Gadag", 15.4319, 75.6355),
    ("Haveri", 14.7952, 75.4053),
    ("Koppal", 15.3456, 76.1554),
    ("Yadgir", 16.7705, 77.1376),
    ("Chamarajanagara", 11.9261, 76.9437),
    ("Chikkaballapura", 13.4325, 77.7275),
    ("Chitradurga", 14.2251, 76.3980),
    ("Kolar", 13.1367, 78.1340),
    ("Ramanagara", 12.7209, 77.2799),
    ("Bengaluru Rural", 13.2257, 77.5750),
    ("Vijayanagara (Hosapete)", 15.2709, 76.3917),
    ("Nanjangud", 12.1190, 76.6800),
    ("Hunsur", 12.3100, 76.2900),
    ("Maddur", 12.5840, 77.0450),
    ("Channapatna", 12.6518, 77.2089),
    ("Kunigal", 13.0239, 77.0253),
    ("Tiptur", 13.2625, 76.4789),
    ("Arsikere", 13.3135, 76.2570),
    ("Sakleshpur", 12.9438, 75.7869),
    ("Gokak", 16.1667, 74.8333),
    ("Dandeli", 15.2447, 74.6225),
    ("Bhatkal", 13.9787, 74.5670),
    ("Sringeri", 13.4187, 75.2560),
    ("Sullia", 12.5630, 75.3900),
    ("Puttur", 12.7661, 75.2033),
    ("Bantwal", 12.8943, 75.0353),
    ("Karkala", 13.2144, 74.9984),
    ("Kundapura", 13.6267, 74.6917),
    ("Byndoor", 13.8744, 74.6294),
    # Indian Metros & Neighbouring Centers
    ("Panaji (Goa)", 15.4909, 73.8278),
    ("Hyderabad", 17.3850, 78.4867),
    ("Chennai", 13.0827, 80.2707),
    ("Mumbai", 19.0760, 72.8777),
    ("Pune", 18.5204, 73.8567),
    ("Coimbatore", 11.0168, 76.9558),
    ("Kozhikode", 11.2588, 75.7804),
    ("Kochi", 9.9312, 76.2673),
    ("Delhi", 28.6139, 77.2090),
    ("Kolkata", 22.5726, 88.3639)
]

def sanitize_coordinates(lat, lon):
    """Validates and sanitizes GPS coordinates."""
    try:
        f_lat = float(lat)
        f_lon = float(lon)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid coordinate format: lat={lat}, lon={lon}")

    if not (-90.0 <= f_lat <= 90.0):
        raise ValueError(f"Latitude out of bounds [-90, 90]: {f_lat}")
    if not (-180.0 <= f_lon <= 180.0):
        raise ValueError(f"Longitude out of bounds [-180, 180]: {f_lon}")

    return round(f_lat, 6), round(f_lon, 6)

def detect_place_name(lat, lon):
    """
    Identifies the human-readable geographic place name for given GPS coordinates.
    Attempts reverse geocoding via OpenStreetMap Nominatim, falling back to 
    an offline spatial lookup across Karnataka districts and Indian centers.
    """
    try:
        f_lat = float(lat)
        f_lon = float(lon)
    except (TypeError, ValueError):
        return f"Coordinates ({lat}, {lon})"

    # 1. Attempt online reverse-geocoding via OpenStreetMap Nominatim (with short 1.5s timeout)
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={f_lat}&lon={f_lon}&zoom=11"
        res = requests.get(url, headers={"User-Agent": "HydroAlert-Karnataka/2.5"}, timeout=1.5)
        if res.status_code == 200:
            payload = res.json()
            address = payload.get("address", {})
            name = (
                address.get("city") or 
                address.get("town") or 
                address.get("county") or 
                address.get("state_district") or 
                address.get("suburb") or 
                address.get("village")
            )
            if name:
                return name.strip()
    except Exception as e:
        logger.debug("Online reverse geocoding unavailable: %s", e)

    # 2. Offline spatial proximity detection against known Karnataka & Indian locations
    closest_name = None
    min_dist = float("inf")

    for name, c_lat, c_lon in KNOWN_SPATIAL_LOCATIONS:
        d = haversine_km(f_lat, f_lon, c_lat, c_lon)
        if d < min_dist:
            min_dist = d
            closest_name = name

    # If within 75 km of a known district or town center, identify by that name
    if closest_name and min_dist <= 75.0:
        return closest_name

    # If in Karnataka boundary box but beyond 75 km of major centers
    if (11.0 <= f_lat <= 18.8) and (73.5 <= f_lon <= 78.8):
        return f"Karnataka Region ({f_lat:.2f}, {f_lon:.2f})"

    return f"Location ({f_lat:.2f}, {f_lon:.2f})"

def resolve_karnataka_location(city_name=None, lat=None, lon=None):
    """
    Validates location strictly against the 7 Karnataka designated flood zones.
    Returns matched zone object or None (indicating Outside Surveillance Bounds).
    """
    return match_karnataka_zone(city_name=city_name, lat=lat, lon=lon)
