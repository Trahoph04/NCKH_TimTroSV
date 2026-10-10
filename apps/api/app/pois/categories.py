"""Nhóm tiện ích cho SV ↔ tag OpenStreetMap. Đổi nhóm/tag CHỈ ở file này (fetch + API + FE đọc chung).

Chọn 6 nhóm theo khảo sát (tiêu chí "gần chợ/siêu thị, an ninh, y tế"): việc hằng ngày của SV
ở trọ — đi chợ, mua đồ, rút tiền, mua thuốc, khám bệnh, đi xe buýt.
"""

# key: (nhãn hiển thị, [(tag OSM, các giá trị khớp)])
CATEGORIES: dict[str, tuple[str, list[tuple[str, tuple[str, ...]]]]] = {
    "cho": ("Chợ", [("amenity", ("marketplace",))]),
    "sieu_thi": ("Siêu thị, cửa hàng tiện lợi", [("shop", ("supermarket", "convenience", "mall"))]),
    "atm": ("ATM, ngân hàng", [("amenity", ("atm", "bank"))]),
    "nha_thuoc": ("Nhà thuốc", [("amenity", ("pharmacy",)), ("healthcare", ("pharmacy",))]),
    "y_te": ("Bệnh viện, phòng khám", [("amenity", ("hospital", "clinic", "doctors"))]),
    "xe_buyt": ("Trạm xe buýt", [("highway", ("bus_stop",)), ("amenity", ("bus_station",))]),
}

LABELS: dict[str, str] = {k: v[0] for k, v in CATEGORIES.items()}

# tag giữ lại trong DB — đủ hiển thị, bỏ phần còn lại (SĐT/website cửa hàng không cần cho SV)
KEEP_TAGS = ("name", "brand", "operator", "opening_hours", "amenity", "shop", "healthcare",
             "highway", "addr:street", "addr:housenumber")


def category_of(tags: dict) -> str | None:
    """Tag OSM → key nhóm; None nếu không thuộc nhóm nào. Nhóm khai trước thắng (vd ATM trong siêu thị)."""
    for key, (_, rules) in CATEGORIES.items():
        for tag, values in rules:
            if tags.get(tag) in values:
                return key
    return None


def overpass_query(bbox: tuple[float, float, float, float], timeout: int = 90) -> str:
    """Query Overpass QL lấy mọi node/way/relation thuộc 6 nhóm trong bbox (S, W, N, E)."""
    s, w, n, e = bbox
    parts = []
    for _, rules in CATEGORIES.values():
        for tag, values in rules:
            regex = "|".join(values)
            parts.append(f'  nwr["{tag}"~"^({regex})$"]({s},{w},{n},{e});')
    return f"[out:json][timeout:{timeout}];\n(\n" + "\n".join(parts) + "\n);\nout center tags;"
