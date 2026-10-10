# PostGIS + pgvector in one image.
# pgvector ships a postgis-enabled variant; build extensions from the official combo.
FROM postgis/postgis:16-3.4

# install pgvector against the bundled PG16
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

# init scripts run once on first cluster init (empty data dir), in filename order
COPY init.sql /docker-entrypoint-initdb.d/10-init.sql
COPY migrations/20_listings.sql /docker-entrypoint-initdb.d/20-listings.sql
COPY migrations/30_users.sql /docker-entrypoint-initdb.d/30-users.sql
COPY migrations/40_auth.sql /docker-entrypoint-initdb.d/40-auth.sql
COPY migrations/50_route_time.sql /docker-entrypoint-initdb.d/50-route-time.sql
COPY migrations/50_ugc.sql /docker-entrypoint-initdb.d/50-ugc.sql
COPY migrations/60_data_cleaning.sql /docker-entrypoint-initdb.d/60-data-cleaning.sql
COPY migrations/70_listing_classify.sql /docker-entrypoint-initdb.d/70-listing-classify.sql
# dữ liệu mẫu (12 tin + 4 tài khoản demo) — chạy cuối, sau khi mọi bảng đã có
COPY migrations/80_seeds.sql /docker-entrypoint-initdb.d/80-seeds.sql
# extras (điện/nước/cọc/giới tính) + places/place_reviews (Google Maps) + reviews (UGC)
COPY migrations/90_extras_reviews.sql /docker-entrypoint-initdb.d/90-extras-reviews.sql
# liên hệ (SĐT/Zalo) + địa chỉ chuẩn hoá + SĐT/website của place Google
COPY migrations/91_contact_address.sql /docker-entrypoint-initdb.d/91-contact-address.sql
# ghép bạn ở (swipes) + nhắn tin realtime (conversations/messages/chat_media/user_reports)
COPY migrations/92_matching_chat.sql /docker-entrypoint-initdb.d/92-matching-chat.sql
# deck log (server ghi vị trí/điểm đã hiển thị — không tin FE) + 2 cột lọc cứng còn thiếu
COPY migrations/93_matching_deck.sql /docker-entrypoint-initdb.d/93-matching-deck.sql
# đánh giá ghép bạn: deck_log.explore, ghép lại không mất vết unmatched, chấm điểm 1–5
COPY migrations/94_matching_eval.sql /docker-entrypoint-initdb.d/94-matching-eval.sql
# bản đồ v2: loại nha_mini, nhãn sang nhượng, bảng tiện ích OSM + cache đường đi ORS
COPY migrations/95_map_v2.sql /docker-entrypoint-initdb.d/95-map-v2.sql
# snapshot tiện ích OSM (Overpass) quanh 3 khu CTU — sinh bằng `python -m app.pois.fetch_overpass --sql`
COPY migrations/96_pois_seed.sql /docker-entrypoint-initdb.d/96-pois-seed.sql
# đánh giá mù hệ gợi ý nhà trọ (pooling 3 hệ, SV chấm 0–2)
COPY migrations/97_rec_eval.sql /docker-entrypoint-initdb.d/97-rec-eval.sql
# rà soát chất lượng: lý do loại tin (audit_reason) — app.cleaner.audit
COPY migrations/98_listing_audit.sql /docker-entrypoint-initdb.d/98-listing-audit.sql
# cờ vị trí chính xác — bản đồ mặc định chỉ cắm tin TRUE
COPY migrations/99_location_precise.sql /docker-entrypoint-initdb.d/98b-location-precise.sql
# chatbot: kho pháp lý/KTX, lịch sử hội thoại, cache câu trả lời (ADR-023). Tên 98c để chạy TRƯỚC 99-test-db.sh
COPY migrations/100_chatbot.sql /docker-entrypoint-initdb.d/98c-chatbot.sql
# DB riêng cho pytest (nckh_test) — chạy SAU mọi migration, áp lại đúng các file trên
COPY create_test_db.sh /docker-entrypoint-initdb.d/99-test-db.sh
COPY create_test_db.sh /usr/local/bin/create_test_db.sh
