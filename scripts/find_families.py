"""扫描 term-map.json 里"共前缀/共后缀"的命名族与单复数对，输出待人工判定的候选清单。

    python scripts/find_families.py [--min 3] [-o 路径]

命名族：`Adaptive Frame` / `Rapid-Fire Frame` 这类共享同一个词的名字。取组内占多数的
中文常量，逐条剥离后给出样例；剥不动的成员单独标出，不影响整族。「新增短词」只数
词库里还没有的短词——`Solstice Boots` 剥出的 `Solstice` 早就在库里，补它没有意义。

单复数只列译文冲突的（两种形式都在库里且译文不同）。其余单复数变体由油猴脚本
`addVariants` 在运行时生成，不需要逐条判定。

判定完把要采用的族加进 gen_partials.py 的 RULES，或把个别词写进 custom_terms.json。
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_partials import RULES, SOURCE_BUCKETS  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
TERM_MAP = REPO / 'term-map.json'


def dominant_affix(values, at_end, min_ratio=0.6):
    """占多数的中文常量。不用严格公共前后缀：一个异常成员就会把整族的常量吃光
    （`Unidentified Radiant Frame` 中文收尾是"模型"，能让 Frame 族的"框架"消失）。
    """
    best, best_hits = '', 0
    for size in range(2, 9):
        pool = [v[-size:] if at_end else v[:size] for v in values if len(v) > size]
        if not pool:
            break
        affix, hits = Counter(pool).most_common(1)[0]
        if hits >= 2 and hits / len(values) >= min_ratio:
            best, best_hits = affix, hits
    return best, best_hits


def collect(term_map):
    """按 EN 去重铺平武器/特性桶，与 gen_partials 同一取数口径"""
    seen = {}
    for name in SOURCE_BUCKETS:
        for entry in term_map['data'].get(name, {}).values():
            en, zh = entry.get('en'), entry.get('zh-chs')
            if en and zh and en not in seen:
                seen[en] = zh
    return seen


def build_families(entries, minimum):
    """(位置, 共享词) → 成员列表；同一批成员只保留最长的那个键"""
    raw = defaultdict(list)
    for en in entries:
        words = en.split()
        if len(words) < 2:
            continue
        for key in ('尾 ' + words[-1], '首 ' + words[0]):
            raw[key].append(en)
        if len(words) >= 3:
            raw['尾 ' + ' '.join(words[-2:])].append(en)
            raw['首 ' + ' '.join(words[:2])].append(en)
    raw = {k: v for k, v in raw.items() if re.search(r'[A-Za-z]', k[2:])}

    best = {}
    for key, members in raw.items():
        if len(members) < minimum:
            continue
        fingerprint = frozenset(members)
        if fingerprint not in best or len(key) > len(best[fingerprint][0]):
            best[fingerprint] = (key, members)
    return sorted(best.values(), key=lambda kv: -len(kv[1]))


def analyse(key, members, entries):
    """算出中文常量与逐条剥离结果；剥不动的成员 zh_part 为 None"""
    at_end = key.startswith('尾 ')
    shared = key[2:]
    zh_values = [entries[en] for en in members]

    suffix, suffix_hits = dominant_affix(zh_values, True)
    prefix, prefix_hits = dominant_affix(zh_values, False)
    zh_const, zh_at_end = (suffix, True) if suffix_hits >= prefix_hits else (prefix, False)

    samples, ok, fresh = [], 0, 0
    for en in sorted(members):
        zh = entries[en]
        en_part = en[: -len(shared)].strip() if at_end else en[len(shared) :].strip()
        matched = zh_const and (zh.endswith(zh_const) if zh_at_end else zh.startswith(zh_const))
        zh_part = (zh[: -len(zh_const)] if zh_at_end else zh[len(zh_const) :]).strip() if matched else ''
        # 中文剩余不足两个字，多半是把词从中间切开了（`深` 会把"深度炼金"切成"度炼金"）
        if not en_part or len(zh_part) < 2:
            zh_part = None
        else:
            ok += 1
            if en_part not in entries:
                fresh += 1  # 短词还不在词库里，补进去才有意义
        samples.append((en, en_part, zh, zh_part))
    return zh_const, zh_at_end, ok, fresh, samples


def plural_of(word):
    if re.search(r'(s|x|z|ch|sh)$', word):
        return word + 'es'
    if re.search(r'[^aeiou]y$', word):
        return word[:-1] + 'ies'
    return word + 's'


def singular_of(word):
    for pattern, repl in ((r'ies$', 'y'), (r'(s|x|z|ch|sh)es$', r'\1'), (r'([^s])s$', r'\1')):
        if re.search(pattern, word):
            return re.sub(pattern, repl, word)
    return None


def swap_last_word(name, transform):
    words = name.split()
    other = transform(words[-1])
    if not other or other == words[-1]:
        return None
    return ' '.join(words[:-1] + [other])


def build_plural_conflicts(entries):
    """两种形式都在库里但译文不同——脚本侧自动生成变体时必须让真实条目优先"""
    conflicts, seen = [], set()
    for en, zh in entries.items():
        for transform in (plural_of, singular_of):
            other = swap_last_word(en, transform)
            if not other or other not in entries or entries[other] == zh:
                continue
            pair = tuple(sorted((en, other)))
            if pair not in seen:
                seen.add(pair)
                conflicts.append((en, other, f'{zh} / {entries[other]}'))
    return conflicts


def covered_by_rules(key):
    shared = key[2:]
    for pattern, _, _ in RULES:
        probe = pattern.replace('^', '').replace('$', '').replace('(.+)', 'X')
        if shared in probe:
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--min', type=int, default=3, help='命名族最少成员数（默认 3）')
    parser.add_argument('-o', '--out', default=str(Path.home() / 'Desktop' / 'term-families.md'))
    args = parser.parse_args()

    entries = collect(json.loads(TERM_MAP.read_text(encoding='utf-8')))
    conflicts = build_plural_conflicts(entries)

    candidates = []
    for key, members in build_families(entries, args.min):
        zh_const, zh_at_end, ok, fresh, samples = analyse(key, members, entries)
        if ok >= args.min and fresh >= args.min:
            candidates.append((key, zh_const, zh_at_end, fresh, samples))

    # 同一个短词被多少个族剥出来。护甲部件族（Boots/Helm/Gloves…）剥出的都是同一批
    # 套装名，复用度高；碎片、框架这类族剥出的短词只属于自己，复用度为 1。
    reuse = defaultdict(set)
    for key, _, _, _, samples in candidates:
        for _, en_part, _, zh_part in samples:
            if zh_part is not None:
                reuse[en_part].add(key)

    scored = []
    for key, zh_const, zh_at_end, fresh, samples in candidates:
        hit = [s for s in samples if s[3] is not None]
        dup = sum(1 for _, p, _, _ in hit if len(reuse[p]) > 1) / len(hit)
        scored.append((fresh, key, zh_const, zh_at_end, samples, dup))
    scored.sort(key=lambda row: -len(row[4]))

    lines = [
        '# term-map 命名族候选',
        '',
        f'取数：`term-map.json` 的 {" + ".join(SOURCE_BUCKETS)} 桶，{len(entries)} 个去重英文名。',
        f'门槛：同族至少 {args.min} 个成员，且至少 {args.min} 个短词尚未在词库里。',
        '',
        '判定方式：要采用的族把规则加进 `scripts/gen_partials.py` 的 `RULES`，'
        '零散的词直接写进 `custom_terms.json` 的 `partials`。',
        '',
        '## 一、总览',
        '',
        '按成员数排。「复用率」= 该族剥出的短词有多大比例也被别的族剥出——'
        '护甲部件族（`X Boots` / `X Helm` 剥的都是同一批套装名）复用率高，通常可以跳过。',
        '',
        '| 采用 | 共享词 | 复用率 | 新增短词 | 成员 | 中文常量 | 样例 |',
        '|---|---|---|---|---|---|---|',
    ]
    for fresh, key, zh_const, zh_at_end, samples, dup in scored:
        mark = '✅' if covered_by_rules(key) else '[ ]'
        where = '后' if zh_at_end else '前'
        hit = [s for s in samples if s[3] is not None]
        sample = '；'.join(f'{en}→**{ep}** {zp}' for en, ep, _, zp in hit[:2])
        lines.append(f'| {mark} | `{key}` | {dup:.0%} | {fresh} | {len(samples)} | {where}`{zh_const}` | {sample} |')

    lines += ['', '## 二、逐族明细', '']
    for fresh, key, zh_const, zh_at_end, samples, _ in scored:
        mark = ' ✅已采用' if covered_by_rules(key) else ''
        where = '后缀' if zh_at_end else '前缀'
        lines.append(f'### `{key}` — {len(samples)} 个成员 / 新增 {fresh} 个短词，中文{where} `{zh_const}`{mark}')
        lines += ['', '| 英文全名 | 短词 | 中文全名 | 中文短词 |', '|---|---|---|---|']
        for en, en_part, zh, zh_part in samples[:12]:
            if zh_part is None:
                lines.append(f'| {en} | — | {zh} | 剥不动，跳过 |')
                continue
            flag = '' if en_part in entries else ' 🆕'
            lines.append(f'| {en} | **{en_part}**{flag} | {zh} | **{zh_part}** |')
        if len(samples) > 12:
            lines.append(f'| …另 {len(samples) - 12} 个 | | | |')
        lines.append('')

    lines += [
        '## 三、单复数冲突（两种形式都在库里且译文不同）',
        '',
        '其余单复数变体由油猴脚本 `addVariants` 运行时生成，真实条目优先，无需逐条判定。',
        '',
        '| A | B | 译文 |',
        '|---|---|---|',
    ]
    for a, b, zh in sorted(conflicts):
        lines.append(f'| {a} | {b} | {zh} |')
    lines.append('')

    Path(args.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'候选命名族 {len(scored)} 个，单复数冲突 {len(conflicts)} 组')
    print(f'已写入 {args.out}')


if __name__ == '__main__':
    main()
