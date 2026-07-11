"""生产数据集构建器(双语 EN + zh-chs),从 manifest_raw/{en,zh-chs} 读盘,产出到仓库根:

  items-full.json   —— 组合包:items/activities/npcs/records/seasons/milestones/factions/destinations
  lore.json         —— 扁平全量 lore 条目(含物品 lore)
  lore-books.json   —— 收藏故事书(书 → 有序 lore 记录)
  items-by-type.json—— items 按 typeName 分组(自用查看)

原则1:剔除空值('' / [] / {} / None),丢弃无 name 词条。item 中文 name/desc/typeName 取自 zh-chs Lite 表。

CI 需先下载以下表到 manifest_raw/(改动本文件读表时同步更新 update-all.yml 的表清单):
  en   : InventoryItem, InventoryBucket, ItemCategory, DamageType, ActivityType, ActivityMode,
         Place, Destination, ActivityModifier, Progression, PresentationNode, Faction, Collectible,
         Lore, Objective, Activity, Vendor, Record, Season, Milestone, GlobalConstants
  zh-chs: 同上但 InventoryItem→InventoryItemLite,去掉 GlobalConstants
"""
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
EN = ROOT / 'manifest_raw' / 'en'
ZH = ROOT / 'manifest_raw' / 'zh-chs'
BN = 'https://www.bungie.net'


def url(p):
    return f'{BN}{p}' if p and str(p).startswith('/') else (p or '')


def L(name, lang_dir):
    f = lang_dir / f'{name}.json'
    return json.load(open(f, encoding='utf-8')) if f.exists() else {}


def nmap(defs):
    return {int(h): v.get('displayProperties', {}).get('name', '') for h, v in defs.items()}


def bimap(name):
    return nmap(L(name, EN)), nmap(L(name, ZH))


def gz(zh_defs, h):
    return zh_defs.get(h, {})


def zdp_name(zh_defs, h):
    return gz(zh_defs, h).get('displayProperties', {}).get('name', '')


def zdp_desc(zh_defs, h):
    return gz(zh_defs, h).get('displayProperties', {}).get('description', '')


def clean(v):
    """递归剔除空值('' / [] / {} / None);保留 0 / False。"""
    if isinstance(v, dict):
        out = {}
        for k, val in v.items():
            cv = clean(val)
            if cv != '' and cv != [] and cv != {} and cv is not None:
                out[k] = cv
        return out
    if isinstance(v, list):
        cleaned = [clean(x) for x in v]
        return [x for x in cleaned if x != '' and x != {} and x is not None]
    return v


def finalize(data):
    """剔空 + 丢弃无 name 词条。"""
    out = {}
    for k, v in data.items():
        cv = clean(v)
        if isinstance(cv, dict) and cv.get('name'):
            out[k] = cv
    return out


# ---- 公共维度表(双语) ----
items_en = L('DestinyInventoryItemDefinition', EN)
item_name_en = {int(h): v.get('displayProperties', {}).get('name', '') for h, v in items_en.items()}
lite_zh = L('DestinyInventoryItemLiteDefinition', ZH)
item_name_zh = {int(h): v.get('displayProperties', {}).get('name', '') for h, v in lite_zh.items()}
item_desc_zh = {int(h): v.get('displayProperties', {}).get('description', '') for h, v in lite_zh.items()}
item_type_zh = {int(h): v.get('itemTypeAndTierDisplayName', '') for h, v in lite_zh.items()}

bucket_en, bucket_zh = bimap('DestinyInventoryBucketDefinition')
cat_en, cat_zh = bimap('DestinyItemCategoryDefinition')
dmg_en = {v['enumValue']: v['displayProperties'].get('name', '') for v in L('DestinyDamageTypeDefinition', EN).values()}
dmg_zh = {v['enumValue']: v['displayProperties'].get('name', '') for v in L('DestinyDamageTypeDefinition', ZH).values()}
atype_en, atype_zh = bimap('DestinyActivityTypeDefinition')
amode_en, amode_zh = bimap('DestinyActivityModeDefinition')
place_en, place_zh = bimap('DestinyPlaceDefinition')
amod_en, amod_zh = bimap('DestinyActivityModifierDefinition')
prog_en, prog_zh = bimap('DestinyProgressionDefinition')
prez_en, prez_zh = bimap('DestinyPresentationNodeDefinition')
fac_en, fac_zh = bimap('DestinyFactionDefinition')

col_en, col_zh = L('DestinyCollectibleDefinition', EN), L('DestinyCollectibleDefinition', ZH)
col_src_en = {v['itemHash']: v.get('sourceString', '') for v in col_en.values() if v.get('itemHash')}
col_src_zh = {v['itemHash']: v.get('sourceString', '') for v in col_zh.values() if v.get('itemHash')}
lore_en, lore_zh = L('DestinyLoreDefinition', EN), L('DestinyLoreDefinition', ZH)
obj_en, obj_zh = L('DestinyObjectiveDefinition', EN), L('DestinyObjectiveDefinition', ZH)

