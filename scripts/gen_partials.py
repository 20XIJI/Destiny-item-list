"""生成"短词/碎片"词条写入 custom_terms.json 的 partials 区。

社区表格常只写复合名的特征部分（`Whisper of Chill` 写成 `Chill`、`Adaptive Frame` 写成 `Adaptive`），
manifest 里只有全名。本脚本按族名后缀做定长剥离，从 term-map.json 反推这些短词。

    python scripts/gen_partials.py [--dry-run]

剥离失败即跳过，不做任何比例截断式的猜测；已有条目按 EN key 覆盖，手工添加的其他条目原样保留。
"""

import json
import re
import sys
from pathlib import Path

from builders import term_map_builder
from utils import generate_data_hash

REPO = Path(__file__).resolve().parents[1]
TERM_MAP = REPO / 'term-map.json'
CUSTOM_TERMS = REPO / 'custom_terms.json'

SOURCE_BUCKETS = ('items', 'perks')

# (EN 模式, 简体族名后缀候选, 繁体族名后缀候选)
# 后缀按顺序试，命中即剥离；繁体一列不统一（框架 = 外觀/模型/機甲/框架/模組）故列多个
RULES = [
    (r'^(.+) Frame$', ['框架'], ['外觀', '模型', '機甲', '框架', '模組']),
    (r'^Echo of (.+)$', ['回声'], ['回聲']),
    (r'^Ember of (.+)$', ['余烬'], ['餘燼']),
    (r'^Spark of (.+)$', ['火花'], ['花火']),
    (r'^Facet of (.+)$', ['琢面'], ['面向']),
    (r'^Thread of (.+)$', ['丝线'], ['之線']),
    (r'^Whisper of (.+)$', ['之吟', '的低语', '低语'], ['的低語', '低語']),
]


def strip_suffix(text, suffixes):
    """去掉族名后缀；没命中或剥空则返回 None"""
    if not text:
        return None
    for suffix in suffixes:
        if text.endswith(suffix):
            stripped = text[: -len(suffix)].strip()
            if stripped:
                return stripped
    return None


def collect_entries(term_map):
    """按 EN 去重地铺平武器/特性桶；同名条目以先出现的为准。

    只扫这两个桶：碎片与武器框架都在这里，而 categories 桶有 `Weapon Mods: Frame`
    这类同形异义的分类名，会污染剥离结果。
    """
    seen = {}
    for name in SOURCE_BUCKETS:
        for entry in term_map['data'].get(name, {}).values():
            en = entry.get('en')
            if en and en not in seen:
                seen[en] = entry
    return seen


def generate(term_map):
    chs, cht, skipped = {}, {}, []

    for en, entry in collect_entries(term_map).items():
        for pattern, chs_suffixes, cht_suffixes in RULES:
            match = re.match(pattern, en)
            if not match:
                continue

            part = match.group(1).strip()
            # `Whisper of the Worm` / `Echo of the Great Disaster` 是武器护甲，不是碎片
            if not part or part.lower().startswith('the '):
                break

            part_chs = strip_suffix(entry.get('zh-chs'), chs_suffixes)
            if not part_chs:
                skipped.append((en, entry.get('zh-chs')))
                break

            chs[part] = part_chs
            part_cht = strip_suffix(entry.get('zh-cht'), cht_suffixes)
            if part_cht:
                cht[part] = part_cht
            break

    return chs, cht, skipped


def main():
    dry_run = '--dry-run' in sys.argv

    term_map = json.loads(TERM_MAP.read_text(encoding='utf-8'))
    custom = json.loads(CUSTOM_TERMS.read_text(encoding='utf-8'))

    chs, cht, skipped = generate(term_map)

    partials = custom.setdefault('partials', {})
    old_chs = partials.setdefault('zh-chs', {})
    old_cht = partials.setdefault('zh-cht', {})

    added = [k for k in chs if k not in old_chs]
    changed = [k for k in chs if k in old_chs and old_chs[k] != chs[k]]

    for en, zh in sorted(chs.items()):
        old_chs[en] = zh
    for en, zh in sorted(cht.items()):
        old_cht[en] = zh

    print(f'生成 {len(chs)} 条（新增 {len(added)}，覆盖 {len(changed)}），繁体 {len(cht)} 条')
    for en in changed:
        print(f'  覆盖 {en}: {chs[en]}')
    for en, zh in skipped:
        print(f'  跳过 {en}: 中文 "{zh}" 不以族名后缀结尾')

    if dry_run:
        print('\n--dry-run，未写入')
        return

    CUSTOM_TERMS.write_text(json.dumps(custom, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'\n已写入 {CUSTOM_TERMS.name}: partials 共 {len(old_chs)} 条')
    apply_to_term_map(term_map, custom)


def apply_to_term_map(term_map, custom):
    """把新的 custom / partials 刷回 term-map.json。

    这两个桶只依赖 custom_terms.json，重刷一遍就够，不必为了几条短词再全量下载一次 manifest。
    """
    data = term_map['data']
    data['custom'] = term_map_builder.build_custom_bucket(custom)
    data['partials'] = term_map_builder.build_partials_bucket(custom)
    for hash_key in custom.get('_exclude') or ():
        for bucket in data.values():
            bucket.pop(hash_key, None)

    term_map['metadata']['data_hash'] = generate_data_hash(data)
    TERM_MAP.write_text(json.dumps(term_map, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'已刷新 {TERM_MAP.name}: custom {len(data["custom"])} 条，partials {len(data["partials"])} 条')


if __name__ == '__main__':
    main()
