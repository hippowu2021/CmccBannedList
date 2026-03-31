"""
Project: Rule-Converter
Version: V0.05 (Proxy Complete)
Description: 增加全局代理支持，urllib下载与Git操作均可通过本地代理进行。
"""

import urllib.request
import urllib.error
import socket
import os
import json
import subprocess
import time


def load_config(config_path="config.json"):
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_config(config_path, config_data):
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)


def get_proxy_url(config):
    proxy = config["settings"].get("proxy", {})
    if proxy.get("enabled"):
        return f"http://{proxy['host']}:{proxy['port']}"
    return None


def run_git_command(repo_dir, args, proxy_url=None, timeout=60):
    """执行 Git 命令并返回执行结果"""
    try:
        env = os.environ.copy()
        if proxy_url:
            env["http_proxy"] = proxy_url
            env["https_proxy"] = proxy_url
            env["HTTP_PROXY"] = proxy_url
            env["HTTPS_PROXY"] = proxy_url
        result = subprocess.run(
            ["git"] + args,
            cwd=repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            env=env,
            timeout=timeout,
        )
        return True, result.stdout
    except subprocess.TimeoutExpired:
        return False, f"Git 命令超时（{timeout}s）"
    except Exception as e:
        return False, str(e)


def process_task(source_url, repo_dir, sub_dir, base_name, config_data, save_list=True):
    r"""
    核心转换逻辑。
    repo_dir: 仓库根目录
    sub_dir: 子路径
    """
    final_target_dir = os.path.normpath(os.path.join(repo_dir, sub_dir))
    os.makedirs(final_target_dir, exist_ok=True)

    cvc_path = os.path.join(final_target_dir, f"{base_name}.cvc")
    list_path = os.path.join(final_target_dir, f"{base_name}.list")
    valid_prefixes = ("DOMAIN,", "DOMAIN-KEYWORD,", "DOMAIN-SUFFIX,")

    proxy_url = get_proxy_url(config_data)
    timeout_conf = config_data["settings"].get("timeout", {})
    head_timeout = timeout_conf.get("head_request", 10)
    get_timeout = timeout_conf.get("get_request", 30)

    proxy_handler = (
        urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        if proxy_url
        else urllib.request.ProxyHandler({})
    )
    opener = urllib.request.build_opener(proxy_handler)

    try:
        headers = {
            "User-Agent": config_data["settings"].get("user_agent", "Mozilla/5.0")
        }
        # 1. 更新预检
        req = urllib.request.Request(source_url, headers=headers)
        req.get_method = lambda: "HEAD"
        with opener.open(req, timeout=head_timeout) as response:
            current_id = response.getheader("ETag") or response.getheader(
                "Last-Modified"
            )

        if (
            current_id
            and config_data["state"].get(base_name) == current_id
            and os.path.exists(cvc_path)
        ):
            print(f"| SKIP    | {base_name: <14} | 状态: 已是最新")
            return False

        # 2. 下载与转换
        print(f"| UPDATE  | {base_name: <14} | 正在生成...")
        get_req = urllib.request.Request(source_url, headers=headers)
        with opener.open(get_req, timeout=get_timeout) as resp:
            raw_content = resp.read().decode("utf-8")

        if save_list:
            with open(list_path, "w", encoding="utf-8") as f:
                f.write(raw_content)

        cvc_output = ["payload:"]
        seen_rules = set()
        for line in raw_content.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            if line_s.startswith("#"):
                cvc_output.append(f"  {line_s}")
            elif line_s.startswith(valid_prefixes):
                fmt_rule = f"  - {line_s}"
                if fmt_rule not in seen_rules:
                    cvc_output.append(fmt_rule)
                    seen_rules.add(fmt_rule)

        with open(cvc_path, "w", encoding="utf-8") as f:
            f.write("\n".join(cvc_output) + "\n")

        config_data["state"][base_name] = current_id
        return True
    except socket.timeout:
        print(f"| ERROR   | {base_name: <14} | 请求超时")
        return False
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.timeout):
            print(f"| ERROR   | {base_name: <14} | 请求超时")
        else:
            print(f"| ERROR   | {base_name: <14} | 网络错误: {e.reason}")
        return False
    except Exception as e:
        print(f"| ERROR   | {base_name: <14} | {e}")
        return False


def main():
    config_file = "config.json"
    config = load_config(config_file)
    if not config:
        print("错误: 无法加载 config.json")
        return

    sett = config["settings"]
    repo_dir = os.path.normpath(os.path.join(sett["root_dir"], sett["project_name"]))
    git_conf = sett["git_integration"]
    proxy_url = get_proxy_url(config)
    git_timeout = sett.get("timeout", {}).get("git_command", 60)

    # --- 核心改进：前置全量同步 ---
    if git_conf["enabled"] and git_conf["auto_pull"]:
        print("=" * 65)
        print(f"开始同步远程仓库: {sett['project_name']}")

        # 步骤 1: Fetch 所有远程更新
        run_git_command(repo_dir, ["fetch", "--all"], proxy_url, git_timeout)

        # 步骤 2: Pull 最新文件到本地
        success, log = run_git_command(
            repo_dir,
            [
                "pull",
                git_conf.get("remote_name", "origin"),
                git_conf.get("branch", "main"),
            ],
            proxy_url,
            git_timeout,
        )
        if success:
            print("本地文件已更新至远程最新状态。")
        else:
            print(f"同步提示: {log.strip()}")
        print("-" * 65)

    # 任务清单
    tasks = [
        (
            "https://raw.githubusercontent.com/Hexon-X/Hex-Clash/refs/heads/main/list/Ai/Gemini.list",
            "Gemini",
            "AI",
            True,
        ),
        (
            "https://raw.githubusercontent.com/Hexon-X/Hex-Clash/refs/heads/main/list/Ai/OpenAI.list",
            "OpenAI",
            "AI",
            True,
        ),
        (
            "https://raw.githubusercontent.com/hippowu2021/CmccBannedList/refs/heads/main/CmccBannedList.list",
            "CmccBannedList",
            "",
            False,
        ),
    ]

    updated_flag = False
    for url, name, sub, sl in tasks:
        if process_task(url, repo_dir, sub, name, config, save_list=sl):
            updated_flag = True

    # 提交改动
    if updated_flag:
        save_config(config_file, config)
        if git_conf["enabled"]:
            print("-" * 65)
            print("检测到本地更新，准备提交...")
            run_git_command(repo_dir, ["add", "."], proxy_url, git_timeout)
            msg = f"{git_conf['commit_message']} @ {time.strftime('%Y-%m-%d %H:%M:%S')}"
            run_git_command(repo_dir, ["commit", "-m", msg], proxy_url, git_timeout)
            if git_conf["auto_push"]:
                success, log = run_git_command(
                    repo_dir, ["push"], proxy_url, git_timeout
                )
                if success:
                    print("SUCCESS: 远程仓库同步完成。")
                else:
                    print(f"PUSH ERROR: {log}")
    else:
        print("-" * 65)
        print("无变动：本地与远程均已是最新版本。")
    print("=" * 65)


if __name__ == "__main__":
    main()
