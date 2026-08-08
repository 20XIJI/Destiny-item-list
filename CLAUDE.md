# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A data-generation project, not an app. Python scrapers pull the Destiny 2 Manifest from the Bungie API and emit bilingual (EN / zh-chs) JSON. The JSON is hosted on GitHub Pages and consumed at runtime by two Tampermonkey userscripts that inject Chinese translations onto Destiny fan sites (light.gg etc.). There is no build/bundle step and no server.

`README.md` is stale — it describes an older `item-list.json` / `Destiny2_term.json` layout that the "重构数据集" refactor replaced. Trust the scripts and `.github/workflows/update-all.yml` over the README.

## Commands

```bash
pip install -r scripts/requirements.txt          # only dep is `requests`
node --test tests/tampermonkey-regression.test.js # userscript regression tests (Node built-in runner, no deps)
ruff check --fix scripts/ && ruff format scripts/ # lint/format (pyproject.toml: single quotes, 120 cols)
```

`ruff format` still reflows `build_dataset.py` / `download_all_manifest.py` away from their deliberately terse layout. Format only the files you touched.

Running the pipelines locally needs `BUNGIE_API_KEY` (from bungie.net/en/Application). `download_all_manifest.py` auto-reads it from a root `.env` file; `fetch_manifest.py` does **not** — it only reads the env var, so `export BUNGIE_API_KEY=…` for that one.

```bash
# term-map pipeline (this is what the userscripts actually fetch today)
export BUNGIE_API_KEY=<key>
python scripts/fetch_manifest.py                 # → term-map.json

# rich dataset pipeline — two steps, ORDER MATTERS
python scripts/download_all_manifest.py          # → manifest_raw/en/*  (gitignored); writes _version.txt
MANIFEST_LANG=zh-chs python scripts/download_all_manifest.py  # → manifest_raw/zh-chs/*
python scripts/build_dataset.py                  # reads manifest_raw/ → items-full.json, lore.json, lore-books.json, items-by-type.json
```

`build_dataset.py` reads `manifest_raw/en/_version.txt`, which only exists after `download_all_manifest.py` has run for `en`. Use `MANIFEST_ONLY=Table1,Table2` to download a subset.

## Architecture

Two independent pipelines share `scripts/utils.py` (API-key check, manifest fetch with retry, data hashing) but produce different outputs from different execution models:

**1. term-map pipeline** — `fetch_manifest.py` → `builders/term_map_builder.py` → `term-map.json`
- Downloads 15 definition types × 3 langs (en, zh-chs, zh-cht) **in memory**, never touching disk. `ALL_DEFINITION_TYPES` is derived from `term_map_builder.DEFINITION_BUCKET_MAP`, so adding a table means editing only that map.
- `term_map_builder.build()` keeps only entries present in ≥2 languages, drops blacklisted item categories, routes decorative categories to a separate `cosmetics` bucket, applies `BUCKET_FILTERS` (vendors need a `subtitle` to count as an NPC) and `custom_terms.json`'s `_exclude` hash list, then appends the `custom` and `partials` buckets.
- Output shape: `{metadata, data: {items, cosmetics, …, custom, partials}}`, each entry `{en, zh-chs, zh-cht}` (`zh-cht` optional).
- **This is the only file the userscripts consume** — fetched from `https://20xiji.github.io/Destiny-item-list/term-map.json`.

`custom_terms.json` is the only hand-edited input. Shape: `{"zh-chs": {EN: 简}, "zh-cht": {EN: 繁}, "partials": {"zh-chs": …, "zh-cht": …}, "_exclude": [hash, …]}`. `partials` holds the short forms communities actually write (`Chill` for `Whisper of Chill`, `Adaptive` for `Adaptive Frame`) — regenerate with `python scripts/gen_partials.py`, which strips a fixed family suffix and skips anything that doesn't end in one. `_exclude` suppresses manifest entries by hash; without it a rebuild silently resurrects deletions. `partials._skip` drops generated short forms by EN name — deleting one by hand is pointless because the next `gen_partials.py` run writes it straight back.

