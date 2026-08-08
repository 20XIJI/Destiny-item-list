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
import family_report  # noqa: E402
from gen_partials import RULES, SOURCE_BUCKETS  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
TERM_MAP = REPO / 'term-map.json'


def best_affix(values, at_end):
    """出现次数最多的中文常量；次数持平时取更长的。

    常量至少两个字：`Deep` 一会儿对 `深度炼金` 一会儿对 `深渊探索者臂环`，
    字面公共前缀只有一个 `深`，剥掉会得到 `度炼金` 这种从词中间劈开的结果。
    """
    best, best_hits = '', 0
    for size in range(2, 9):
        pool = [v[-size:] if at_end else v[:size] for v in values if len(v) > size]
        if not pool:
            break
        affix, hits = Counter(pool).most_common(1)[0]
        if hits >= 2 and hits >= best_hits:
            best, best_hits = affix, hits
    return best, best_hits


def dominant_affixes(values, at_end, limit=3):
    """一族可以有多个常量：`Whisper of X` 的简体收尾既有 `之吟` 也有 `的低语`。
    贪心地一轮轮取，每轮只在还没被覆盖的成员里找，直到没有出现两次以上的常量。
    """
    affixes, rest = [], list(values)
    while len(affixes) < limit and rest:
        affix, _ = best_affix(rest, at_end)
        if not affix:
            break
        affixes.append(affix)
        rest = [v for v in rest if not (v.endswith(affix) if at_end else v.startswith(affix))]
    return affixes, len(values) - len(rest)


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

    suffixes, suffix_hits = dominant_affixes(zh_values, True)
    prefixes, prefix_hits = dominant_affixes(zh_values, False)
    zh_consts, zh_at_end = (suffixes, True) if suffix_hits >= prefix_hits else (prefixes, False)
    # 长的排前面，`的低语` 要先于 `低语` 试，否则 `锁链的低语` 会剩个孤零零的 `的`
    zh_consts = sorted(zh_consts, key=len, reverse=True)

    samples, ok, fresh = [], 0, 0
    for en in sorted(members):
        zh = entries[en]
        en_part = en[: -len(shared)].strip() if at_end else en[len(shared) :].strip()
        # 短词以虚词开头说明共享词切少了：`首 Spark` 会剥出 `of Amplitude`，该看 `首 Spark of`
        if re.match(r'(of|the|to|and|for|in|on|a|an)\b', en_part, re.I):
            en_part = ''

        zh_part = None
        for const in zh_consts:
            if not (zh.endswith(const) if zh_at_end else zh.startswith(const)):
                continue
            stripped = (zh[: -len(const)] if zh_at_end else zh[len(const) :]).strip()
            # 常量取到 `低语` 时 `锁链的低语` 会剩个尾巴 `的`，助词一并去掉
            stripped = stripped.rstrip('的之') if zh_at_end else stripped.lstrip('的之')
            # 只剩一个汉字的当词条噪音太大，不如不剥
            if len(stripped) >= 2:
                zh_part = stripped
            break

        if not en_part or zh_part is None:
            zh_part = None
        else:
            ok += 1
            if en_part not in entries:
                fresh += 1  # 短词还不在词库里，补进去才有意义
        samples.append((en, en_part, zh, zh_part))
    return zh_consts, zh_at_end, ok, fresh, samples


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
    parser.add_argument('-o', '--out', default=str(Path.home() / 'Desktop' / 'term-families.html'))
    args = parser.parse_args()

    entries = collect(json.loads(TERM_MAP.read_text(encoding='utf-8')))
    conflicts = build_plural_conflicts(entries)

    candidates = []
    for key, members in build_families(entries, args.min):
        zh_consts, zh_at_end, ok, fresh, samples = analyse(key, members, entries)
        if ok >= args.min and fresh >= args.min:
            candidates.append((key, zh_consts, zh_at_end, fresh, samples))

    # 同一个短词被多少个族剥出来。护甲部件族（Boots/Helm/Gloves…）剥出的都是同一批
    # 套装名，复用度高；碎片、框架这类族剥出的短词只属于自己，复用度为 1。
    reuse = defaultdict(set)
    for key, _, _, _, samples in candidates:
        for _, en_part, _, zh_part in samples:
            if zh_part is not None:
                reuse[en_part].add(key)

    families = []
    for key, zh_consts, zh_at_end, fresh, samples in candidates:
        hit = [s for s in samples if s[3] is not None]
        families.append(
            {
                'key': key,
                'consts': zh_consts,
                'at': 'suffix' if zh_at_end else 'prefix',
                'fresh': fresh,
                'total': len(samples),
                'dup': round(sum(1 for _, p, _, _ in hit if len(reuse[p]) > 1) / len(hit), 3),
                'adopted': covered_by_rules(key),
                'rows': [[en, part, zh, zh_part, part not in entries] for en, part, zh, zh_part in samples],
            }
        )
    families.sort(key=lambda fam: -fam['total'])

    html = family_report.render(families, len(entries), sorted(conflicts), SOURCE_BUCKETS, args.min)
    Path(args.out).write_text(html, encoding='utf-8')
    print(f'候选命名族 {len(families)} 个，单复数冲突 {len(conflicts)} 组')
    print(f'已写入 {args.out}')


if __name__ == '__main__':
    main()
