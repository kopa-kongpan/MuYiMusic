"""Generate a deterministic, idempotent demo-data seed SQL for MuYiMusic.

Usage:  python deploy/seed/generate_seed_sql.py  (run from repo root)
Output: deploy/seed/seed_demo_data.sql

All primary keys are derived from uuid5(name) so re-running this script
always produces the same SQL, and every INSERT uses ON CONFLICT DO NOTHING,
so the generated file can be re-executed safely on any environment.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent / "seed_demo_data.sql"

NS = uuid.UUID("7b7c6d3e-4a1f-4b2c-9d3e-8f0a1b2c3d4e")


def uid(name: str) -> str:
    """Deterministic UUID for a given logical key."""
    return str(uuid.uuid5(NS, name))


def sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_ts(value: datetime) -> str:
    return f"TIMESTAMPTZ '{value:%Y-%m-%d %H:%M:%S}+08'"


def ts(*, days: int, hour: int, minute: int = 0) -> datetime:
    """Fixed timestamptz in UTC+8: seed date + offset days at the given hour."""
    return datetime(2026, 8, 7, hour, minute) + timedelta(days=days)


# ---------------------------------------------------------------- data ----

STORES = [
    dict(
        key="store-a",
        name="木易音乐·徐汇旗舰店",
        city="上海市",
        district="徐汇区",
        address="漕溪北路88号 音乐中心3层",
        phone="021-64081234",
        lat="31.188469",
        lng="121.437106",
    ),
    dict(
        key="store-b",
        name="木易音乐·朝阳店",
        city="北京市",
        district="朝阳区",
        address="望京街10号 望京SOHO T2-203",
        phone="010-84701234",
        lat="39.987803",
        lng="116.469251",
    ),
]

CONTENT_BLOCKS = [
    # (store_key, block_type, title, media_key, jump_type, jump_target, sort)
    ("store-a", "image", "开学季 · 钢琴启蒙班火热招生中", "seed/banner-piano.png", "none", None, 10),
    ("store-a", "image", "暑期吉他集训营 7 月开营", "seed/banner-guitar.png", "none", None, 20),
    ("store-a", "shortcut", "预约课程", None, "internal", "/pages/schedule/index", 30),
    ("store-a", "shortcut", "课程商城", None, "internal", "/pages/courses/index", 40),
    ("store-b", "image", "英皇考级冲刺课 名师一对一", "seed/banner-piano.png", "none", None, 10),
    ("store-b", "image", "成人零基础吉他速成", "seed/banner-guitar.png", "none", None, 20),
    ("store-b", "shortcut", "预约课程", None, "internal", "/pages/schedule/index", 30),
    ("store-b", "shortcut", "课程商城", None, "internal", "/pages/courses/index", 40),
]

CATEGORIES = [
    ("store-a", "钢琴", 10),
    ("store-a", "吉他", 20),
    ("store-a", "声乐", 30),
    ("store-b", "钢琴", 10),
    ("store-b", "吉他", 20),
    ("store-b", "声乐", 30),
]

PRODUCTS = [
    # store_key, category, name, summary, cover, sales, skus[(name, price, lessons, validity_days)]
    ("store-a", "钢琴", "钢琴一对一启蒙课",
     "零基础钢琴启蒙，一对一教学，资深钢琴教师执教，注重基本功与乐感培养。",
     "seed/cover-piano-a.png", 12,
     [("1 节体验课", 9900, 1, 30), ("10 次卡", 288000, 10, 180), ("20 次卡", 528000, 20, 365)]),
    ("store-a", "吉他", "吉他流行弹唱课",
     "流行弹唱入门到进阶，和弦、节奏、弹唱技巧全覆盖，轻松学会自弹自唱。",
     "seed/cover-guitar-a.png", 8,
     [("1 节体验课", 8800, 1, 30), ("10 次卡", 198000, 10, 180)]),
    ("store-a", "声乐", "少儿声乐启蒙课",
     "面向 5-12 岁儿童，科学发声、气息训练、舞台表现力培养，寓教于乐。",
     "seed/cover-vocal-a.png", 6,
     [("10 次卡", 228000, 10, 180), ("20 次卡", 428000, 20, 365)]),
    ("store-b", "钢琴", "钢琴进阶考级课",
     "英皇考级专项辅导，演奏技巧与乐理同步提升，多年考级教学经验教师执教。",
     "seed/cover-piano-b.png", 9,
     [("10 次卡", 328000, 10, 180), ("20 次卡", 598000, 20, 365)]),
    ("store-b", "吉他", "成人吉他速成课",
     "专为上班族设计的速成体系，4 节课掌握 3 首弹唱，碎片时间高效学习。",
     "seed/cover-guitar-b.png", 15,
     [("4 次卡", 68800, 4, 90), ("10 次卡", 158000, 10, 180)]),
    ("store-b", "声乐", "声乐一对一精修课",
     "一对一定制发声方案，流行/美声/民族唱法均可，适合有基础的进阶学员。",
     "seed/cover-vocal-b.png", 5,
     [("10 次卡", 268000, 10, 180)]),
]

TEACHERS = [
    # store_key, name, specialties, bio, sort
    ("store-a", "林婉清", "钢琴启蒙 / 考级辅导", "上海音乐学院钢琴系硕士，教龄 9 年，擅长儿童钢琴启蒙与英皇考级辅导。", 10),
    ("store-a", "陈子昂", "吉他 / 尤克里里", "职业吉他手出身，教龄 6 年，教学风格轻松，注重即兴与乐感。", 20),
    ("store-b", "王若曦", "钢琴 / 英皇考级", "中央音乐学院钢琴系毕业，教龄 10 年，英皇考级通过率 95%。", 10),
    ("store-b", "张悦", "声乐 / 合唱", "音乐学院声乐表演专业，前合唱团领唱，教龄 7 年。", 20),
]

# schedule plan: (store_key, teacher, course_name, product_idx, weekday_offsets, times)
# times are (hour, minute); each slot is 45 minutes.
SCHEDULE_PLAN = [
    ("store-a", "林婉清", "钢琴一对一", 0, [2, 3, 4], [(10, 0), (15, 0)]),
    ("store-a", "陈子昂", "吉他弹唱课", 1, [2, 3, 4], [(11, 0), (16, 0)]),
    ("store-b", "王若曦", "钢琴考级课", 3, [2, 3, 4], [(10, 0), (15, 0)]),
    ("store-b", "张悦", "声乐一对一", 5, [2, 3, 4], [(11, 0), (16, 0)]),
]

# The appointment demo: user u1 books the piano class on day+3 at 10:00 in store-a.
BOOKING = dict(
    user="u1",
    store="store-a",
    teacher="林婉清",
    day_offset=3,
    hour=10,
)

USERS = [
    # key, nickname, phone, avatar
    ("u1", "林晓", "13800138000", "seed/avatar-u1.png"),
    ("u2", "周雨桐", "13900139000", "seed/avatar-u2.png"),
    ("u3", "吴一凡", "13700137000", "seed/avatar-u3.png"),
]

# H5 login codes (>= 20 chars) whose sha256 becomes provider_subject="local_<hex>"
H5_CODES = {
    "u1": "seed-local-user-0001-abcdefghijklmnop",
    "u2": "seed-local-user-0002-abcdefghijklmnop",
    "u3": "seed-local-user-0003-abcdefghijklmnop",
}

ORDERS = [
    # user_key, store_key, order_no, created, product_name, sku_name,
    # qty, total_cents, lesson_count, validity_days, remaining, reserved
    ("u1", "store-a", "MO20260801001", ts(days=-7, hour=10, minute=5),
     "钢琴一对一启蒙课", "10 次卡", 1, 288000, 10, 180, 8, 1),
    ("u2", "store-a", "MO20260802002", ts(days=-6, hour=15, minute=20),
     "吉他流行弹唱课", "10 次卡", 1, 198000, 10, 180, 10, 0),
    ("u3", "store-b", "MO20260803003", ts(days=-5, hour=11, minute=0),
     "声乐一对一精修课", "10 次卡", 1, 268000, 10, 180, 10, 0),
]

ADMIN_PASSWORD_HASH = "pbkdf2_sha256$600000$c2VlZC1hZG1pbi0yMDI2ISE=$63jD-pHOEujndQEX2vfNsgtcjof1MuoGSCa99WQvFFc="
OPERATOR_PASSWORD_HASH = "pbkdf2_sha256$600000$c2VlZC1vcC0yMDI2ISEhISE=$QgT00QA1LAbk-if_hvFi_t6Qrdga5FLYJxgbewdAP9g="

PERMISSIONS = [
    ("stores:manage", "管理门店"),
    ("store_content:manage", "管理门店首页内容"),
    ("products:manage", "管理课程商品"),
    ("users:read", "查询用户订单与课程权益"),
    ("schedules:manage", "管理教师与排课"),
    ("appointments:manage", "管理预约"),
    ("consumptions:manage", "执行消课与缺席"),
    ("consumptions:reverse", "撤销消课"),
    ("admins:manage", "管理运营账号"),
]
OPERATOR_PERMISSIONS = {
    "store_content:manage",
    "products:manage",
    "users:read",
    "schedules:manage",
    "appointments:manage",
    "consumptions:manage",
}


def ts_relative(days: int, hour: int, minute: int = 0) -> str:
    """Timestamptz relative to the run date (so schedules stay in the future)."""
    return (
        f"((CURRENT_DATE + {days}) + TIME '{hour:02d}:{minute:02d}') "
        f"AT TIME ZONE 'Asia/Shanghai'"
    )


def build() -> str:
    sql: list[str] = []
    add = sql.append

    add("-- =====================================================================")
    add("-- MuYiMusic 演示数据种子 (demo seed data)")
    add("-- 生成时间: 2026-08-07   |   由 deploy/seed/generate_seed_sql.py 生成")
    add("--")
    add("-- 特性: 所有 INSERT 均使用 ON CONFLICT DO NOTHING, 可重复执行(幂等);")
    add("--       排课时间使用相对当前日期的表达式, 任何环境执行都会落在未来。")
    add("-- 用途: 本地/测试/演示环境初始化模拟数据, 验证小程序端与管理后台流程。")
    add("-- =====================================================================")
    add("BEGIN;")
    add("")

    # ------------------------------------------------------------ stores ----
    add("-- 门店 -----------------------------------------------------------------")
    add("INSERT INTO stores (id, name, city, district, address, phone, latitude, longitude, status, sort_order)")
    add("VALUES")
    rows = []
    for s in STORES:
        rows.append(
            f"  ({sql_str(uid(f'store:{s['key']}'))}, {sql_str(s['name'])}, {sql_str(s['city'])}, "
            f"{sql_str(s['district'])}, {sql_str(s['address'])}, {sql_str(s['phone'])}, "
            f"{s['lat']}, {s['lng']}, 'active', 10)"
        )
    add(",\n".join(rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    # -------------------------------------------------- store content blocks ----
    add("-- 门店首页内容块 ---------------------------------------------------------")
    add("INSERT INTO store_content_blocks (id, store_id, block_type, title, media_object_key, jump_type, jump_target, sort_order, status)")
    add("VALUES")
    rows = []
    for key, btype, title, media, jump, target, sort in CONTENT_BLOCKS:
        store_id = uid(f"store:{key}")
        media_sql = "NULL" if media is None else sql_str(media)
        target_sql = "NULL" if target is None else sql_str(target)
        rows.append(
            f"  ({sql_str(uid(f'block:{key}:{title}:{sort}'))}, {sql_str(store_id)}, {sql_str(btype)}, "
            f"{sql_str(title)}, {media_sql}, {sql_str(jump)}, {target_sql}, {sort}, 'enabled')"
        )
    add(",\n".join(rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    # ---------------------------------------------------------- categories ----
    add("-- 商品分类 ---------------------------------------------------------------")
    add("INSERT INTO categories (id, store_id, name, sort_order, is_enabled)")
    add("VALUES")
    rows = []
    for store_key, name, sort in CATEGORIES:
        rows.append(
            f"  ({sql_str(uid(f'category:{store_key}:{name}'))}, {sql_str(uid(f'store:{store_key}'))}, "
            f"{sql_str(name)}, {sort}, true)"
        )
    add(",\n".join(rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    # ------------------------------------------------------------ products ----
    add("-- 课程商品 / SKU / 商品图 -------------------------------------------------")
    product_rows = []
    sku_rows = []
    img_rows = []
    for store_key, cat, name, summary, cover, sales, skus in PRODUCTS:
        pkey = f"product:{store_key}:{name}"
        product_rows.append(
            f"  ({sql_str(uid(pkey))}, {sql_str(uid(f'store:{store_key}'))}, "
            f"{sql_str(uid(f'category:{store_key}:{cat}'))}, {sql_str(name)}, "
            f"{sql_str(summary)}, '教学特色：一对一因材施教，课前课后都有练习反馈。', "
            f"{sql_str(cover)}, 'published', {sql_ts(ts(days=-14, hour=9))}, {sales}, 10)"
        )
        for i, (sku_name, price, lessons, validity) in enumerate(skus, start=1):
            sku_rows.append(
                f"  ({sql_str(uid(f'sku:{store_key}:{name}:{sku_name}'))}, {sql_str(uid(pkey))}, "
                f"{sql_str(sku_name)}, {price}, {lessons}, {validity}, {i * 10}, true)"
            )
            img_rows.append(
                f"  ({sql_str(uid(f'img:{store_key}:{name}:{i}'))}, {sql_str(uid(pkey))}, "
                f"{sql_str(f'seed/img-{store_key}-{i}.png')}, {i * 10})"
            )
    add("INSERT INTO products (id, store_id, category_id, name, summary, details, cover_object_key, status, published_at, sales_count, sort_order)")
    add("VALUES")
    add(",\n".join(product_rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")
    add("INSERT INTO product_skus (id, product_id, name, price_cents, lesson_count, validity_days, sort_order, is_active)")
    add("VALUES")
    add(",\n".join(sku_rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")
    add("INSERT INTO product_images (id, product_id, object_key, sort_order)")
    add("VALUES")
    add(",\n".join(img_rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    # ------------------------------------------------------------- teachers ----
    add("-- 教师 -------------------------------------------------------------------")
    add("INSERT INTO teachers (id, store_id, name, specialties, bio, is_active, sort_order)")
    add("VALUES")
    rows = []
    for store_key, name, specialties, bio, sort in TEACHERS:
        rows.append(
            f"  ({sql_str(uid(f'teacher:{store_key}:{name}'))}, {sql_str(uid(f'store:{store_key}'))}, "
            f"{sql_str(name)}, {sql_str(specialties)}, {sql_str(bio)}, true, {sort})"
        )
    add(",\n".join(rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    # --------------------------------------------------------------- schedule ----
    add("-- 排课(相对未来时间, 每天 2 节 x 3 天, 每节 45 分钟) ----------------------")
    add("INSERT INTO class_schedules (id, store_id, teacher_id, product_id, course_name, starts_at, ends_at, capacity, reserved_count, status, notes)")
    add("VALUES")
    rows = []
    for store_key, teacher, course, prod_idx, offsets, times in SCHEDULE_PLAN:
        product_name = PRODUCTS[prod_idx][2]
        for day_offset in offsets:
            for hour, minute in times:
                start = ts_relative(day_offset, hour, minute)
                end = ts_relative(day_offset, hour, minute + 45)
                is_booked = (
                    store_key == BOOKING["store"]
                    and teacher == BOOKING["teacher"]
                    and day_offset == BOOKING["day_offset"]
                    and hour == BOOKING["hour"]
                )
                reserved = 1 if is_booked else 0
                rows.append(
                    f"  ({sql_str(uid(f'schedule:{store_key}:{teacher}:{day_offset}:{hour}'))}, "
                    f"{sql_str(uid(f'store:{store_key}'))}, {sql_str(uid(f'teacher:{store_key}:{teacher}'))}, "
                    f"{sql_str(uid(f'product:{store_key}:{product_name}'))}, {sql_str(course)}, "
                    f"{start}, {end}, 4, {reserved}, 'open', '')"
                )
    add(",\n".join(rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    # ---------------------------------------------------------------- users ----
    add("-- 用户与第三方账号 ---------------------------------------------------------")
    add("INSERT INTO users (id, nickname, avatar_url, phone, status)")
    add("VALUES")
    rows = []
    for key, nickname, phone, avatar in USERS:
        rows.append(
            f"  ({sql_str(uid(f'user:{key}'))}, {sql_str(nickname)}, {sql_str(avatar)}, "
            f"{sql_str(phone)}, 'active')"
        )
    add(",\n".join(rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")
    add("INSERT INTO provider_accounts (id, user_id, provider, provider_subject, last_login_at)")
    add("VALUES")
    rows = []
    for key, nickname, _phone, _avatar in USERS:
        import hashlib

        subject = "local_" + hashlib.sha256(H5_CODES[key].encode()).hexdigest()
        rows.append(
            f"  ({sql_str(uid(f'provider:{key}'))}, {sql_str(uid(f'user:{key}'))}, 'h5', "
            f"{sql_str(subject)}, {sql_ts(ts(days=-1, hour=20))})"
        )
    add(",\n".join(rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    # -------------------------------------------------------------- orders ----
    add("-- 订单 / 订单项 / 课程权益 --------------------------------------------------")
    add("INSERT INTO orders (id, order_no, user_id, store_id, status, total_amount_cents, created_at)")
    add("VALUES")
    rows = []
    for user_key, store_key, order_no, created, _pname, _sku, qty, total, _lc, _vd, _rem, _rsv in ORDERS:
        rows.append(
            f"  ({sql_str(uid(f'order:{order_no}'))}, {sql_str(order_no)}, "
            f"{sql_str(uid(f'user:{user_key}'))}, {sql_str(uid(f'store:{store_key}'))}, "
            f"'confirmed', {total}, {sql_ts(created)})"
        )
    add(",\n".join(rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    add("INSERT INTO order_items (id, order_id, product_id, product_sku_id, product_name, sku_name, unit_price_cents, quantity, total_amount_cents, lesson_count, validity_days)")
    add("VALUES")
    rows = []
    for user_key, store_key, order_no, created, product_name, sku_name, qty, total, lessons, validity, _rem, _rsv in ORDERS:
        rows.append(
            f"  ({sql_str(uid(f'item:{order_no}'))}, {sql_str(uid(f'order:{order_no}'))}, "
            f"{sql_str(uid(f'product:{store_key}:{product_name}'))}, "
            f"{sql_str(uid(f'sku:{store_key}:{product_name}:{sku_name}'))}, "
            f"{sql_str(product_name)}, {sql_str(sku_name)}, {total}, {qty}, {total}, {lessons}, {validity})"
        )
    add(",\n".join(rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    add("INSERT INTO course_entitlements (id, user_id, store_id, order_item_id, product_id, product_sku_id, course_name, total_lessons, remaining_lessons, reserved_lessons, valid_from, expires_at, status)")
    add("VALUES")
    rows = []
    for user_key, store_key, order_no, created, product_name, sku_name, qty, total, lessons, validity, remain, reserved in ORDERS:
        rows.append(
            f"  ({sql_str(uid(f'ent:{order_no}'))}, {sql_str(uid(f'user:{user_key}'))}, "
            f"{sql_str(uid(f'store:{store_key}'))}, {sql_str(uid(f'item:{order_no}'))}, "
            f"{sql_str(uid(f'product:{store_key}:{product_name}'))}, "
            f"{sql_str(uid(f'sku:{store_key}:{product_name}:{sku_name}'))}, "
            f"{sql_str(product_name)}, {lessons}, {remain}, {reserved}, "
            f"{sql_ts(ts(days=-7, hour=10))}, {sql_ts(ts(days=-7 + validity, hour=10))}, 'active')"
        )
    add(",\n".join(rows))
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    # ---------------------------------------------------------- appointment ----
    add("-- 预约(演示 1 条已预约的课程) ---------------------------------------------")
    booked_schedule = f"schedule:{BOOKING['store']}:{BOOKING['teacher']}:{BOOKING['day_offset']}:{BOOKING['hour']}"
    booked_store_id = uid(f"store:{BOOKING['store']}")
    add("INSERT INTO appointments (id, appointment_no, user_id, store_id, schedule_id, entitlement_id, status, booking_idempotency_key)")
    add("VALUES")
    add(
        f"  ({sql_str(uid('appointment:u1-piano'))}, 'A20260810100000ABCDEF123456', "
        f"{sql_str(uid('user:u1'))}, {sql_str(booked_store_id)}, "
        f"{sql_str(uid(booked_schedule))}, {sql_str(uid('ent:MO20260801001'))}, "
        f"'reserved', 'seed-booking-u1-piano')"
    )
    add("ON CONFLICT (id) DO NOTHING;")
    add("")

    # -------------------------------------------------------------- admins ----
    add("-- 权限 / 角色 / 运营账号 ---------------------------------------------------")
    add("INSERT INTO permissions (id, code, name)")
    add("VALUES")
    rows = [
        f"  ({sql_str(uid(f'perm:{code}'))}, {sql_str(code)}, {sql_str(name)})"
        for code, name in PERMISSIONS
    ]
    add(",\n".join(rows))
    add("ON CONFLICT (code) DO NOTHING;")
    add("")

    add("INSERT INTO roles (id, code, name)")
    add("VALUES")
    add(f"  ({sql_str(uid('role:platform_admin'))}, 'platform_admin', '平台管理员'),")
    add(f"  ({sql_str(uid('role:store_operator'))}, 'store_operator', '门店运营')")
    add("ON CONFLICT (code) DO NOTHING;")
    add("")

    add("INSERT INTO role_permissions (role_id, permission_id)")
    add("SELECT r.id, p.id FROM roles r, permissions p WHERE r.code = 'platform_admin'")
    add("ON CONFLICT DO NOTHING;")
    add("")
    add("INSERT INTO role_permissions (role_id, permission_id)")
    add(f"SELECT r.id, p.id FROM roles r, permissions p WHERE r.code = 'store_operator' AND p.code IN ({', '.join(sql_str(c) for c in sorted(OPERATOR_PERMISSIONS))})")
    add("ON CONFLICT DO NOTHING;")
    add("")

    add("INSERT INTO admin_users (id, username, password_hash, is_active)")
    add("VALUES")
    add(f"  ({sql_str(uid('admin:admin'))}, 'admin', {sql_str(ADMIN_PASSWORD_HASH)}, true),")
    add(f"  ({sql_str(uid('admin:operator'))}, 'operator', {sql_str(OPERATOR_PASSWORD_HASH)}, true)")
    add("ON CONFLICT (username) DO NOTHING;")
    add("")

    add("INSERT INTO admin_user_roles (admin_user_id, role_id)")
    add("SELECT a.id, r.id FROM admin_users a, roles r WHERE a.username = 'admin' AND r.code = 'platform_admin'")
    add("ON CONFLICT DO NOTHING;")
    add("")
    add("INSERT INTO admin_user_roles (admin_user_id, role_id)")
    add("SELECT a.id, r.id FROM admin_users a, roles r WHERE a.username = 'operator' AND r.code = 'store_operator'")
    add("ON CONFLICT DO NOTHING;")
    add("")

    add("-- 门店运营账号授权门店 store-a -------------------------------------------")
    add("INSERT INTO admin_user_stores (admin_user_id, store_id)")
    add(f"SELECT a.id, s.id FROM admin_users a, stores s WHERE a.username = 'operator' AND s.id = {sql_str(uid('store:store-a'))}")
    add("ON CONFLICT DO NOTHING;")
    add("")

    add("COMMIT;")
    add("")
    return "\n".join(sql)


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"Generated: {OUT}")


if __name__ == "__main__":
    main()
