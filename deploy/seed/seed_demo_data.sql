-- =====================================================================
-- MuYiMusic 演示数据种子 (demo seed data)
-- 生成时间: 2026-08-07   |   由 deploy/seed/generate_seed_sql.py 生成
--
-- 特性: 所有 INSERT 均使用 ON CONFLICT DO NOTHING, 可重复执行(幂等);
--       排课时间使用相对当前日期的表达式, 任何环境执行都会落在未来。
-- 用途: 本地/测试/演示环境初始化模拟数据, 验证小程序端与管理后台流程。
-- =====================================================================
BEGIN;

-- 门店 -----------------------------------------------------------------
INSERT INTO stores (id, name, city, district, address, phone, latitude, longitude, status, sort_order)
VALUES
  ('a83966b0-19a4-58a4-a718-ea396d5a04f8', '木易音乐·徐汇旗舰店', '上海市', '徐汇区', '漕溪北路88号 音乐中心3层', '021-64081234', 31.188469, 121.437106, 'active', 10),
  ('802856c7-6f0d-57c4-b4db-307bb5d8110e', '木易音乐·朝阳店', '北京市', '朝阳区', '望京街10号 望京SOHO T2-203', '010-84701234', 39.987803, 116.469251, 'active', 10)
ON CONFLICT (id) DO NOTHING;

-- 门店首页内容块 ---------------------------------------------------------
INSERT INTO store_content_blocks (id, store_id, block_type, title, media_object_key, jump_type, jump_target, sort_order, status)
VALUES
  ('01989370-bf0b-52c0-814f-400fb62c5c01', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'image', '开学季 · 钢琴启蒙班火热招生中', 'seed/banner-piano.png', 'none', NULL, 10, 'enabled'),
  ('ea0a98b4-df6d-5443-bec8-b97d9ef777ea', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'image', '暑期吉他集训营 7 月开营', 'seed/banner-guitar.png', 'none', NULL, 20, 'enabled'),
  ('ab9fd67a-b1c0-57c4-9f6d-f8eeabe3128c', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'shortcut', '预约课程', NULL, 'internal', '/pages/schedule/index', 30, 'enabled'),
  ('3f308e94-489f-53e3-9dbb-fe9215ca99ef', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'shortcut', '课程商城', NULL, 'internal', '/pages/courses/index', 40, 'enabled'),
  ('c4b7f19a-4b61-509e-bdd0-b9d9289486b5', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'image', '英皇考级冲刺课 名师一对一', 'seed/banner-piano.png', 'none', NULL, 10, 'enabled'),
  ('ba5ffaea-03a0-5eae-a24a-8a0703e10f96', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'image', '成人零基础吉他速成', 'seed/banner-guitar.png', 'none', NULL, 20, 'enabled'),
  ('df251e4d-606a-50e3-bc31-9cc388f955f2', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'shortcut', '预约课程', NULL, 'internal', '/pages/schedule/index', 30, 'enabled'),
  ('2283fc3d-7fca-53c3-b974-91c9553830f7', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'shortcut', '课程商城', NULL, 'internal', '/pages/courses/index', 40, 'enabled')
ON CONFLICT (id) DO NOTHING;

