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
OUTPUT_FILE_NAME = 'MISC/Destiny2_term_test.json'
METADATA_FILE_NAME = 'metadata_test.json'

def get_manifest_version():
    """获取当前Manifest版本"""
    print("获取Manifest版本...")
    response = requests.get(MANIFEST_URL, headers={'X-API-Key': BUNGIE_API_KEY})
    response.raise_for_status()
    return response.json()['Response']['version']

def fetch_manifest_data():
    """获取Destiny 2 Manifest数据"""
    print("获取Manifest数据...")
    headers = {'X-API-Key': BUNGIE_API_KEY}
    response = requests.get(MANIFEST_URL, headers=headers)
    response.raise_for_status()
    manifest = response.json()
    print("Manifest数据获取成功")
    return manifest

def fetch_and_extract_data(manifest, definition_types, lang_list, item_filter=None, item_filter_del=None):
    """
    获取并提取Destiny 2清单中的定义数据。
    
    参数:
        manifest: Manifest数据
        definition_types: 要获取的定义类型列表
        lang_list: 语言代码列表
        item_filter: 要包含的类别哈希列表（适用于物品）
        item_filter_del: 要排除的类别哈希列表（适用于物品）
        
    返回:
        英文术语到中文术语的映射字典列表
    """
    all_data = []
    
    for definition_type in definition_types:
        print(f"处理 {definition_type}...")
        
        # 获取所有语言的定义数据
        definitions_by_lang = {}
        for lang in lang_list:
            if definition_type not in manifest['Response']['jsonWorldComponentContentPaths'][lang]:
                print(f"警告: 语言 {lang} 中未找到 {definition_type}")
                continue
                
            path = manifest['Response']['jsonWorldComponentContentPaths'][lang][definition_type]
            url = f'https://www.bungie.net{path}'
            
            print(f"为语言 {lang} 获取 {definition_type} 数据...")
            response = requests.get(url, headers={'X-API-Key': BUNGIE_API_KEY})
            response.raise_for_status()
            data = response.json()
            definitions_by_lang[lang] = data
            print(f"{lang} {definition_type} 数据获取成功")
            
            # 添加延迟以避免API限制
            time.sleep(1)
        
        # 提取数据
        combined_data = {}
        if definition_type == "DestinyInventoryItemLiteDefinition" and item_filter:
            # 使用类别过滤器处理物品
            for key in definitions_by_lang[lang_list[0]]:
                item = definitions_by_lang[lang_list[0]][key]
                
                # 应用物品过滤器
                if (item.get('itemCategoryHashes') and
                        any(hash in item_filter for hash in item.get('itemCategoryHashes')) and
                        not any(hash in item_filter_del for hash in item.get('itemCategoryHashes', [])) and
                        item.get('displayProperties', {}).get('name') and
                        item['displayProperties']['name'].strip()):
                    
                    en_name = definitions_by_lang['en'][key]['displayProperties']['name']
                    zh_name = definitions_by_lang['zh-chs'][key]['displayProperties']['name']
                    
                    if en_name.strip() and zh_name.strip():
                        combined_data[en_name] = zh_name
        else:
            # 处理其他定义类型（如活动）
            for key in definitions_by_lang[lang_list[0]]:
                if (key in definitions_by_lang['en'] and key in definitions_by_lang['zh-chs'] and
                        definitions_by_lang['en'][key].get('displayProperties', {}).get('name') and
                        definitions_by_lang['zh-chs'][key].get('displayProperties', {}).get('name')):
                    
                    en_name = definitions_by_lang['en'][key]['displayProperties']['name']
                    zh_name = definitions_by_lang['zh-chs'][key]['displayProperties']['name']
                    
                    if en_name.strip() and zh_name.strip():
                        combined_data[en_name] = zh_name
        
        print(f"从 {definition_type} 提取了 {len(combined_data)} 个条目")
        all_data.append(combined_data)
    
    return all_data

def transform_and_sort_data(data_list):
    """转换数据，添加变体，并按英文术语长度排序"""
    print("转换和排序数据...")

    # 加载本地数据
    try:
        with open('myself.json', 'r', encoding='utf-8') as file:
            local_data = json.load(file)
    except FileNotFoundError:
        print("警告: 未找到'myself.json'，将继续处理而不使用本地数据")
        local_data = {}
    except json.JSONDecodeError:
        print("警告: 'myself.json'包含无效的JSON，将继续处理而不使用本地数据")
        local_data = {}

    # 合并所有字典
    combined_data = {}
    for data_dict in data_list:
        combined_data.update(data_dict)
    
    # 添加本地数据
    combined_data.update(local_data)
    
    # 创建一个新字典来存储增强数据
    augmented_data = combined_data.copy()

    # 添加变体
    for en, zh_chs in combined_data.items():
        # 添加弯引号版本
        if "'" in en:
            curved_en = en.replace("'", "’")
            augmented_data[curved_en] = zh_chs

        # 添加删除"The"前缀的版本
        if en.startswith("The "):
            without_the = en[4:]
            augmented_data[without_the] = zh_chs

    # 按英文术语长度排序
    sorted_data = dict(sorted(augmented_data.items(), key=lambda item: len(item[0].split()), reverse=True))
    print(f"一共处理了 {len(sorted_data)} 个条目")
    print("数据转换和排序完成")
    return sorted_data

def generate_data_hash(data):
    """生成数据哈希用于检测变更"""
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()

def save_merged_json(metadata, data, output_file):
    """保存合并后的JSON数据到文件"""
    print(f"保存合并后的JSON数据到文件: {output_file}...")
    output = {
        "metadata": metadata,
        "data": data
    }
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
    print(f"数据已保存到 {output_file}")

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

    # 定义要处理的定义类型列表
    definition_types = [
        "DestinyInventoryItemLiteDefinition",
        "DestinyActivityDefinition",
        "DestinySandboxPerkDefinition",
    ]
    
    # 获取并提取所有定义类型的数据
    data_list = fetch_and_extract_data(
        manifest,
        definition_types,
        LANG_LIST,
        ITEM_CATEGORY_FILTER,
        ITEM_CATEGORY_FILTER_DEL
    )
    
    # 转换和排序数据
    transformed_data = transform_and_sort_data(data_list)

    # 生成数据哈希
    data_hash = generate_data_hash(transformed_data)

    # 生成元数据
    metadata = {
        "version": current_version,
        "timestamp": start_time.isoformat(),
        "item_count": len(transformed_data),
        "data_hash": data_hash,
        "source": "Bungie Destiny 2 Manifest",
        "definition_types": definition_types
    }

    # 保存合并后的JSON数据（包含元数据）
    save_merged_json(metadata, transformed_data, OUTPUT_FILE_NAME)

    end_time = datetime.now(UTC)
    duration = end_time - start_time
    print(f"数据处理完成! 总耗时: {duration}")

if __name__ == "__main__":
    main()

