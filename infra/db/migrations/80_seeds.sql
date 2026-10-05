-- ====================================================================
-- 80_seeds.sql: Mock data & seed data for development & team sharing
-- Dữ liệu mẫu chuẩn cho Đại học Cần Thơ (CTU Khu 1, Khu 2, Khu 3)
-- ====================================================================

-- 1. SEED USERS & IDENTITIES (Mật khẩu mặc định: '123456' - bcrypt hash)
-- Hash: $2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW
INSERT INTO users (id, email, name, role, email_verified, phone)
VALUES 
    (1, 'admin@ctu.edu.vn', 'Quản Trị Viên CTU', 'admin', true, '0901234567'),
    (2, 'nguyenvana@ctu.edu.vn', 'Nguyễn Văn A (K47 CNTT)', 'user', true, '0912345678'),
    (3, 'tranthib@ctu.edu.vn', 'Trần Thị B (K48 Kinh Tế)', 'user', true, '0923456789'),
    (4, 'chutro.xuanhuong@gmail.com', 'Chủ Trọ Cô Xuân', 'user', true, '0934567890')
ON CONFLICT (id) DO NOTHING;

SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));

INSERT INTO user_identities (user_id, provider, provider_user_id, secret_hash)
VALUES
    (1, 'local', 'admin@ctu.edu.vn', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW'),
    (2, 'ctu', 'B2101234', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW'),
    (2, 'local', 'nguyenvana@ctu.edu.vn', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW'),
    (3, 'ctu', 'B2205678', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW'),
    (3, 'local', 'tranthib@ctu.edu.vn', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW'),
    (4, 'local', 'chutro.xuanhuong@gmail.com', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW')
ON CONFLICT (provider, provider_user_id) DO NOTHING;

-- 2. SEED ROOMMATE PROFILES (Tìm bạn ở ghép)
INSERT INTO roommate_profiles (user_id, sleep_time, cleanliness, smoke, noise_tolerance, gender_pref, bio)
VALUES
    (2, 2, 4, false, 3, 1, 'Sinh viên K47 CNTT cần tìm 1 bạn nam ở ghép hẻm 51 3/2, gọn gàng, thức khuya học bài không ồn ào.'),
    (3, 1, 5, false, 2, 2, 'Sinh viên K48 Nữ tìm bạn nữ ở ghép gần CTU Khu 2, tính tình hòa đồng, sạch sẽ, không hút thuốc.')
ON CONFLICT (user_id) DO NOTHING;

-- 3. SEED AGGREGATED LISTINGS (Nhà trọ & Phòng trọ quanh Đại học Cần Thơ)
INSERT INTO aggregated_listings (
    id, title, price, area, address, district, geom, images, description,
    source, source_url, source_id, content_hash, parsed_amenities,
    risk_score, risk_reasons, distance_to_ctu, geocode_confidence,
    status, posted_by, route_time_campus, cleaning_status, listing_type, quality_score
) VALUES 
(
    1,
    'Phòng trọ mới xây hẻm 51 đường 3/2 - Gần CTU Khu 2',
    1600000,
    20.0,
    'Hẻm 51 Đường 3/2, Phường Xuân Khánh, Quận Ninh Kiều, Cần Thơ',
    'Ninh Kiều',
    ST_SetSRID(ST_MakePoint(105.7689, 10.0299), 4326),
    ARRAY['https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600', 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600'],
    'Phòng trọ có gác lửng, giờ giấc tự do, có wifi tốc độ cao, camera an ninh 24/7. Cách cổng C ĐH Cần Thơ 300m, thuận tiện đi bộ đi học.',
    'chotot',
    'https://nhatot.com/thue-phong-tro-ninh-kieu-can-tho/101.htm',
    'ct_001',
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    '{"wifi": true, "air_conditioner": true, "parking": true, "private_bathroom": true, "mezzanine": true}'::jsonb,
    0.02,
    ARRAY[]::TEXT[],
    300.0,
    'high',
    'active',
    NULL,
    ARRAY[8.0, 3.0, 10.5],
    'cleaned',
    'phong_tro',
    0.95
),
(
    2,
    'Phòng trọ máy lạnh hẻm 132 đường 3/2 - An ninh tốt',
    1800000,
    22.0,
    'Hẻm 132 Đường 3/2, Phường Hưng Lợi, Quận Ninh Kiều, Cần Thơ',
    'Ninh Kiều',
    ST_SetSRID(ST_MakePoint(105.7650, 10.0255), 4326),
    ARRAY['https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600'],
    'Trang bị sẵn máy lạnh, tủ lạnh, giường nệm. Khu vực an ninh, không ngập nước khi mưa lớn, gần chợ Da Liễu.',
    'nhatot',
    'https://nhatot.com/thue-phong-tro-ninh-kieu-can-tho/102.htm',
    'nt_002',
    'a3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b856',
    '{"wifi": true, "air_conditioner": true, "refrigerator": true, "parking": true, "private_bathroom": true}'::jsonb,
    0.05,
    ARRAY[]::TEXT[],
    650.0,
    'high',
    'active',
    NULL,
    ARRAY[6.5, 5.0, 12.0],
    'cleaned',
    'phong_tro',
    0.92
),
(
    3,
    'Ký túc xá mini / Giường Sleepbox cao cấp đường 30/4 (Gần CTU Khu 1)',
    1100000,
    15.0,
    'Đường 30/4, Phường Hưng Lợi, Quận Ninh Kiều, Cần Thơ',
    'Ninh Kiều',
    ST_SetSRID(ST_MakePoint(105.7780, 10.0340), 4326),
    ARRAY['https://images.unsplash.com/photo-1555854877-bab0e564b8d5?w=600'],
    'Mô hình Sleepbox riêng tư bao trọn gói điện nước wifi, máy giặt chung, bếp chung. Cách CTU Khu 1 chỉ 200m.',
    'chotot',
    'https://nhatot.com/thue-phong-tro-ninh-kieu-can-tho/103.htm',
    'ct_003',
    'b3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b857',
    '{"wifi": true, "air_conditioner": true, "washing_machine": true, "kitchen": true}'::jsonb,
    0.01,
    ARRAY[]::TEXT[],
    1200.0,
    'high',
    'active',
    NULL,
    ARRAY[2.0, 8.0, 14.0],
    'cleaned',
    'phong_tro',
    0.98
),
(
    4,
    'Nhà nguyên căn 2 phòng ngủ KDC Metro (Gần CTU Khu 3)',
    4200000,
    60.0,
    'Khu Dân Cư Metro, Phường Hưng Lợi, Quận Ninh Kiều, Cần Thơ',
    'Ninh Kiều',
    ST_SetSRID(ST_MakePoint(105.7550, 10.0380), 4326),
    ARRAY['https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=600'],
    'Nhà nguyên căn 1 trệt 1 lầu, 2 phòng ngủ, thích hợp nhóm 3-4 bạn sinh viên thuê chung. Đường trước nhà 6m.',
    'ugc',
    NULL,
    'ugc_004',
    'c3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b858',
    '{"wifi": true, "parking": true, "kitchen": true, "balcony": true}'::jsonb,
    0.00,
    ARRAY[]::TEXT[],
    1800.0,
    'high',
    'active',
    4,
    ARRAY[14.0, 6.0, 5.0],
    'cleaned',
    'nha_nguyen_can',
    0.90
),
(
    5,
    'Phòng trọ giá rẻ sinh viên hẻm 54 đường Trần Việt Châu',
    900000,
    14.0,
    'Hẻm 54 Trần Việt Châu, Phường An Hòa, Quận Ninh Kiều, Cần Thơ',
    'Ninh Kiều',
    ST_SetSRID(ST_MakePoint(105.7695, 10.0450), 4326),
    ARRAY['https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?w=600'],
    'Phòng trọ giá rẻ cho sinh viên tiết kiệm chi phí, có gác lửng, WC riêng, chủ trọ thân thiện.',
    'chotot',
    'https://nhatot.com/thue-phong-tro-ninh-kieu-can-tho/105.htm',
    'ct_005',
    'd3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b859',
    '{"wifi": true, "parking": true, "private_bathroom": true, "mezzanine": true}'::jsonb,
    0.10,
    ARRAY['Giá thấp hơn mức trung bình khu vực']::TEXT[],
    2100.0,
    'medium',
    'active',
    NULL,
    ARRAY[15.0, 9.0, 6.0],
    'cleaned',
    'phong_tro',
    0.85
)
ON CONFLICT (id) DO NOTHING;

SELECT setval('aggregated_listings_id_seq', (SELECT MAX(id) FROM aggregated_listings));

-- 4. SEED SAMPLE USER INTERACTIONS & SEARCHES
INSERT INTO user_interactions (user_id, listing_id, type, duration_ms)
VALUES
    (2, 1, 'view', 45000),
    (2, 1, 'bookmark', 1200),
    (2, 2, 'view', 30000),
    (3, 1, 'view', 60000),
    (3, 3, 'bookmark', 2000)
ON CONFLICT DO NOTHING;

INSERT INTO saved_searches (user_id, criteria)
VALUES
    (2, '{"min_price": 1000000, "max_price": 2000000, "district": "Ninh Kiều", "amenities": ["wifi", "air_conditioner"]}'::jsonb),
    (3, '{"min_price": 1000000, "max_price": 1800000, "district": "Ninh Kiều", "amenities": ["wifi"]}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO crawl_runs (source, mode, fetched, new_count, updated_count, expired_count)
VALUES 
    ('chotot', 'incremental', 25, 4, 18, 3),
    ('nhatot', 'incremental', 15, 2, 12, 1)
ON CONFLICT DO NOTHING;
