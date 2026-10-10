"""ORS routing: route time (Matrix) + geometry (Directions). Xem docs/specs/Map_Routing.md.

GOTCHA: ORS dùng thứ tự [lng, lat], NGƯỢC với DB [lat, lng]. Luôn xếp [lng, lat].
"""
import httpx

from app.config import settings

# 3 campus CTU (lat, lng) — chốt 2026-07-06, xem Map_Routing.md. Index 0/1/2 = khu I/II/III.
CAMPUSES: list[tuple[float, float]] = [
    (10.0159, 105.7656),  # khu I
    (10.0322, 105.7683),  # khu II
    (10.0340, 105.7798),  # khu III
]

_BASE = "https://api.openrouteservice.org/v2"
PROFILE = "driving-car"  # ponytail: xấp xỉ xe máy, đủ để rank; đổi khi cần chính xác tuyệt đối


def _matrix_body(points: list[tuple[float, float]]) -> dict:
    """Dựng body Matrix: sources = points, destinations = 3 campus. Xếp [lng, lat] cho ORS."""
    locations = [[lng, lat] for lat, lng in points] + [[lng, lat] for lat, lng in CAMPUSES]
    n = len(points)
    return {
        "locations": locations,
        "sources": list(range(n)),
        "destinations": [n, n + 1, n + 2],
        "metrics": ["duration"],
    }


async def matrix_minutes(
    points: list[tuple[float, float]],
) -> list[list[float | None] | None]:
    """Route time (phút) từ mỗi điểm (lat,lng) tới 3 campus. Trả [[khuI,II,III], ...].

    1 call: sources = points, destinations = 3 campus. None nếu ORS không tính được cặp đó.
    """
    if not settings.ors_api_key:
        raise RuntimeError("ORS_API_KEY chưa set — không route được")
    if not points:
        return []

    body = _matrix_body(points)
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{_BASE}/matrix/{PROFILE}",
            json=body,
            headers={"Authorization": settings.ors_api_key},
        )
        resp.raise_for_status()
        durations = resp.json()["durations"]  # giây, [source][dest]
    return [
        [round(d / 60, 1) if d is not None else None for d in row] for row in durations
    ]


async def route_geometry(
    origin: tuple[float, float], dest: tuple[float, float]
) -> list[list[float]]:
    """Đường đi thật origin→dest (cả 2 là lat,lng). Trả list [lat,lng] để vẽ polyline."""
    if not settings.ors_api_key:
        raise RuntimeError("ORS_API_KEY chưa set — không route được")
    body = {"coordinates": [[origin[1], origin[0]], [dest[1], dest[0]]]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{_BASE}/directions/{PROFILE}/geojson",
            json=body,
            headers={"Authorization": settings.ors_api_key},
        )
        resp.raise_for_status()
        coords = resp.json()["features"][0]["geometry"]["coordinates"]  # [lng,lat]
    return [[lat, lng] for lng, lat in coords]


# Dự phòng khi ORS hết quota Directions (403 cả ngày 07/10): máy chủ OSRM công khai — cùng dữ liệu OpenStreetMap, không
# cần key, chỉ dành cho lưu lượng nhẹ (~1 request/giây) nên mọi kết quả đều được lưu vào route_cache.
OSRM_BASE = "https://router.project-osrm.org"
OSRM_PROFILE = "osrm-driving"  # khoá cache riêng: không ghi đường OSRM dưới tên profile của ORS
_UA = {"User-Agent": "TroCTU-NCKH/1.0 (contact: phub2303891@student.ctu.edu.vn)"}


async def route_geometry_osrm(
    origin: tuple[float, float], dest: tuple[float, float]
) -> list[list[float]]:
    """Như route_geometry nhưng qua OSRM. origin/dest là (lat, lng); OSRM nhận lng,lat trong URL."""
    url = f"{OSRM_BASE}/route/v1/driving/{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
    async with httpx.AsyncClient(timeout=20.0, headers=_UA) as client:
        resp = await client.get(url, params={"overview": "full", "geometries": "geojson"})
        resp.raise_for_status()
        data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError(f"OSRM: {data.get('code')} {data.get('message', '')}")
    return [[lat, lng] for lng, lat in data["routes"][0]["geometry"]["coordinates"]]


if __name__ == "__main__":
    # self-check: body dựng đúng thứ tự [lng,lat] + campus đúng vị trí destination
    tro = (10.05, 105.77)  # 1 tin (lat, lng)
    b = _matrix_body([tro])
    assert b["locations"][0] == [105.77, 10.05], "point phải [lng,lat], không [lat,lng]"
    assert b["locations"][1] == [105.7656, 10.0159], "campus khu I sai vị trí/thứ tự"
    assert b["sources"] == [0] and b["destinations"] == [1, 2, 3], "index sai"
    assert len(b["locations"]) == 4, "1 tin + 3 campus = 4 locations"
    print("routing self-check OK")
