# Destiny-item-list

Destiny 2 双语（英文/中文）术语数据库。从 Bungie API 自动抓取物品和术语数据，生成 JSON 文件通过 GitHub Pages 托管，配合 Tampermonkey 用户脚本在 Destiny 2 粉丝网站（light.gg 等）上实现双语显示。

## 用户脚本

| 脚本 | 用途 | 安装链接 |
|------|------|----------|
| Destiny2_Term_replace | 通用术语替换（适用于任意网站） | [Greasyfork](https://greasyfork.org/scripts/524822) |
| Light.gg Bilingual Display Tool | light.gg 专属双语增强 | [Greasyfork](https://greasyfork.org/scripts/512095) |

## 数据文件

| 文件 | 说明 | 更新频率 |
|------|------|----------|
| `item-list.json` | 完整物品库（按 hash 索引，26,000+ 条目） | 每日自动 |
| `Destiny2_term.json` | 精选术语表（按英文名索引，15,000+ 条目） | 每日自动 |
| `custom_terms.json` | 手工维护的术语映射（320+ 条目） | 手动更新 |

数据通过 GitHub Actions 每日 UTC 17:30（北京时间 01:30）自动更新。

## 本地运行

```bash
pip install -r scripts/requirements.txt
export BUNGIE_API_KEY=<your-key>
python scripts/fetch_items.py       # → item-list.json
python scripts/Destiny2_term.py     # → Destiny2_term.json
```

需要 Bungie API Key（在 [Bungie.net](https://www.bungie.net/en/Application) 申请）。

## 架构

```
Bungie API ──→ scripts/fetch_items.py ──→ item-list.json
            ──→ scripts/Destiny2_term.py ──→ Destiny2_term.json
                                               ↑ merges custom_terms.json

GitHub Pages serves JSON ──→ tampermonkey/*.user.js (fetch at runtime)
```

- `scripts/utils.py` — 共享工具函数（API 校验、Manifest 获取、数据哈希）
- `scripts/fetch_items.py` — 抓取完整物品定义
- `scripts/Destiny2_term.py` — 抓取术语（物品 + 活动 + 技能），合并自定义术语，生成变体
- `custom_terms.json` — 手工维护的 EN→ZH 术语映射

## 许可证

MIT