AMMO = {0: '', 1: 'Primary', 2: 'Special', 3: 'Heavy'}
TIER_EN = {0: '', 2: 'Basic', 3: 'Common', 4: 'Rare', 5: 'Legendary', 6: 'Exotic'}
TIER_ZH = {0: '', 2: '基本', 3: '常见', 4: '稀有', 5: '传说', 6: '异域'}
CLS = {0: 'Titan', 1: 'Hunter', 2: 'Warlock', 3: 'Any'}


# ---------- items(去掉 stats/perks) ----------
def build_items():
    data = {}
    for h, v in items_en.items():
        name = v.get('displayProperties', {}).get('name', '').strip()
        if not name or v.get('itemType') == 20 or v.get('redacted'):
            continue
        inv = v.get('inventory', {})
        dp = v.get('displayProperties', {})
        hi = int(h)
        tier = inv.get('tierType', 0)
        data[h] = {
            'name': name, 'name_zh': item_name_zh.get(hi, ''),
            'description': dp.get('description', ''), 'description_zh': item_desc_zh.get(hi, ''),
            'flavor': v.get('flavorText', ''),
            'typeName': v.get('itemTypeAndTierDisplayName', ''), 'typeName_zh': item_type_zh.get(hi, ''),
            'tierName': TIER_EN.get(tier, ''), 'tierName_zh': TIER_ZH.get(tier, ''),
            'class': CLS.get(v.get('classType'), ''),
            'slot': bucket_en.get(inv.get('bucketTypeHash'), ''), 'slot_zh': bucket_zh.get(inv.get('bucketTypeHash'), ''),
            'damage': dmg_en.get(v.get('defaultDamageType'), ''), 'damage_zh': dmg_zh.get(v.get('defaultDamageType'), ''),
            'ammo': AMMO.get(v.get('equippingBlock', {}).get('ammoType'), ''),
            'categories': [cat_en.get(x, '') for x in v.get('itemCategoryHashes', []) if cat_en.get(x)],
            'categories_zh': [cat_zh.get(x, '') for x in v.get('itemCategoryHashes', []) if cat_zh.get(x)],
            'source': col_src_en.get(v['hash'], ''), 'source_zh': col_src_zh.get(v['hash'], ''),
            'lore': lore_en.get(str(v.get('loreHash')), {}).get('displayProperties', {}).get('description', ''),
            'lore_zh': lore_zh.get(str(v.get('loreHash')), {}).get('displayProperties', {}).get('description', ''),
            'icon': url(dp.get('icon', '')), 'iconHD': url(dp.get('highResIcon', '')),
            'banner': url(v.get('secondaryIcon', '')),
            'screenshot': url(v.get('screenshot', '')), 'watermark': url(v.get('iconWatermark', '')),
        }
    return data


def build_activities():
    en, zh = L('DestinyActivityDefinition', EN), L('DestinyActivityDefinition', ZH)
    data = {}
    for h, v in en.items():
        if not v.get('displayProperties', {}).get('name') or v.get('redacted'):
            continue
        mm = v.get('matchmaking', {})
        data[h] = {
            'name': v['displayProperties'].get('name', ''), 'name_zh': zdp_name(zh, h),
            'description': v['displayProperties'].get('description', ''), 'description_zh': zdp_desc(zh, h),
            'type': atype_en.get(v.get('activityTypeHash'), ''), 'type_zh': atype_zh.get(v.get('activityTypeHash'), ''),
            'modes': [amode_en.get(x, '') for x in v.get('activityModeHashes', [])],
            'modes_zh': [amode_zh.get(x, '') for x in v.get('activityModeHashes', [])],
            'place': place_en.get(v.get('placeHash'), ''), 'place_zh': place_zh.get(v.get('placeHash'), ''),
            'lightLevel': v.get('activityLightLevel', 0),
            'isPvP': v.get('isPvP', False), 'isPlaylist': v.get('isPlaylist', False),
            'matchmade': mm.get('isMatchmade', False), 'maxPlayers': mm.get('maxPlayers', 0),
            'modifiers': [amod_en.get(m.get('activityModifierHash'), '') for m in v.get('modifiers', []) if amod_en.get(m.get('activityModifierHash'))],
            'modifiers_zh': [amod_zh.get(m.get('activityModifierHash'), '') for m in v.get('modifiers', []) if amod_zh.get(m.get('activityModifierHash'))],
            'image': url(v.get('pgcrImage', '')),
        }
    return data


