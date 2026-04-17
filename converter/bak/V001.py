"""
Project: Rule-Converter
Version: V0.01
Python Version: 3.14 (Optimized)
"""

import urllib.request
import os

def process_task(source_url, target_dir, base_name):
    """处理下载、备份与转换的核心函数"""
    cvc_path = os.path.join(target_dir, f"{base_name}.cvc")
    list_path = os.path.join(target_dir, f"{base_name}.list")
    valid_prefixes = ("DOMAIN,", "DOMAIN-KEYWORD,", "DOMAIN-SUFFIX,")
    
    try:
        # 抓取源文件
        req = urllib.request.Request(source_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            raw_content = response.read().decode('utf-8')

        # 保存原始备份 (.list)
        with open(list_path, "w", encoding="utf-8") as f_list:
            f_list.write(raw_content)

        # 执行转换逻辑 (.cvc)
        lines = raw_content.splitlines()
        processed_entries = []
        seen = set()

        for line in lines:
            s_line = line.strip()
            # 1. 过滤注释与空行
            if not s_line or s_line.startswith('#'):
                continue
            
            # 2. 匹配有效前缀
            if s_line.startswith(valid_prefixes):
                formatted = f"  - {s_line}"
                # 3. 去重且保序
                if formatted not in seen:
                    processed_entries.append(formatted)
                    seen.add(formatted)

        # 写入转换结果
        with open(cvc_path, "w", encoding="utf-8") as f_cvc:
            f_cvc.write("payload:\n")
            if processed_entries:
                f_cvc.write("\n".join(processed_entries) + "\n")
        
        print(f"| SUCCESS | {base_name: <7} | 有效行: {len(processed_entries)}")

    except Exception as e:
        print(f"| ERROR   | {base_name: <7} | 原因: {e}")

def main():
    target_folder = r"d:\tmp"
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    tasks = [
        ("https://raw.githubusercontent.com/Hexon-X/Hex-Clash/refs/heads/main/list/Ai/Gemini.list", "Gemini"),
        ("https://raw.githubusercontent.com/Hexon-X/Hex-Clash/refs/heads/main/list/Ai/OpenAI.list", "OpenAI")
    ]

    print("="*45)
    print(" 规则转换工具 V0.01 启动中...")
    print("-" * 45)
    for url, name in tasks:
        process_task(url, target_folder, name)
    print("="*45)
    print("所有任务已处理完毕。")

if __name__ == "__main__":
    main()