The userscript decides two things about these buckets, both in `Destiny2_Term_replace.user.js`: `DEFAULT_DISABLED_BUCKETS` (which start unchecked; bump `DISABLED_BUCKETS_KEY` when changing it or browsers keep the old stored value) and `BUCKET_TIERS`, which resolves the ~41 EN strings that carry different Chinese in different buckets — `custom` outranks everything, the activity family (`activities` / `activity_types` / `activity_modes` / `destinations`) loses to everything.

`python scripts/find_families.py` writes `~/Desktop/term-families.html` — a self-contained review page (rendering lives in `scripts/family_report.py`; no network, checkbox state in `localStorage`) listing every shared-prefix/suffix naming family (`X Frame`, `Whisper of X`, …) with its dominant Chinese constant and the short forms it would yield — use it to decide what else belongs in `gen_partials.py`'s `RULES`. Singular/plural is **not** on that sheet: the userscript's `addVariants` generates both forms at runtime, and `buildTermMapFromData` seeds all real terms before any variant so a genuine entry always wins (`Lucent Blade 光亮之刃` vs `Lucent Blades 光明利刃`).

**2. rich dataset pipeline** — `download_all_manifest.py` (to disk) → `build_dataset.py` (from disk)
- `download_all_manifest.py` dumps raw manifest tables to `manifest_raw/<lang>/*.json` (gitignored, large).
- `build_dataset.py` cross-references EN + zh-chs tables into rich per-entity records (items with slot/damage/lore/icons, activities, npcs, records, lore, seasons, milestones, factions, destinations). zh-chs item names/descs come from the `Lite` table. `clean()` strips empty values; `finalize()` drops entries with no `name`.
- Newer refactor; the userscripts do not read these yet.

**Userscripts** (`tampermonkey/*.user.js`) — plain DOM-manipulation userscripts, not part of any build. `Destiny2_Term_replace` does generic term replacement on any site; `Light.gg Bilingual Display Tool` is a light.gg-specific enhancer. They cache `term-map.json` and walk the DOM to replace/annotate text. Trusted-Types-safe (no `innerHTML` sinks) — the tests assert this.

## Editing gotchas

- **Table-list sync**: `build_dataset.py`'s module docstring lists the manifest tables it needs. `update-all.yml`'s `EN_TABLES` / `ZH_TABLES` env vars must mirror that list. Change one → change both, or CI downloads the wrong tables.
- **Never hand-edit `term-map.json`** — it is regenerated wholesale and any direct edit vanishes on the next run. Put additions in `custom_terms.json` (`zh-chs` / `partials`), deletions in `_exclude`.
- **`patch_term_map.py` mirrors `build()`**: it applies the same bucket layout offline from `manifest_raw/`, for when there is no API key. It reuses `classify_item` / `extract_names` / `BUCKET_FILTERS` / `build_custom_bucket` / `build_partials_bucket`, but owns its own bucket-assembly loop — change the shape of `build()` and change it here too. Delete it once an online rebuild has run.
- **Userscript ↔ test coupling**: `tests/tampermonkey-regression.test.js` extracts named functions (`buildRegex`, `performReplace`, `optimizedTransformReviewItems`, `parseCachedTermMap`, …) out of the userscript source by string-scanning and runs them in a `vm`. Renaming or restructuring those functions breaks the tests even if the userscript still works. The `vm` sandbox only holds `document, NodeFilter, Set, WeakSet, Map, RegExp, langSource, replacementHistory, HISTORY_LIMIT, processedNodes` — referencing any other outer variable from those functions throws `ReferenceError`, so helpers they need must live inside their own bodies.
- **Regex shape is load-bearing for speed**: `buildRegex` emits one alternation over ~20k terms. Wrapping it in a single `\b(…)\b` scans ~5ms per block; switching the literal spaces to `\s+` or moving `\b` onto every alternative makes it 5–20× slower. Whitespace tolerance therefore lives on the text side — `performReplace` collapses runs of whitespace and keeps an offset map back to the original string.
- **Auto-update is paused**: the `schedule:` in `update-all.yml` is commented out (game in long hiatus); the workflow is `workflow_dispatch`-only. Don't assume the hosted JSON is fresh.
- **Style**: Python here is deliberately terse/single-file with Chinese comments and `ponytail:` markers for intentional shortcuts — match it; don't introduce frameworks, dataclasses, or a package structure for these scripts.
