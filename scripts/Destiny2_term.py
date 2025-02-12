import requests
import json
import os
import time
import hashlib
from datetime import datetime, UTC

# 环境变量和常量
BUNGIE_API_KEY = os.getenv('BUNGIE_API_KEY')
MANIFEST_URL = 'https://www.bungie.net/Platform/Destiny2/Manifest/'
LANG_LIST = ['zh-chs', 'en']
ITEM_CATEGORY_FILTER = [1, 20, 39, 40, 41, 42, 43, 59, 1112488720, 2088636411]
ITEM_CATEGORY_FILTER_DEL = [44, 1742617626]
OUTPUT_FILE_NAME = 'Destiny2_term.json'
METADATA_FILE_NAME = 'metadata.json' # 新增元数据文件名

def get_manifest_version():
    """获取当前Manifest版本"""
    print("获取Manifest版本...")
    response = requests.get(MANIFEST_URL, headers={'X-API-Key': BUNGIE_API_KEY})
    response.raise_for_status()
    return response.json()['Response']['version']

def fetch_manifest_data():
    """Fetch Destiny 2 Manifest data."""
    print("获取Manifest数据...")
    headers = {'X-API-Key': BUNGIE_API_KEY}
    response = requests.get(MANIFEST_URL, headers=headers)
    response.raise_for_status() # 抛出HTTP错误，方便工作流中捕获
    manifest = response.json()
    print("Manifest数据获取成功")
    return manifest

def fetch_item_data(manifest, lang_list, item_filter, item_filter_del):
    """Fetch item definitions from Destiny 2 manifest."""
    item_define_list = {}
    for lang in lang_list:
        item_define_path = manifest['Response']['jsonWorldComponentContentPaths'][lang]['DestinyInventoryItemLiteDefinition']
        print(f"为语言 {lang} 获取物品数据...")
        item_define_resp = requests.get(f'https://www.bungie.net{item_define_path}', headers={'X-API-Key': BUNGIE_API_KEY})
        item_define_resp.raise_for_status()
        item_define = item_define_resp.json()
        item_define_list[lang] = item_define
        print(f"{lang} 物品数据获取成功")
        time.sleep(3) # 保持请求间隔，避免API限制
    return item_define_list

def extract_combined_items(item_define_list, lang_list, item_filter, item_filter_del):
    """Extract items and map names in multiple languages."""
    combined_item_list = {}
    print("提取合并物品数据...")
    for key in item_define_list[lang_list[0]]:
        item = item_define_list[lang_list[0]][key]
        if (item.get('itemCategoryHashes') and
                any(hash in item_filter for hash in item.get('itemCategoryHashes')) and
                not any(hash in item_filter_del for hash in item.get('itemCategoryHashes')) and
                item.get('displayProperties', {}).get('name') and
                item['displayProperties']['name'].strip()):

            en_name = item_define_list['en'][key]['displayProperties']['name']
            zh_name = item_define_list['zh-chs'][key]['displayProperties']['name']
            combined_item_list[en_name] = zh_name
    print("物品数据提取合并完成")
    return combined_item_list

def fetch_activity_data(manifest, lang_list):
    """Fetch activity definitions."""
    activity_define_list = {}
    for lang in lang_list:
        item_define_path = manifest['Response']['jsonWorldComponentContentPaths'][lang]['DestinyActivityDefinition'] #  保持和第一个脚本一致，使用 DestinyActivityDefinition
        print(f"为语言 {lang} 获取活动数据...")
        item_define_resp = requests.get(f'https://www.bungie.net{item_define_path}', headers={'X-API-Key': BUNGIE_API_KEY})
        item_define_resp.raise_for_status()
        activity_define = item_define_resp.json()
        activity_define_list[lang] = activity_define
        print(f"{lang} 活动数据获取成功")
        time.sleep(1) # 保持请求间隔
    return activity_define_list

def extract_combined_activities(activity_define_list, lang_list):
    """提取活动并映射多语言名称。"""
    combined_activity_list = {}
    print("提取合并活动数据...")
    base_lang = lang_list[0]
    for key in activity_define_list[base_lang]:
        en_name = activity_define_list['en'][key]['displayProperties']['name']
        zh_name = activity_define_list['zh-chs'][key]['displayProperties']['name']

        if en_name.strip() and zh_name.strip():
            combined_activity_list[en_name] = zh_name
    print("活动数据提取合并完成")
    return combined_activity_list

