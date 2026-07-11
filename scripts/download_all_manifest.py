"""下载 manifest 全部定义表到 manifest_raw/<lang>/（已 gitignore）。

用法: python scripts/download_all_manifest.py
语言默认 en，改 MANIFEST_LANG 环境变量可切 zh-chs / zh-cht。
"""
import os
import sys
import time
import pathlib

import requests
from utils import validate_api_key, get_manifest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 自己读 .env，不引依赖 (ponytail: 单行 KEY=VALUE 够用，复杂了再上 python-dotenv)
env = ROOT / '.env'
if env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

KEY = os.getenv('BUNGIE_API_KEY')
LANG = os.getenv('MANIFEST_LANG', 'en')
ONLY = {t.strip() for t in os.getenv('MANIFEST_ONLY', '').split(',') if t.strip()}  # 空=全下
DELAY = 0.3

validate_api_key(KEY)

out = ROOT / 'manifest_raw' / LANG
out.mkdir(parents=True, exist_ok=True)

manifest = get_manifest(KEY)
version = manifest['Response']['version']
paths = manifest['Response']['jsonWorldComponentContentPaths'].get(LANG)
if not paths:
    sys.exit(f'manifest 无 {LANG} 语言')
if ONLY:
    paths = {k: v for k, v in paths.items() if k in ONLY}

print(f'版本 {version} — {len(paths)} 张表 → {out}')
(out / '_version.txt').write_text(version)

session = requests.Session()
for i, (name, path) in enumerate(sorted(paths.items()), 1):
    r = session.get(f'https://www.bungie.net{path}',
                    headers={'X-API-Key': KEY}, timeout=120)
    r.raise_for_status()
    (out / f'{name}.json').write_bytes(r.content)
    print(f'[{i}/{len(paths)}] {name}  {len(r.content) // 1024} KB', flush=True)
    time.sleep(DELAY)

print('完成')