def build_npcs():
    en, zh = L('DestinyVendorDefinition', EN), L('DestinyVendorDefinition', ZH)
    seen = set()
    data = {}
    for h, v in en.items():
        d = v.get('displayProperties', {})
        name, sub = d.get('name', '').strip(), d.get('subtitle', '').strip()
        if not name or not sub or name in seen:
            continue
        seen.add(name)
        data[h] = {
            'name': name, 'name_zh': zdp_name(zh, h),
            'title': sub, 'title_zh': gz(zh, h).get('displayProperties', {}).get('subtitle', ''),
            'description': d.get('description', ''), 'description_zh': zdp_desc(zh, h),
            'faction': fac_en.get(v.get('factionHash'), ''), 'faction_zh': fac_zh.get(v.get('factionHash'), ''),
            'icon': url(d.get('icon', '')), 'iconHD': url(d.get('highResIcon', '')),
        }
    return data


def build_records():
    en, zh = L('DestinyRecordDefinition', EN), L('DestinyRecordDefinition', ZH)
    data = {}
    for h, v in en.items():
        if not v.get('displayProperties', {}).get('name'):
            continue
        objs = []
        for oh in v.get('objectiveHashes', []):
            o = obj_en.get(str(oh))
            if o:
                objs.append({'desc': o.get('progressDescription', ''),
                             'desc_zh': obj_zh.get(str(oh), {}).get('progressDescription', ''),
                             'target': o.get('completionValue', 0)})
        rewards = v.get('rewardItems', [])
        data[h] = {
            'name': v['displayProperties'].get('name', ''), 'name_zh': zdp_name(zh, h),
            'description': v['displayProperties'].get('description', ''), 'description_zh': zdp_desc(zh, h),
            'objectives': objs,
            'score': v.get('completionInfo', {}).get('ScoreValue', 0),
            'rewards': [item_name_en.get(r.get('itemHash')) for r in rewards if item_name_en.get(r.get('itemHash'))],
            'rewards_zh': [item_name_zh.get(r.get('itemHash')) for r in rewards if item_name_zh.get(r.get('itemHash'))],
            'parents': [prez_en.get(x, '') for x in v.get('parentNodeHashes', []) if prez_en.get(x)],
            'parents_zh': [prez_zh.get(x, '') for x in v.get('parentNodeHashes', []) if prez_zh.get(x)],
            'icon': url(v['displayProperties'].get('icon', '')), 'iconHD': url(v['displayProperties'].get('highResIcon', '')),
        }
    return data


def build_lore():
    data = {}
    for h, v in lore_en.items():
        if not v.get('displayProperties', {}).get('name'):
            continue
        d = v.get('displayProperties', {})
        z = gz(lore_zh, h)
        data[h] = {
            'name': d.get('name', ''), 'name_zh': z.get('displayProperties', {}).get('name', ''),
            'subtitle': v.get('subtitle', ''), 'subtitle_zh': z.get('subtitle', ''),
            'text': d.get('description', ''), 'text_zh': z.get('displayProperties', {}).get('description', ''),
        }
    return data


def build_lore_books():
    gc = L('DestinyGlobalConstantsDefinition', EN)
    root = next(iter(gc.values())).get('loreRootNodeHash')
    pen, pzh = L('DestinyPresentationNodeDefinition', EN), L('DestinyPresentationNodeDefinition', ZH)
    ren, rzh = L('DestinyRecordDefinition', EN), L('DestinyRecordDefinition', ZH)
    books = {}

    def walk(h, path):
        n = pen.get(str(h))
        if not n:
            return
        nm = n['displayProperties'].get('name', '')
        recs = n.get('children', {}).get('records', [])
        subs = n.get('children', {}).get('presentationNodes', [])
        if recs:
            entries = []
            for r in recs:
                rh = str(r['recordHash'])
                rd = ren.get(rh)
                if not rd:
                    continue
                lh = str(rd.get('loreHash'))
                entries.append({
                    'name': rd['displayProperties'].get('name', ''),
                    'name_zh': rzh.get(rh, {}).get('displayProperties', {}).get('name', ''),
                    'text': lore_en.get(lh, {}).get('displayProperties', {}).get('description', ''),
                    'text_zh': lore_zh.get(lh, {}).get('displayProperties', {}).get('description', ''),
                })
            books[str(h)] = {
                'name': nm, 'name_zh': pzh.get(str(h), {}).get('displayProperties', {}).get('name', ''),
                'path': path, 'entryCount': len(entries), 'entries': entries,
            }
        for s in subs:
            walk(s['presentationNodeHash'], f'{path} / {nm}'.strip(' /'))

    walk(root, '')
    return books


