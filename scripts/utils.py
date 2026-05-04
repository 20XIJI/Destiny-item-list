import json
import hashlib
import requests


def validate_api_key(api_key):
    if not api_key:
        raise EnvironmentError("请设置环境变量 BUNGIE_API_KEY")


def get_manifest(api_key, manifest_url='https://www.bungie.net/Platform/Destiny2/Manifest/'):
    response = requests.get(manifest_url, headers={'X-API-Key': api_key})
    response.raise_for_status()
    return response.json()


def get_manifest_version(api_key, manifest_url='https://www.bungie.net/Platform/Destiny2/Manifest/'):
    manifest = get_manifest(api_key, manifest_url)
    return manifest['Response']['version']


def generate_data_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