-- 商品分类 ---------------------------------------------------------------
INSERT INTO categories (id, store_id, name, sort_order, is_enabled)
VALUES
  ('a1e97579-9ba0-5534-bf7f-e7da01fab5bd', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', '钢琴', 10, true),
  ('26be0cdf-a546-5aee-a285-92f854bef756', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', '吉他', 20, true),
  ('e9781908-cf1e-54e6-a520-a91e9f3c9636', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', '声乐', 30, true),
  ('6a3e7d8d-6854-5542-95ed-f3730eb09ae2', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '钢琴', 10, true),
  ('95d6f777-5d9b-53df-964b-16c9f12bcb1e', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '吉他', 20, true),
  ('3e295384-f8d2-543e-8bc9-58c74248a3d1', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '声乐', 30, true)
ON CONFLICT (id) DO NOTHING;

-- 课程商品 / SKU / 商品图 -------------------------------------------------
INSERT INTO products (id, store_id, category_id, name, summary, details, cover_object_key, status, published_at, sales_count, sort_order)
VALUES
  ('d74d5c3e-636a-594d-a1c5-1ba500242987', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'a1e97579-9ba0-5534-bf7f-e7da01fab5bd', '钢琴一对一启蒙课', '零基础钢琴启蒙，一对一教学，资深钢琴教师执教，注重基本功与乐感培养。', '教学特色：一对一因材施教，课前课后都有练习反馈。', 'seed/cover-piano-a.png', 'published', TIMESTAMPTZ '2026-07-24 09:00:00+08', 12, 10),
  ('b3d5a652-7525-545f-ba5e-aef1de57d800', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', '26be0cdf-a546-5aee-a285-92f854bef756', '吉他流行弹唱课', '流行弹唱入门到进阶，和弦、节奏、弹唱技巧全覆盖，轻松学会自弹自唱。', '教学特色：一对一因材施教，课前课后都有练习反馈。', 'seed/cover-guitar-a.png', 'published', TIMESTAMPTZ '2026-07-24 09:00:00+08', 8, 10),
  ('ab595055-3c07-57d4-829d-a6fb1bf94087', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'e9781908-cf1e-54e6-a520-a91e9f3c9636', '少儿声乐启蒙课', '面向 5-12 岁儿童，科学发声、气息训练、舞台表现力培养，寓教于乐。', '教学特色：一对一因材施教，课前课后都有练习反馈。', 'seed/cover-vocal-a.png', 'published', TIMESTAMPTZ '2026-07-24 09:00:00+08', 6, 10),
  ('41eb0dcb-1624-5c43-9da4-3b8a054b78b5', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '6a3e7d8d-6854-5542-95ed-f3730eb09ae2', '钢琴进阶考级课', '英皇考级专项辅导，演奏技巧与乐理同步提升，多年考级教学经验教师执教。', '教学特色：一对一因材施教，课前课后都有练习反馈。', 'seed/cover-piano-b.png', 'published', TIMESTAMPTZ '2026-07-24 09:00:00+08', 9, 10),
  ('8d04c7bb-6125-5350-94c7-badd29aeeaa7', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '95d6f777-5d9b-53df-964b-16c9f12bcb1e', '成人吉他速成课', '专为上班族设计的速成体系，4 节课掌握 3 首弹唱，碎片时间高效学习。', '教学特色：一对一因材施教，课前课后都有练习反馈。', 'seed/cover-guitar-b.png', 'published', TIMESTAMPTZ '2026-07-24 09:00:00+08', 15, 10),
  ('b3e34c7d-9e28-535b-a1c6-c75d35f98c21', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '3e295384-f8d2-543e-8bc9-58c74248a3d1', '声乐一对一精修课', '一对一定制发声方案，流行/美声/民族唱法均可，适合有基础的进阶学员。', '教学特色：一对一因材施教，课前课后都有练习反馈。', 'seed/cover-vocal-b.png', 'published', TIMESTAMPTZ '2026-07-24 09:00:00+08', 5, 10)
ON CONFLICT (id) DO NOTHING;

INSERT INTO product_skus (id, product_id, name, price_cents, lesson_count, validity_days, sort_order, is_active)
VALUES
  ('63f9ca20-811b-5a87-98d9-0a024bf17e45', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '1 节体验课', 9900, 1, 30, 10, true),
  ('95b504c3-27d3-5e69-984d-e924e15ac591', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '10 次卡', 288000, 10, 180, 20, true),
  ('8a557d47-53d0-5569-990a-471a7eace053', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '20 次卡', 528000, 20, 365, 30, true),
  ('31dfc21f-3273-56aa-afc3-3569e5e41383', 'b3d5a652-7525-545f-ba5e-aef1de57d800', '1 节体验课', 8800, 1, 30, 10, true),
  ('9f7c450b-b618-53ae-ab0c-3fb49f33afe5', 'b3d5a652-7525-545f-ba5e-aef1de57d800', '10 次卡', 198000, 10, 180, 20, true),
  ('e81ab13f-cfec-5e43-bb00-6cca070c7d03', 'ab595055-3c07-57d4-829d-a6fb1bf94087', '10 次卡', 228000, 10, 180, 10, true),
  ('813dc99e-aebc-5495-aefb-3af4125aec29', 'ab595055-3c07-57d4-829d-a6fb1bf94087', '20 次卡', 428000, 20, 365, 20, true),
  ('4dc2f972-918c-5934-baf7-a2f0bebb6009', '41eb0dcb-1624-5c43-9da4-3b8a054b78b5', '10 次卡', 328000, 10, 180, 10, true),
  ('a241d7c5-d1f5-531a-b707-fbe7fee1acf0', '41eb0dcb-1624-5c43-9da4-3b8a054b78b5', '20 次卡', 598000, 20, 365, 20, true),
  ('f5f379d1-945a-5973-b1dc-d05c57fd0816', '8d04c7bb-6125-5350-94c7-badd29aeeaa7', '4 次卡', 68800, 4, 90, 10, true),
  ('831e6781-719f-5cf6-8ffe-b2cee133fb8e', '8d04c7bb-6125-5350-94c7-badd29aeeaa7', '10 次卡', 158000, 10, 180, 20, true),
  ('2dd50c2e-748d-58c9-85b4-14d52fa5842e', 'b3e34c7d-9e28-535b-a1c6-c75d35f98c21', '10 次卡', 268000, 10, 180, 10, true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO product_images (id, product_id, object_key, sort_order)
VALUES
  ('f3342173-d840-5d58-aeca-bd4d9164864c', 'd74d5c3e-636a-594d-a1c5-1ba500242987', 'seed/img-store-a-1.png', 10),
  ('82f908ea-4986-57cf-b586-3a2d1cc21e72', 'd74d5c3e-636a-594d-a1c5-1ba500242987', 'seed/img-store-a-2.png', 20),
  ('d62795d9-9bc4-52e9-a25a-a72588b62615', 'd74d5c3e-636a-594d-a1c5-1ba500242987', 'seed/img-store-a-3.png', 30),
  ('898cf43b-3402-51a2-9be2-2a9cdf727e67', 'b3d5a652-7525-545f-ba5e-aef1de57d800', 'seed/img-store-a-1.png', 10),
  ('f5730635-94ef-5384-b818-3e1207c78fd1', 'b3d5a652-7525-545f-ba5e-aef1de57d800', 'seed/img-store-a-2.png', 20),
  ('740b3513-e210-5d44-a7bd-fcef005121d8', 'ab595055-3c07-57d4-829d-a6fb1bf94087', 'seed/img-store-a-1.png', 10),
  ('b6d384fe-32f8-5791-8881-3c056eb487c7', 'ab595055-3c07-57d4-829d-a6fb1bf94087', 'seed/img-store-a-2.png', 20),
  ('f822de2c-ddec-5c66-83b4-fd2df495b463', '41eb0dcb-1624-5c43-9da4-3b8a054b78b5', 'seed/img-store-b-1.png', 10),
  ('a33714ae-3008-51cd-b609-6d483cfd6882', '41eb0dcb-1624-5c43-9da4-3b8a054b78b5', 'seed/img-store-b-2.png', 20),
  ('b270636a-e413-570f-a704-5042c39e62fa', '8d04c7bb-6125-5350-94c7-badd29aeeaa7', 'seed/img-store-b-1.png', 10),
  ('2c1befc8-3dec-538e-8d5d-97fdf05b560c', '8d04c7bb-6125-5350-94c7-badd29aeeaa7', 'seed/img-store-b-2.png', 20),
  ('0feef202-55fa-5b4b-b125-a7cada11af7e', 'b3e34c7d-9e28-535b-a1c6-c75d35f98c21', 'seed/img-store-b-1.png', 10)
ON CONFLICT (id) DO NOTHING;

-- 教师 -------------------------------------------------------------------
INSERT INTO teachers (id, store_id, name, specialties, bio, is_active, sort_order)
VALUES
  ('fb562869-e227-5d72-920b-422c1fa5148b', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', '林婉清', '钢琴启蒙 / 考级辅导', '上海音乐学院钢琴系硕士，教龄 9 年，擅长儿童钢琴启蒙与英皇考级辅导。', true, 10),
  ('f93d227f-8ddd-5927-80fa-cad382483d67', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', '陈子昂', '吉他 / 尤克里里', '职业吉他手出身，教龄 6 年，教学风格轻松，注重即兴与乐感。', true, 20),
  ('8e5f13b4-9bf6-5142-ad0e-96feddfbe433', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '王若曦', '钢琴 / 英皇考级', '中央音乐学院钢琴系毕业，教龄 10 年，英皇考级通过率 95%。', true, 10),
  ('dfb32a7a-19f3-5b18-92c3-10eeb39da945', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '张悦', '声乐 / 合唱', '音乐学院声乐表演专业，前合唱团领唱，教龄 7 年。', true, 20)
ON CONFLICT (id) DO NOTHING;

-- 排课(相对未来时间, 每天 2 节 x 3 天, 每节 45 分钟) ----------------------
INSERT INTO class_schedules (id, store_id, teacher_id, product_id, course_name, starts_at, ends_at, capacity, reserved_count, status, notes)
VALUES
  ('9b3c6101-53b6-54a8-b952-9bd13b85709b', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'fb562869-e227-5d72-920b-422c1fa5148b', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '钢琴一对一', ((CURRENT_DATE + 2) + TIME '10:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 2) + TIME '10:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('2727f271-1bac-5599-9ecd-3db78e709754', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'fb562869-e227-5d72-920b-422c1fa5148b', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '钢琴一对一', ((CURRENT_DATE + 2) + TIME '15:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 2) + TIME '15:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('4b21cd6d-2c9f-5f2e-b4d3-d457d4126d77', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'fb562869-e227-5d72-920b-422c1fa5148b', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '钢琴一对一', ((CURRENT_DATE + 3) + TIME '10:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 3) + TIME '10:45') AT TIME ZONE 'Asia/Shanghai', 4, 1, 'open', ''),
  ('5eac5b26-29a9-5cbb-8027-7b89050ee563', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'fb562869-e227-5d72-920b-422c1fa5148b', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '钢琴一对一', ((CURRENT_DATE + 3) + TIME '15:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 3) + TIME '15:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('86a15c5a-569d-56a1-b675-43b13576a472', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'fb562869-e227-5d72-920b-422c1fa5148b', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '钢琴一对一', ((CURRENT_DATE + 4) + TIME '10:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 4) + TIME '10:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('1a49f927-f2cb-5912-848a-2a02dbdfabfc', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'fb562869-e227-5d72-920b-422c1fa5148b', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '钢琴一对一', ((CURRENT_DATE + 4) + TIME '15:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 4) + TIME '15:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('2ab4294c-f30b-5d2e-bb24-dcc44213fe72', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'f93d227f-8ddd-5927-80fa-cad382483d67', 'b3d5a652-7525-545f-ba5e-aef1de57d800', '吉他弹唱课', ((CURRENT_DATE + 2) + TIME '11:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 2) + TIME '11:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('e938e1c2-f062-5894-9605-9bc3f8d778de', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'f93d227f-8ddd-5927-80fa-cad382483d67', 'b3d5a652-7525-545f-ba5e-aef1de57d800', '吉他弹唱课', ((CURRENT_DATE + 2) + TIME '16:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 2) + TIME '16:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('ac460a5a-417b-5775-b2b2-2f2b624f5972', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'f93d227f-8ddd-5927-80fa-cad382483d67', 'b3d5a652-7525-545f-ba5e-aef1de57d800', '吉他弹唱课', ((CURRENT_DATE + 3) + TIME '11:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 3) + TIME '11:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('25bec67d-d792-5928-9115-fc635e98a351', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'f93d227f-8ddd-5927-80fa-cad382483d67', 'b3d5a652-7525-545f-ba5e-aef1de57d800', '吉他弹唱课', ((CURRENT_DATE + 3) + TIME '16:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 3) + TIME '16:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('a855efd2-1886-56f3-92c1-7a963446e2b3', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'f93d227f-8ddd-5927-80fa-cad382483d67', 'b3d5a652-7525-545f-ba5e-aef1de57d800', '吉他弹唱课', ((CURRENT_DATE + 4) + TIME '11:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 4) + TIME '11:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('366f0f15-96b0-5b87-822b-5962c726136a', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'f93d227f-8ddd-5927-80fa-cad382483d67', 'b3d5a652-7525-545f-ba5e-aef1de57d800', '吉他弹唱课', ((CURRENT_DATE + 4) + TIME '16:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 4) + TIME '16:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('42c4c554-0e4b-507e-b1df-c086a661fe3a', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '8e5f13b4-9bf6-5142-ad0e-96feddfbe433', '41eb0dcb-1624-5c43-9da4-3b8a054b78b5', '钢琴考级课', ((CURRENT_DATE + 2) + TIME '10:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 2) + TIME '10:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('9408d88f-5e95-59db-8990-942013492b05', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '8e5f13b4-9bf6-5142-ad0e-96feddfbe433', '41eb0dcb-1624-5c43-9da4-3b8a054b78b5', '钢琴考级课', ((CURRENT_DATE + 2) + TIME '15:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 2) + TIME '15:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('34704735-0558-5676-9b63-ac6144b536a6', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '8e5f13b4-9bf6-5142-ad0e-96feddfbe433', '41eb0dcb-1624-5c43-9da4-3b8a054b78b5', '钢琴考级课', ((CURRENT_DATE + 3) + TIME '10:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 3) + TIME '10:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('bc514c4f-c938-5d50-9b48-1c64c6a63032', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '8e5f13b4-9bf6-5142-ad0e-96feddfbe433', '41eb0dcb-1624-5c43-9da4-3b8a054b78b5', '钢琴考级课', ((CURRENT_DATE + 3) + TIME '15:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 3) + TIME '15:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('b657a506-c5ee-5771-b82c-c183bc9f7c1e', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '8e5f13b4-9bf6-5142-ad0e-96feddfbe433', '41eb0dcb-1624-5c43-9da4-3b8a054b78b5', '钢琴考级课', ((CURRENT_DATE + 4) + TIME '10:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 4) + TIME '10:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('9049fd3c-1e1f-589d-8153-c068dedae2f3', '802856c7-6f0d-57c4-b4db-307bb5d8110e', '8e5f13b4-9bf6-5142-ad0e-96feddfbe433', '41eb0dcb-1624-5c43-9da4-3b8a054b78b5', '钢琴考级课', ((CURRENT_DATE + 4) + TIME '15:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 4) + TIME '15:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('93a25c27-678b-5e8c-973f-f29866d55f19', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'dfb32a7a-19f3-5b18-92c3-10eeb39da945', 'b3e34c7d-9e28-535b-a1c6-c75d35f98c21', '声乐一对一', ((CURRENT_DATE + 2) + TIME '11:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 2) + TIME '11:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('3f4ab4fd-a42c-539c-ba77-8a4926244ba8', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'dfb32a7a-19f3-5b18-92c3-10eeb39da945', 'b3e34c7d-9e28-535b-a1c6-c75d35f98c21', '声乐一对一', ((CURRENT_DATE + 2) + TIME '16:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 2) + TIME '16:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('2eb992e8-cb5e-5711-b749-9f8af48e5d21', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'dfb32a7a-19f3-5b18-92c3-10eeb39da945', 'b3e34c7d-9e28-535b-a1c6-c75d35f98c21', '声乐一对一', ((CURRENT_DATE + 3) + TIME '11:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 3) + TIME '11:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('45f4b453-692d-59b9-9676-2eb60ed7c459', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'dfb32a7a-19f3-5b18-92c3-10eeb39da945', 'b3e34c7d-9e28-535b-a1c6-c75d35f98c21', '声乐一对一', ((CURRENT_DATE + 3) + TIME '16:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 3) + TIME '16:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('ffd71bac-c071-5e2c-84fa-b63e7b2f3479', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'dfb32a7a-19f3-5b18-92c3-10eeb39da945', 'b3e34c7d-9e28-535b-a1c6-c75d35f98c21', '声乐一对一', ((CURRENT_DATE + 4) + TIME '11:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 4) + TIME '11:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', ''),
  ('ac877149-5ec4-563e-bebd-986f1b1e6fb5', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'dfb32a7a-19f3-5b18-92c3-10eeb39da945', 'b3e34c7d-9e28-535b-a1c6-c75d35f98c21', '声乐一对一', ((CURRENT_DATE + 4) + TIME '16:00') AT TIME ZONE 'Asia/Shanghai', ((CURRENT_DATE + 4) + TIME '16:45') AT TIME ZONE 'Asia/Shanghai', 4, 0, 'open', '')
ON CONFLICT (id) DO NOTHING;

-- 用户与第三方账号 ---------------------------------------------------------
INSERT INTO users (id, nickname, avatar_url, phone, status)
VALUES
  ('183dcc88-8da3-59ae-a6a8-7422934d3d3e', '林晓', 'seed/avatar-u1.png', '13800138000', 'active'),
  ('891a2ad7-a830-5d2f-9717-b1454939efa1', '周雨桐', 'seed/avatar-u2.png', '13900139000', 'active'),
  ('80093b21-dec1-5b4a-822e-904ec4965a91', '吴一凡', 'seed/avatar-u3.png', '13700137000', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO provider_accounts (id, user_id, provider, provider_subject, last_login_at)
VALUES
  ('47c6a3df-a538-544e-9df9-cfc8b545669c', '183dcc88-8da3-59ae-a6a8-7422934d3d3e', 'h5', 'local_a620392336a3df767fb6d5b76a2d187e1c174b73ab5bafa1035a9a0131d031b9', TIMESTAMPTZ '2026-08-06 20:00:00+08'),
  ('15c30c5a-44ad-5621-a105-721a0ee663b4', '891a2ad7-a830-5d2f-9717-b1454939efa1', 'h5', 'local_c8444852e48c7cd689b2ec6f3ebe2547b323d100ef75233156f17877c5cfc811', TIMESTAMPTZ '2026-08-06 20:00:00+08'),
  ('8a65e31e-2f51-556e-af0b-b4fe0cd117fd', '80093b21-dec1-5b4a-822e-904ec4965a91', 'h5', 'local_9f96230e822984ee37491fd0c82490c42bb1e1eab74b965e1fab3a161b746c0c', TIMESTAMPTZ '2026-08-06 20:00:00+08')
ON CONFLICT (id) DO NOTHING;

-- 订单 / 订单项 / 课程权益 --------------------------------------------------
INSERT INTO orders (id, order_no, user_id, store_id, status, total_amount_cents, created_at)
VALUES
  ('c64adbe6-dc97-5f35-98cc-b47c7ad9404d', 'MO20260801001', '183dcc88-8da3-59ae-a6a8-7422934d3d3e', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'confirmed', 288000, TIMESTAMPTZ '2026-07-31 10:05:00+08'),
  ('8090895c-110d-5e4e-8bc2-7192e497e6a5', 'MO20260802002', '891a2ad7-a830-5d2f-9717-b1454939efa1', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', 'confirmed', 198000, TIMESTAMPTZ '2026-08-01 15:20:00+08'),
  ('7b5a5d01-99c1-567e-be4b-231797fe7e18', 'MO20260803003', '80093b21-dec1-5b4a-822e-904ec4965a91', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'confirmed', 268000, TIMESTAMPTZ '2026-08-02 11:00:00+08')
ON CONFLICT (id) DO NOTHING;

INSERT INTO order_items (id, order_id, product_id, product_sku_id, product_name, sku_name, unit_price_cents, quantity, total_amount_cents, lesson_count, validity_days)
VALUES
  ('69c5358d-a1d8-5dba-829f-8320e81a0d6d', 'c64adbe6-dc97-5f35-98cc-b47c7ad9404d', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '95b504c3-27d3-5e69-984d-e924e15ac591', '钢琴一对一启蒙课', '10 次卡', 288000, 1, 288000, 10, 180),
  ('2cb60484-6c28-5f5f-b953-809157a34ed3', '8090895c-110d-5e4e-8bc2-7192e497e6a5', 'b3d5a652-7525-545f-ba5e-aef1de57d800', '9f7c450b-b618-53ae-ab0c-3fb49f33afe5', '吉他流行弹唱课', '10 次卡', 198000, 1, 198000, 10, 180),
  ('d563aa44-0d20-5e3c-b784-2787871cf9fb', '7b5a5d01-99c1-567e-be4b-231797fe7e18', 'b3e34c7d-9e28-535b-a1c6-c75d35f98c21', '2dd50c2e-748d-58c9-85b4-14d52fa5842e', '声乐一对一精修课', '10 次卡', 268000, 1, 268000, 10, 180)
ON CONFLICT (id) DO NOTHING;

INSERT INTO course_entitlements (id, user_id, store_id, order_item_id, product_id, product_sku_id, course_name, total_lessons, remaining_lessons, reserved_lessons, valid_from, expires_at, status)
VALUES
  ('44d24b5d-998b-5b08-a41a-dcebffa271ae', '183dcc88-8da3-59ae-a6a8-7422934d3d3e', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', '69c5358d-a1d8-5dba-829f-8320e81a0d6d', 'd74d5c3e-636a-594d-a1c5-1ba500242987', '95b504c3-27d3-5e69-984d-e924e15ac591', '钢琴一对一启蒙课', 10, 8, 1, TIMESTAMPTZ '2026-07-31 10:00:00+08', TIMESTAMPTZ '2027-01-27 10:00:00+08', 'active'),
  ('971ef34e-e1e1-504c-a5b4-b224438530cb', '891a2ad7-a830-5d2f-9717-b1454939efa1', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', '2cb60484-6c28-5f5f-b953-809157a34ed3', 'b3d5a652-7525-545f-ba5e-aef1de57d800', '9f7c450b-b618-53ae-ab0c-3fb49f33afe5', '吉他流行弹唱课', 10, 10, 0, TIMESTAMPTZ '2026-07-31 10:00:00+08', TIMESTAMPTZ '2027-01-27 10:00:00+08', 'active'),
  ('d39aad2d-ea60-55e6-8b22-cb6ab35860ec', '80093b21-dec1-5b4a-822e-904ec4965a91', '802856c7-6f0d-57c4-b4db-307bb5d8110e', 'd563aa44-0d20-5e3c-b784-2787871cf9fb', 'b3e34c7d-9e28-535b-a1c6-c75d35f98c21', '2dd50c2e-748d-58c9-85b4-14d52fa5842e', '声乐一对一精修课', 10, 10, 0, TIMESTAMPTZ '2026-07-31 10:00:00+08', TIMESTAMPTZ '2027-01-27 10:00:00+08', 'active')
ON CONFLICT (id) DO NOTHING;

-- 预约(演示 1 条已预约的课程) ---------------------------------------------
INSERT INTO appointments (id, appointment_no, user_id, store_id, schedule_id, entitlement_id, status, booking_idempotency_key)
VALUES
  ('b3d9f6bd-ac90-5b36-9cc6-25e79b1f40f0', 'A20260810100000ABCDEF123456', '183dcc88-8da3-59ae-a6a8-7422934d3d3e', 'a83966b0-19a4-58a4-a718-ea396d5a04f8', '4b21cd6d-2c9f-5f2e-b4d3-d457d4126d77', '44d24b5d-998b-5b08-a41a-dcebffa271ae', 'reserved', 'seed-booking-u1-piano')
ON CONFLICT (id) DO NOTHING;

-- 权限 / 角色 / 运营账号 ---------------------------------------------------
INSERT INTO permissions (id, code, name)
VALUES
  ('738ba5d5-8c5e-516f-aff7-0d5d27b8e542', 'stores:manage', '管理门店'),
  ('ff1ad744-48ee-5d63-becc-d4e0dabd2bf1', 'store_content:manage', '管理门店首页内容'),
  ('40af0d6b-5482-5fe9-a1e0-b96e778fdc5c', 'products:manage', '管理课程商品'),
  ('d9c7bdf7-a453-59f3-b113-fc051e75ec92', 'users:read', '查询用户订单与课程权益'),
  ('ead9aa7d-2a93-55f4-9b40-479556e68a06', 'schedules:manage', '管理教师与排课'),
  ('f5a6f58c-7b34-5ad1-89f1-751624d8cc16', 'appointments:manage', '管理预约'),
  ('ef7edfb4-6c35-5f90-b699-c477c227583d', 'consumptions:manage', '执行消课与缺席'),
  ('2053eba7-7b0c-5500-bb9b-e22684ed529f', 'consumptions:reverse', '撤销消课'),
  ('0e0529cf-7ca3-52f0-ae13-572754c6723c', 'admins:manage', '管理运营账号')
ON CONFLICT (code) DO NOTHING;

INSERT INTO roles (id, code, name)
VALUES
  ('ce8f45c3-341c-5056-a2c8-f273a607b130', 'platform_admin', '平台管理员'),
  ('5ce0f841-7637-54fe-8877-409542d3b338', 'store_operator', '门店运营')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.code = 'platform_admin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.code = 'store_operator' AND p.code IN ('appointments:manage', 'consumptions:manage', 'products:manage', 'schedules:manage', 'store_content:manage', 'users:read')
ON CONFLICT DO NOTHING;

INSERT INTO admin_users (id, username, password_hash, is_active)
VALUES
  ('85cae213-2b4b-5d77-bd38-18c398414f80', 'admin', 'pbkdf2_sha256$600000$c2VlZC1hZG1pbi0yMDI2ISE=$63jD-pHOEujndQEX2vfNsgtcjof1MuoGSCa99WQvFFc=', true),
  ('65458ac4-2dce-5579-9453-d655c9e4d1a3', 'operator', 'pbkdf2_sha256$600000$c2VlZC1vcC0yMDI2ISEhISE=$QgT00QA1LAbk-if_hvFi_t6Qrdga5FLYJxgbewdAP9g=', true)
ON CONFLICT (username) DO NOTHING;

INSERT INTO admin_user_roles (admin_user_id, role_id)
SELECT a.id, r.id FROM admin_users a, roles r WHERE a.username = 'admin' AND r.code = 'platform_admin'
ON CONFLICT DO NOTHING;

INSERT INTO admin_user_roles (admin_user_id, role_id)
SELECT a.id, r.id FROM admin_users a, roles r WHERE a.username = 'operator' AND r.code = 'store_operator'
ON CONFLICT DO NOTHING;

-- 门店运营账号授权门店 store-a -------------------------------------------
INSERT INTO admin_user_stores (admin_user_id, store_id)
SELECT a.id, s.id FROM admin_users a, stores s WHERE a.username = 'operator' AND s.id = 'a83966b0-19a4-58a4-a718-ea396d5a04f8'
ON CONFLICT DO NOTHING;

COMMIT;
