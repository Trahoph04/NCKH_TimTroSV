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
