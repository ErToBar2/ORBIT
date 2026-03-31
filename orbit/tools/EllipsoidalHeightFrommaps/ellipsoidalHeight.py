import requests
import numpy as np

HBG18_PATH = r"C:\Code\EllipsoidalHeightFrommaps\QuasyGeoidDatahBG18.txt"

def load_hbg18_grid(path):
    lats, lons, Ns = [], [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            lat, lon, n = map(float, parts[:3])
            lats.append(lat); lons.append(lon); Ns.append(n)

    uniq_lats = np.unique(lats)
    uniq_lons = np.unique(lons)
    N_grid = np.full((len(uniq_lats), len(uniq_lons)), np.nan)
    lat_idx = {v: i for i, v in enumerate(uniq_lats)}
    lon_idx = {v: j for j, v in enumerate(uniq_lons)}
    for la, lo, n in zip(lats, lons, Ns):
        N_grid[lat_idx[la], lon_idx[lo]] = n
    return uniq_lats, uniq_lons, N_grid

def bilinear_interpolate(lat, lon, lats, lons, Ngrid):
    i = np.searchsorted(lats, lat) - 1
    j = np.searchsorted(lons, lon) - 1
    i = np.clip(i, 0, len(lats)-2)
    j = np.clip(j, 0, len(lons)-2)
    lat1, lat2 = lats[i], lats[i+1]
    lon1, lon2 = lons[j], lons[j+1]
    Q11, Q21 = Ngrid[i, j], Ngrid[i+1, j]
    Q12, Q22 = Ngrid[i, j+1], Ngrid[i+1, j+1]
    t = (lat - lat1)/(lat2 - lat1)
    u = (lon - lon1)/(lon2 - lon1)
    return (1-t)*(1-u)*Q11 + t*(1-u)*Q21 + (1-t)*u*Q12 + t*u*Q22

def get_elevation(lat, lon):
    """Query Open-Elevation API, returns H in meters (EGM96-like)."""
    url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["results"][0]["elevation"]

def main():
    lats, lons, Ngrid = load_hbg18_grid(HBG18_PATH)
    coord_str = input("Lat, Lon: ").strip()
    lat, lon = map(float, coord_str.replace(",", " ").split()[:2])

    # Step 1: orthometric height H from elevation API
    H = get_elevation(lat, lon)

    # Step 2: quasi-geoid undulation N from hBG18
    N = bilinear_interpolate(lat, lon, lats, lons, Ngrid)

    # Step 3: ellipsoidal height
    h = H + N

    print(f"At ({lat:.6f}, {lon:.6f}):")
    print(f"  H (orthometric, API) = {H:.2f} m")
    print(f"  N (hBG18)           = {N:.2f} m")
    print(f"  h = H + N            = {h:.2f} m (ellipsoidal)")

if __name__ == "__main__":
    main()