def build_seasons():
    en, zh = L('DestinySeasonDefinition', EN), L('DestinySeasonDefinition', ZH)
    data = {}
    for h, v in en.items():
        d = v.get('displayProperties', {})
        ah = v.get('artifactItemHash')
        data[h] = {
            'name': d.get('name', ''), 'name_zh': zdp_name(zh, h),
            'seasonNumber': v.get('seasonNumber'),
            'startDate': v.get('startDate', ''), 'endDate': v.get('endDate', ''),
            'artifact': item_name_en.get(ah, ''), 'artifact_zh': item_name_zh.get(ah, ''),
            'background': url(v.get('backgroundImagePath', '')), 'icon': url(d.get('icon', '')),
        }
    return data


def build_milestones():
    en, zh = L('DestinyMilestoneDefinition', EN), L('DestinyMilestoneDefinition', ZH)
    act_en, act_zh = bimap('DestinyActivityDefinition')
    data = {}
    for h, v in en.items():
        d = v.get('displayProperties', {})
        acts = v.get('activities', [])[:10]
        data[h] = {
            'name': d.get('name', ''), 'name_zh': zdp_name(zh, h),
            'description': d.get('description', ''), 'description_zh': zdp_desc(zh, h),
            'type': v.get('milestoneType'),
            'activities': [act_en.get(a.get('activityHash'), '') for a in acts],
            'activities_zh': [act_zh.get(a.get('activityHash'), '') for a in acts],
            'image': url(v.get('image', '')), 'icon': url(d.get('icon', '')), 'iconHD': url(d.get('highResIcon', '')),
        }
    return data


def build_factions():
    en, zh = L('DestinyFactionDefinition', EN), L('DestinyFactionDefinition', ZH)
    data = {}
    for h, v in en.items():
        d = v.get('displayProperties', {})
        rh = v.get('rewardItemHash')
        data[h] = {
            'name': d.get('name', ''), 'name_zh': zdp_name(zh, h),
            'description': d.get('description', ''), 'description_zh': zdp_desc(zh, h),
            'progression': prog_en.get(v.get('progressionHash'), ''), 'progression_zh': prog_zh.get(v.get('progressionHash'), ''),
            'rewardItem': item_name_en.get(rh, ''), 'rewardItem_zh': item_name_zh.get(rh, ''),
            'icon': url(d.get('icon', '')), 'iconHD': url(d.get('highResIcon', '')),
        }
    return data


def build_destinations():
    en, zh = L('DestinyDestinationDefinition', EN), L('DestinyDestinationDefinition', ZH)
    data = {}
    for h, v in en.items():
        d = v.get('displayProperties', {})
        zb = gz(zh, h).get('bubbles', [])
        zb_name = {b.get('hash'): b.get('displayProperties', {}).get('name', '') for b in zb}
        data[h] = {
            'name': d.get('name', ''), 'name_zh': zdp_name(zh, h),
            'description': d.get('description', ''), 'description_zh': zdp_desc(zh, h),
            'place': place_en.get(v.get('placeHash'), ''), 'place_zh': place_zh.get(v.get('placeHash'), ''),
            'bubbles': [b.get('displayProperties', {}).get('name', '') for b in v.get('bubbles', []) if b.get('displayProperties', {}).get('name')][:20],
            'bubbles_zh': [zb_name.get(b.get('hash'), '') for b in v.get('bubbles', [])][:20],
        }
    return data


def save(name, doc):
    (ROOT / name).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'已写 {name}')


def main():
    version = (EN / '_version.txt').read_text().strip()
    stamp = datetime.now(timezone.utc).isoformat()

    # 组合包 = items-full.json(不含 lore)
    cats = {
        'items': finalize(build_items()),
        'activities': finalize(build_activities()),
        'npcs': finalize(build_npcs()),
        'records': finalize(build_records()),
        'seasons': finalize(build_seasons()),
        'milestones': finalize(build_milestones()),
        'factions': finalize(build_factions()),
        'destinations': finalize(build_destinations()),
    }
    counts = {k: len(v) for k, v in cats.items()}
    save('items-full.json', {'metadata': {'version': version, 'timestamp': stamp,
                                          'languages': ['en', 'zh-chs'], 'counts': counts}, **cats})

    # lore 两个单独保留
    save('lore.json', {'metadata': {'version': version, 'timestamp': stamp},
                       'data': finalize(build_lore())})
    save('lore-books.json', {'metadata': {'version': version, 'timestamp': stamp},
                             'data': finalize(build_lore_books())})

    # items 按 typeName 分组(自用)
    by_type = {}
    for h, it in cats['items'].items():
        by_type.setdefault(it.get('typeName') or '(none)', {})[h] = it
    save('items-by-type.json', {'metadata': {'version': version, 'timestamp': stamp,
                                            'typeCount': len(by_type)}, 'data': by_type})

    print('\n统计:', counts)


if __name__ == '__main__':
    main()