def transform_and_sort_data(combined_item_list, combined_activity_list):
    """Transform data, add variations, and sort by English term length, including local data from myself.json."""
    print("转换和排序数据...")

    # 加载本地文件数据
    with open('myself.json', 'r', encoding='utf-8') as file:
        local_data = json.load(file)

    # 合并所有字典
    transformed_data = combined_item_list.copy()
    transformed_data.update(combined_activity_list)
    transformed_data.update(local_data)
    
    # 创建一个新字典来保存增强后的数据
    augmented_data = transformed_data.copy()

    # 添加变体
    for en, zh_chs in transformed_data.items():
        # 添加弯引号版本
        if "'" in en:
            curved_en = en.replace("'", "’")
            augmented_data[curved_en] = zh_chs

        # 添加删除 "The" 前缀的版本
        if en.startswith("The "):
            without_the = en[4:]
            augmented_data[without_the] = zh_chs

    # 按英文术语长度排序
    sorted_data = dict(sorted(augmented_data.items(), key=lambda item: len(item[0].split()), reverse=True))
    print(f"一共梳理了 {len(sorted_data)} 个条目")
    print("数据转换和排序完成")
    return sorted_data

def generate_data_hash(data):
    """生成数据哈希用于检测变更"""
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()

def save_merged_json(metadata, data, output_file):
    """Save merged JSON data to file with metadata."""
    print(f"保存合并后的JSON数据到文件: {output_file}...")
    output = {
        "metadata": metadata,
        "data": data
    }
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(output, file, ensure_ascii=False, indent=2) # 使用 indent=2 更紧凑，类似第二个脚本
    print(f"数据已保存到 {output_file}")

def save_metadata_json(metadata, metadata_file):
    """Save metadata JSON to a separate file."""
    print(f"保存元数据到文件: {metadata_file}...")
    with open(metadata_file, 'w', encoding='utf-8') as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    print(f"元数据已保存到 {metadata_file}")


def main():
    start_time = datetime.now(UTC)

    # 检查API密钥
    if not BUNGIE_API_KEY:
        raise EnvironmentError("请设置环境变量 BUNGIE_API_KEY")

    # 获取当前Manifest版本
    current_version = get_manifest_version()
    print(f"当前 Manifest 版本: {current_version}")

    # 获取Manifest数据
    manifest = fetch_manifest_data()

    # 获取物品数据
    item_define_list = fetch_item_data(manifest, LANG_LIST, ITEM_CATEGORY_FILTER, ITEM_CATEGORY_FILTER_DEL)
    combined_item_list = extract_combined_items(item_define_list, LANG_LIST, ITEM_CATEGORY_FILTER, ITEM_CATEGORY_FILTER_DEL)

    # 获取活动数据
    activity_define_list = fetch_activity_data(manifest, LANG_LIST)
    combined_activity_list = extract_combined_activities(activity_define_list, LANG_LIST)

    # 转换和排序数据
    transformed_data = transform_and_sort_data(combined_item_list, combined_activity_list)

    # 生成数据哈希
    data_hash = generate_data_hash(transformed_data)

    # 生成元数据
    metadata = {
        "version": current_version,
        "timestamp": start_time.isoformat(),
        "item_count": len(transformed_data),
        "data_hash": data_hash,
        "source": "Bungie Destiny 2 Manifest",
        "script_name": os.path.basename(__file__) # 记录脚本名称
    }

    # 保存合并后的JSON数据 (包含元数据)
    save_merged_json(metadata, transformed_data, OUTPUT_FILE_NAME)

    # 保存元数据到单独的文件 (可选，如果需要分离元数据)
    # save_metadata_json(metadata, METADATA_FILE_NAME) #  保存元数据到单独的文件

    end_time = datetime.now(UTC)
    duration = end_time - start_time
    print(f"数据处理完成! 总耗时: {duration}")

if __name__ == "__main__":
    main()