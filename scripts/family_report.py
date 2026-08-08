"""把命名族候选渲染成一张自包含的 HTML 审阅页，供 find_families.py 调用。

页面本身不联网：样式与脚本全部内联，数据以 JSON 嵌在页里。勾选状态存 localStorage，
关掉再打开还在；「复制已勾选」把选中的共享词拷到剪贴板，直接贴回来即可。
"""

import json

STYLE = """
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; font: 15px/1.6 -apple-system, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
       color: var(--fg); background: var(--bg); }
table { border-collapse: collapse; }
button, input { font: inherit; color: inherit; }

:root {
    --bg: #f7f7f8; --surface: #fff; --fg: #17171a; --muted: #6b6b76;
    --line: #e3e3e8; --accent: #3b5bdb; --accent-soft: #edf0fd;
    --new: #0b7a5a; --new-soft: #e4f5ef; --warn: #a1601b; --warn-soft: #fbf0e2;
    --shadow: 0 1px 2px rgba(0,0,0,.05), 0 8px 24px rgba(0,0,0,.06);
}
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #131316; --surface: #1c1c21; --fg: #e8e8ec; --muted: #9a9aa6;
        --line: #2e2e36; --accent: #8ba2ff; --accent-soft: #23263a;
        --new: #4ecfa6; --new-soft: #16302a; --warn: #e0a761; --warn-soft: #322616;
        --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35);
    }
}

.wrap { max-width: 1180px; margin: 0 auto; padding: 0 24px 96px; }

header { padding: 48px 0 24px; }
h1 { margin: 0 0 8px; font-size: 30px; letter-spacing: -.02em; }
.lede { margin: 0; max-width: 68ch; color: var(--muted); }
.lede code { background: var(--accent-soft); color: var(--accent); padding: 1px 5px; border-radius: 4px; font-size: .9em; }

.stats { display: flex; flex-wrap: wrap; gap: 10px; margin: 24px 0 0; }
.stat { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 10px 16px; }
.stat b { display: block; font-size: 22px; font-variant-numeric: tabular-nums; }
.stat span { font-size: 12px; color: var(--muted); }

.toolbar { position: sticky; top: 0; z-index: 5; margin: 24px 0 20px; padding: 12px 0;
           background: color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter: blur(10px);
           border-bottom: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.toolbar input[type=search] { flex: 1 1 240px; min-width: 180px; padding: 9px 13px; border-radius: 9px;
                              border: 1px solid var(--line); background: var(--surface); }
.toolbar input[type=search]:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
.chip { padding: 8px 13px; border-radius: 9px; border: 1px solid var(--line); background: var(--surface);
        cursor: pointer; white-space: nowrap; }
.chip[aria-pressed=true] { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
.chip.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.count { color: var(--muted); font-size: 13px; margin-left: auto; font-variant-numeric: tabular-nums; }

.fam { background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
       margin-bottom: 10px; box-shadow: var(--shadow); overflow: hidden; }
.fam.picked { border-color: var(--accent); }
.head { display: flex; align-items: center; gap: 12px; padding: 13px 16px; cursor: pointer; }
.head input { width: 17px; height: 17px; accent-color: var(--accent); cursor: pointer; flex: none; }
.key { font: 600 15px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; flex: none; }
.const { color: var(--muted); font-size: 13px; flex: none; }
.const b { color: var(--fg); font-weight: 600; }
.peek { flex: 1 1 auto; min-width: 0; color: var(--muted); font-size: 13px;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.peek b { color: var(--fg); }
.tags { display: flex; gap: 6px; flex: none; }
.tag { font-size: 11px; padding: 3px 8px; border-radius: 999px; background: var(--accent-soft); color: var(--accent);
       font-variant-numeric: tabular-nums; }
.tag.new { background: var(--new-soft); color: var(--new); }
.tag.dup { background: var(--warn-soft); color: var(--warn); }
.tag.done { background: var(--new-soft); color: var(--new); }

.body { display: none; border-top: 1px solid var(--line); overflow-x: auto; }
.fam.open .body { display: block; }
.body table { width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 7px 16px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { position: sticky; top: 0; background: var(--surface); color: var(--muted); font-weight: 500; font-size: 12px; }
tr:last-child td { border-bottom: 0; }
td.short { font-weight: 600; }
td.skip { color: var(--muted); font-style: italic; }
.badge { font-size: 10px; color: var(--new); background: var(--new-soft); padding: 1px 5px; border-radius: 4px;
         margin-left: 5px; vertical-align: 1px; }

.empty { padding: 48px; text-align: center; color: var(--muted); }
footer { margin-top: 40px; padding-top: 24px; border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; }
footer table { width: 100%; margin-top: 12px; font-size: 13px; }
"""

