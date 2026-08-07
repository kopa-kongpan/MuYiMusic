# 演示数据种子 (Seed)

本目录提供一套**可跨环境初始化**的演示数据,用于本地开发、测试与演示环境,
覆盖小程序端与管理后台的完整业务闭环。

## 文件

| 文件 | 说明 |
|---|---|
| `seed_demo_data.sql` | 可直接执行的种子 SQL(提交入库,跨环境复用) |
| `generate_seed_sql.py` | 种子 SQL 生成器(改数据时编辑此文件后重新生成) |

生成器保证确定性:所有主键由 `uuid5(命名空间, 业务名)` 推导,
同一份代码在任何机器上生成完全相同的 SQL;所有 `INSERT` 均带
`ON CONFLICT DO NOTHING`,**重复执行安全(幂等)**,不会污染已有数据。

## 在本地环境执行

```powershell
# 从仓库根目录执行(需本地部署已启动)
$env:PGPASSWORD = (Select-String -Path .env -Pattern '^POSTGRES_PASSWORD=').Line.Split('=')[1]
Get-Content deploy/seed/seed_demo_data.sql | docker exec -i muyimusic-postgres-1 psql -U admin -d muyimusic -v ON_ERROR_STOP=1
```

或在任意 PostgreSQL 环境执行:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f deploy/seed/seed_demo_data.sql
```

## 数据内容

- **2 家门店**(上海徐汇 / 北京朝阳)+ 每店 4 个首页内容块(banner + 快捷入口)
- **6 个课程商品** × 2-3 个 SKU(体验课 / 次卡),含分类与商品图
- **4 名教师 + 24 节排课**:排课时间用相对日期表达式 `(CURRENT_DATE + N)`,
  任何环境执行都会落在未来 2-4 天,便于直接演示预约流程
- **3 个 H5 测试用户**,各带订单、课程权益;其中 1 条已预约课程
  (8/10 10:00 钢琴一对一,权益 8/10 节、已预约 1 节)
- **运营账号体系**:9 项权限、2 个角色(平台管理员 / 门店运营)、
  2 个账号;`operator` 已授权门店「木易音乐·徐汇旗舰店」

## 演示账号

| 端 | 账号 | 密码 / code |
|---|---|---|
| 管理后台 | `admin` | `MuYiMusic@2026local`(平台管理员) |
| 管理后台 | `operator` | `Operator@2026local`(门店运营,仅限徐汇店) |
| 小程序 H5 | code `seed-local-user-0001-abcdefghijklmnop` | 林晓(13800138000) |
| 小程序 H5 | code `seed-local-user-0002-abcdefghijklmnop` | 周雨桐(13900139000) |
| 小程序 H5 | code `seed-local-user-0003-abcdefghijklmnop` | 吴一凡(13700137000) |

H5 登录接口: `POST /api/v1/app/auth/login`
```json
{"provider": "h5", "code": "seed-local-user-0001-abcdefghijklmnop", "nickname": "林晓"}
```
(仅 `APP_ENV=local` 时可用;H5 用户的 `provider_subject` 为
`local_` + `sha256(code)` 的十六进制)

## 注意

- **媒体文件为占位 key**(如 `seed/banner-piano.png`),需在对象存储或
  静态目录放置同名文件,或替换为真实 key 后重新生成
- 排课时间相对执行当天生成,数据始终是"未来 3 天";如需更多可约日期,
  编辑 `generate_seed_sql.py` 的 `SCHEDULE_PLAN` 后重新生成
- `admin` 账号由启动引导脚本 `bootstrap_admin.py` 创建,种子只会补
  `operator`;若环境没有 `admin`,执行种子后也会创建
- 修改文案/价格/排期:改 `generate_seed_sql.py` → `python deploy/seed/generate_seed_sql.py`
  → 重新执行 SQL(幂等,旧数据不动)
