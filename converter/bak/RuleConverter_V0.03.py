"""
Project: Rule-Converter
Version: V0.03
Description: 自动化规则转换并同步至 Git 仓库。
"""

import urllib.request
import os
import json
import subprocess
import time

def load_config(config_path="config.json"):
    """加载配置文件"""
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_config(config_path, config_data):
    """保存配置与状态"""
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

def run_git_command(repo_dir, args):
    """执行 Git 命令并捕获结果"""
    try:
        result = subprocess.run(
            ["git"] + args, 
            cwd=repo_dir, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except Exception as e:
        return False, str(e)

def process_task(source_url, target_dir, base_name, config_data):
    """核心转换逻辑"""
    cvc_path = os.path.join(target_dir, f"{base_name}.cvc")
    list_path = os.path.join(target_dir, f"{base_name}.list")
    valid_prefixes = ("DOMAIN,", "DOMAIN-KEYWORD,", "DOMAIN-SUFFIX,")
    
    try:
        # 1. 预检更新 (HEAD 请求)
        req = urllib.request.Request(source_url, headers={'User-Agent': 'Mozilla/5.0'})
        req.get_method = lambda: 'HEAD'
        with urllib.request.urlopen(req) as response:
            current_id = response.getheader('ETag') or response.getheader('Last-Modified')

        if config_data["state"].get(base_name) == current_id and os.path.exists(cvc_path):
            print(f"| SKIP    | {base_name: <7} | 无更新。")
            return False

        # 2. 获取并处理内容
        print(f"| UPDATE  | {base_name: <7} | 检测到更新，下载中...")
        with urllib.request.urlopen(urllib.request.Request(source_url, headers={'User-Agent': 'Mozilla/5.0'})) as resp:
            raw_content = resp.read().decode('utf-8')

        with open(list_path, "w", encoding="utf-8") as f:
            f.write(raw_content)

        cvc_output = ["payload:"]
        seen = set()
        for line in raw_content.splitlines():
            s = line.strip()
            if not s: continue
            if s.startswith('#'):
                cvc_output.append(f"  {s}") # 保留注释并缩进
            elif s.startswith(valid_prefixes):
                fmt = f"  - {s}"
                if fmt not in seen:
                    cvc_output.append(fmt)
                    seen.add(fmt)

        with open(cvc_path, "w", encoding="utf-8") as f:
            f.write("\n".join(cvc_output) + "\n")

        config_data["state"][base_name] = current_id
        return True
    except Exception as e:
        print(f"| ERROR   | {base_name: <7} | {e}")
        return False

def main():
    config_file = "config.json"
    config = load_config(config_file)
    if not config:
        print("错误: 找不到 config.json。")
        return

    # 路径解析
    sett = config["settings"]
    repo_dir = os.path.join(sett["root_dir"], sett["project_name"])
    target_dir = os.path.join(repo_dir, sett["sub_dir"])
    
    # 确保目录存在
    os.makedirs(target_dir, exist_ok=True)

    git_conf = sett["git_integration"]
    
    # 1. 自动化 Pull 同步
    if git_conf["enabled"] and git_conf["auto_pull"]:
        print(f"正在从远程同步仓库...")
        success, out = run_git_command(repo_dir, ["pull", git_conf.get("remote_name", "origin"), git_conf.get("branch", "main")])
        if not success:
            print(f"警告: Pull 失败 (可能本地已是最新或存在冲突): {out}")

    # 2. 转换任务
    tasks = [
        ("https://raw.githubusercontent.com/Hexon-X/Hex-Clash/refs/heads/main/list/Ai/Gemini.list", "Gemini"),
        ("https://raw.githubusercontent.com/Hexon-X/Hex-Clash/refs/heads/main/list/Ai/OpenAI.list", "OpenAI")
    ]

    print("-" * 55)
    any_updated = False
    for url, name in tasks:
        if process_task(url, target_dir, name, config):
            any_updated = True

    # 3. 自动化 Git 提交
    if any_updated:
        save_config(config_file, config)
        if git_conf["enabled"]:
            print("-" * 55)
            print("正在将改动推送至 GitHub...")
            run_git_command(repo_dir, ["add", "."])
            commit_msg = f"{git_conf['commit_message']} @ {time.strftime('%Y-%m-%d %H:%M:%S')}"
            run_git_command(repo_dir, ["commit", "-m", commit_msg])
            
            if git_conf["auto_push"]:
                success, out = run_git_command(repo_dir, ["push"])
                if success:
                    print("SUCCESS: 仓库已更新并推送到远程。")
                else:
                    print(f"ERROR: Push 失败: {out}")
    else:
        print("-" * 55)
        print("状态检查完毕：所有规则均已是最新，无须上传。")
    print("="*55)

if __name__ == "__main__":
    main()