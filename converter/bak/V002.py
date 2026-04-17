"""
Project: Rule-Converter
Version: V0.02
Python: 3.14+ (Compatible 3.10+)
Description: 支持配置文件、增量更新及注释保留的自动化规则转换工具。
"""

import urllib.request
import os
import json
import tempfile

def load_config(config_path):
    """加载配置文件，若不存在则初始化默认配置"""
    default_config = {
        "settings": {
            "output_dir": "d:\\tmp",  # 可在此修改默认输出目录
            "git_push_enabled": False,
            "git_repo_url": ""
        },
        "state": {}  # 存储文件的 ETag 或 Last-Modified
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            print("警告: 配置文件格式异常，将使用默认设置。")
    return default_config

def save_config(config_path, config_data):
    """持久化配置与状态"""
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

def get_effective_dir(config_dir):
    """确定最终输出文件夹，支持 Windows 临时目录回退"""
    if config_dir and config_dir.strip():
        target = os.path.expandvars(config_dir)
    else:
        # 回退到 Windows 临时目录
        target = os.path.join(tempfile.gettempdir(), "RuleConverter")
    
    os.makedirs(target, exist_ok=True)
    return target

def process_task(source_url, target_dir, base_name, config_data):
    """单项转换任务逻辑"""
    cvc_path = os.path.join(target_dir, f"{base_name}.cvc")
    list_path = os.path.join(target_dir, f"{base_name}.list")
    valid_prefixes = ("DOMAIN,", "DOMAIN-KEYWORD,", "DOMAIN-SUFFIX,")
    
    try:
        # 1. 预检更新 (HEAD 请求)
        req = urllib.request.Request(source_url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            current_id = response.getheader('ETag') or response.getheader('Last-Modified')

        # 2. 状态比对 (判断是否需要执行)
        last_id = config_data["state"].get(base_name)
        if last_id == current_id and os.path.exists(cvc_path) and os.path.exists(list_path):
            print(f"| SKIP    | {base_name: <7} | 文件已是最新，跳过。")
            return False

        # 3. 下载内容
        print(f"| UPDATE  | {base_name: <7} | 发现更新，正在同步...")
        get_req = urllib.request.Request(source_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(get_req) as resp:
            raw_content = resp.read().decode('utf-8')

        # 保存 .list 镜像
        with open(list_path, "w", encoding="utf-8") as f:
            f.write(raw_content)

        # 4. 转换 .cvc 逻辑 (含注释保留)
        lines = raw_content.splitlines()
        cvc_output = ["payload:"]
        seen_rules = set()

        for line in lines:
            stripped = line.strip()
            if not stripped: continue
            
            if stripped.startswith('#'):
                # 保持注释并加缩进
                cvc_output.append(f"  {stripped}")
            elif stripped.startswith(valid_prefixes):
                # 规则行转换并去重
                fmt_rule = f"  - {stripped}"
                if fmt_rule not in seen_rules:
                    cvc_output.append(fmt_rule)
                    seen_rules.add(fmt_rule)

        with open(cvc_path, "w", encoding="utf-8") as f:
            f.write("\n".join(cvc_output) + "\n")

        # 5. 更新状态标识
        config_data["state"][base_name] = current_id
        print(f"| SUCCESS | {base_name: <7} | 处理完成 (规则数: {len(seen_rules)})")
        return True

    except Exception as e:
        print(f"| ERROR   | {base_name: <7} | 失败详情: {e}")
        return False

def main():
    config_file = "config.json"
    config_data = load_config(config_file)
    output_dir = get_effective_dir(config_data["settings"].get("output_dir"))
    
    # 待处理任务定义
    tasks = [
        ("https://raw.githubusercontent.com/Hexon-X/Hex-Clash/refs/heads/main/list/Ai/Gemini.list", "Gemini"),
        ("https://raw.githubusercontent.com/Hexon-X/Hex-Clash/refs/heads/main/list/Ai/OpenAI.list", "OpenAI")
    ]

    print("="*55)
    print(f" Rule-Converter V0.02 | 运行环境: Windows")
    print(f" 目标目录: {output_dir}")
    print("-" * 55)

    updated_any = False
    for url, name in tasks:
        if process_task(url, output_dir, name, config_data):
            updated_any = True

    if updated_any:
        save_config(config_file, config_data)
        print("-" * 55)
        print("所有本地改动已同步，配置文件已更新。")
    else:
        print("-" * 55)
        print("未检测到源文件更新。")
    print("="*55)

if __name__ == "__main__":
    main()