SCRIPT = """
const families = JSON.parse(document.getElementById('data').textContent);
const list = document.getElementById('list');
const STORE = 'term-families-picked';
let picked = new Set(JSON.parse(localStorage.getItem(STORE) || '[]'));
let query = '', filter = 'all';

function save() { localStorage.setItem(STORE, JSON.stringify([...picked])); }

function matches(fam) {
    if (filter === 'picked' && !picked.has(fam.key)) return false;
    if (filter === 'fresh' && fam.dup >= 0.5) return false;
    if (filter === 'todo' && fam.adopted) return false;
    if (!query) return true;
    return fam.haystack.includes(query);
}

function cell(text) { const td = document.createElement('td'); td.textContent = text; return td; }

function buildBody(fam) {
    const table = document.createElement('table');
    const head = table.insertRow();
    for (const label of ['英文全名', '短词', '中文全名', '中文短词']) {
        const th = document.createElement('th');
        th.textContent = label;
        head.appendChild(th);
    }
    for (const [en, part, zh, zhPart, isNew] of fam.rows) {
        const tr = table.insertRow();
        tr.appendChild(cell(en));
        if (zhPart === null) {
            tr.appendChild(cell('—'));
            tr.appendChild(cell(zh));
            const skip = cell('剥不动，跳过');
            skip.className = 'skip';
            tr.appendChild(skip);
            continue;
        }
        const short = cell(part);
        short.className = 'short';
        if (isNew) {
            const badge = document.createElement('span');
            badge.className = 'badge';
            badge.textContent = '新';
            short.appendChild(badge);
        }
        tr.appendChild(short);
        tr.appendChild(cell(zh));
        const zhShort = cell(zhPart);
        zhShort.className = 'short';
        tr.appendChild(zhShort);
    }
    return table;
}

function render() {
    list.textContent = '';
    const shown = families.filter(matches);
    document.getElementById('count').textContent =
        `显示 ${shown.length} / ${families.length} 族 · 已勾选 ${picked.size}`;

    if (!shown.length) {
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = '没有匹配的命名族';
        list.appendChild(empty);
        return;
    }

    for (const fam of shown) {
        const card = document.createElement('article');
        card.className = 'fam' + (picked.has(fam.key) ? ' picked' : '');

        const head = document.createElement('div');
        head.className = 'head';

        const box = document.createElement('input');
        box.type = 'checkbox';
        box.checked = picked.has(fam.key);
        box.addEventListener('click', (e) => e.stopPropagation());
        box.addEventListener('change', () => {
            box.checked ? picked.add(fam.key) : picked.delete(fam.key);
            card.classList.toggle('picked', box.checked);
            save();
            document.getElementById('count').textContent =
                `显示 ${shown.length} / ${families.length} 族 · 已勾选 ${picked.size}`;
        });
        head.appendChild(box);

        const key = document.createElement('span');
        key.className = 'key';
        key.textContent = fam.key;
        head.appendChild(key);

        const konst = document.createElement('span');
        konst.className = 'const';
        konst.append(fam.at === 'suffix' ? '中文后缀 ' : '中文前缀 ');
        const strong = document.createElement('b');
        strong.textContent = fam.consts.join(' / ');
        konst.appendChild(strong);
        head.appendChild(konst);

        const peek = document.createElement('span');
        peek.className = 'peek';
        for (const [i, [en, part, , zhPart]] of fam.rows.filter(r => r[3] !== null).slice(0, 2).entries()) {
            if (i) peek.append('   ');
            peek.append(en + ' → ');
            const b = document.createElement('b');
            b.textContent = `${part} ${zhPart}`;
            peek.appendChild(b);
        }
        head.appendChild(peek);

        const tags = document.createElement('span');
        tags.className = 'tags';
        const addTag = (cls, text) => {
            const t = document.createElement('span');
            t.className = 'tag ' + cls;
            t.textContent = text;
            tags.appendChild(t);
        };
        if (fam.adopted) addTag('done', '已采用');
        addTag('new', `新增 ${fam.fresh}`);
        addTag('', `成员 ${fam.total}`);
        if (fam.dup >= 0.5) addTag('dup', `复用 ${Math.round(fam.dup * 100)}%`);
        head.appendChild(tags);

        head.addEventListener('click', () => {
            if (!card.querySelector('.body')) {
                const body = document.createElement('div');
                body.className = 'body';
                body.appendChild(buildBody(fam));
                card.appendChild(body);
            }
            card.classList.toggle('open');
        });

        card.appendChild(head);
        list.appendChild(card);
    }
}

document.getElementById('search').addEventListener('input', (e) => {
    query = e.target.value.trim().toLowerCase();
    render();
});

for (const chip of document.querySelectorAll('.chip[data-filter]')) {
    chip.addEventListener('click', () => {
        filter = chip.dataset.filter;
        for (const other of document.querySelectorAll('.chip[data-filter]')) {
            other.setAttribute('aria-pressed', String(other === chip));
        }
        render();
    });
}

document.getElementById('copy').addEventListener('click', async (e) => {
    const text = [...picked].join('\\n');
    if (!text) { e.target.textContent = '还没勾选'; }
    else {
        await navigator.clipboard.writeText(text);
        e.target.textContent = `已复制 ${picked.size} 条`;
    }
    setTimeout(() => { e.target.textContent = '复制已勾选'; }, 1600);
});

render();
"""


