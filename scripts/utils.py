import json
import hashlib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


MANIFEST_URL = 'https://www.bungie.net/Platform/Destiny2/Manifest/'
REQUEST_TIMEOUT = 30


def validate_api_key(api_key):
    if not api_key:
        raise EnvironmentError("请设置环境变量 BUNGIE_API_KEY")


def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    return session


def get_manifest(api_key, manifest_url=MANIFEST_URL):
    session = create_session()
    response = session.get(manifest_url, headers={'X-API-Key': api_key}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def generate_data_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