def _escape(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def render(families, entries_count, conflicts, source_buckets, minimum):
    """families: [{key, consts, at, fresh, total, dup, adopted, rows}]"""
    for fam in families:
        parts = [fam['key']] + fam['consts'] + [cell for row in fam['rows'] for cell in row[:4] if cell]
        fam['haystack'] = ' '.join(parts).lower()

    total_fresh = sum(f['fresh'] for f in families)
    clean = sum(1 for f in families if f['dup'] < 0.5)
    payload = json.dumps(families, ensure_ascii=False, separators=(',', ':'))

    conflict_rows = '\n'.join(
        f'<tr><td>{_escape(a)}</td><td>{_escape(b)}</td><td>{_escape(zh)}</td></tr>' for a, b, zh in conflicts
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>term-map 命名族候选</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>命名族候选</h1>
  <p class="lede">
    共享同一个词的名字凑成一族（<code>X Frame</code>、<code>Whisper of X</code>），
    取组内占多数的中文常量剥出短词。要采用的族把规则写进
    <code>scripts/gen_partials.py</code> 的 <code>RULES</code>，零散的词直接写进
    <code>custom_terms.json</code> 的 <code>partials</code>。
  </p>
  <div class="stats">
    <div class="stat"><b>{len(families)}</b><span>候选族</span></div>
    <div class="stat"><b>{total_fresh}</b><span>可新增短词</span></div>
    <div class="stat"><b>{clean}</b><span>复用率低于 50%</span></div>
    <div class="stat"><b>{entries_count}</b><span>去重英文名</span></div>
    <div class="stat"><b>{len(conflicts)}</b><span>单复数冲突</span></div>
  </div>
</header>

<div class="toolbar">
  <input id="search" type="search" placeholder="搜共享词、英文名或中文…" autocomplete="off">
  <button class="chip" data-filter="all" aria-pressed="true">全部</button>
  <button class="chip" data-filter="fresh" aria-pressed="false">复用率低</button>
  <button class="chip" data-filter="todo" aria-pressed="false">未采用</button>
  <button class="chip" data-filter="picked" aria-pressed="false">已勾选</button>
  <button class="chip primary" id="copy">复制已勾选</button>
  <span class="count" id="count"></span>
</div>

<main id="list"></main>

<footer>
  <p>
    取数 <code>term-map.json</code> 的 {' + '.join(source_buckets)} 桶；门槛：同族至少 {minimum} 个成员、
    且至少 {minimum} 个短词尚未在词库里。「复用率」= 该族剥出的短词有多大比例也被别的族剥出，
    护甲部件族（<code>X Boots</code> / <code>X Helm</code> 剥的都是同一批套装名）复用率高，通常可以跳过。
  </p>
  <p>
    单复数只列译文冲突的；其余变体由油猴脚本 <code>addVariants</code> 运行时生成，真实词条优先，无需逐条判定。
  </p>
  <table>
    <tr><th>A</th><th>B</th><th>译文</th></tr>
    {conflict_rows}
  </table>
</footer>

</div>
<script id="data" type="application/json">{payload}</script>
<script>{SCRIPT}</script>
</body>
</html>
"""
