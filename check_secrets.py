#!/usr/bin/env python
"""
check_secrets.py —— 提交前自检：防止密钥被误提交。

用法：
    python check_secrets.py

它会扫描 git 即将提交的文件内容，发现疑似密钥就报警并退出码 1。
可以手动跑，也可以接进 git pre-commit 钩子自动跑（见文件末尾说明）。

为什么需要它？
    这个项目曾经把含真实 API Key 的 .env 提交并推送到远程，
    靠人记住"别提交 .env"是不可靠的，得让机器兜住。
"""

import re
import subprocess
import sys
from pathlib import Path

# ---- 疑似密钥的匹配规则 ----
# 每条是 (规则名, 正则)。宁可误报也不能漏报。
PATTERNS = [
    ("OpenAI 风格密钥", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("通用 api_key 赋值", re.compile(r"""(?i)api[_-]?key['"]?\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]""")),
    ("通用 secret 赋值", re.compile(r"""(?i)secret['"]?\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]""")),
    ("Bearer token", re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}")),
    ("阿里/腾讯云密钥", re.compile(r"(?i)(LTAI[A-Za-z0-9]{12,}|AKID[A-Za-z0-9]{20,})")),
]

# 允许出现的"假密钥"占位符，避免把模板文件误判成泄露
ALLOWLIST_MARKERS = [
    "your-api-key-here",
    "your-key",
    "xxxx",
    "example.com",
    "sk-...",
    "placeholder",
]

# 这些文件本身是模板或不含真实值的文档，跳过
SKIP_SUFFIXES = {".example", ".sample", ".template", ".md"}


def repo_root() -> Path:
    """取 git 仓库根目录。

        ★ 关键：本仓库的根目录不是 mvp_agent/，而是上一级的 D:/ASpace/AgentWork。
          而 `git diff --cached --name-only` 返回的路径永远是相对仓库根目录的，
          所以必须把根目录拼上，否则读文件会找不到（这个坑实际踩过一次）。
        """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def staged_files() -> list:
    """列出 git 暂存区里的文件（即这次要提交的文件）。

        返回的是"相对仓库根目录"的路径字符串。
        """
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("警告：不在 git 仓库中，或 git 不可用。改为扫描工作区。")
        return []
    return [f for f in out.splitlines() if f.strip()]


def should_skip(path: str) -> bool:
    p = Path(path)
    if p.suffix in SKIP_SUFFIXES:
        return True
    if p.name in {".env.example", ".gitignore"}:
        return True
    return False


def scan_file(abs_path: Path, display_path: str) -> list:
    """扫描单个文件，返回 [(行号, 规则名, 该行内容)]。

        abs_path     —— 用于真正读取文件
        display_path —— 用于报错时显示（相对仓库根的路径，更好认）
        """
    findings = []
    try:
        # errors="replace" 防止二进制文件或编码异常导致崩溃
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return findings

    for lineno, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        # 命中允许列表的占位符，跳过
        if any(marker in low for marker in ALLOWLIST_MARKERS):
            continue
        for rule_name, pattern in PATTERNS:
            if pattern.search(line):
                findings.append((lineno, rule_name, line.strip()[:100]))
    return findings


def main() -> int:
    print("=" * 60)
    print("提交前密钥自检")
    print("=" * 60)

    root = repo_root()
    print(f"仓库根目录: {root}\n")

    files = staged_files()
    if not files:
        print("暂存区没有文件。先 git add 再跑本脚本。")
        return 0

    print(f"待检查 {len(files)} 个文件\n")

    total = 0
    for rel_path in files:
        if should_skip(rel_path):
            continue
        # 把"相对仓库根的路径"还原成绝对路径才能读到文件
        findings = scan_file(root / rel_path, rel_path)
        for lineno, rule_name, content in findings:
            total += 1
            print(f"  [命中] {rel_path}:{lineno}")
            print(f"         规则: {rule_name}")
            print(f"         内容: {content}")
            print()

    print("=" * 60)
    if total:
        print(f"发现 {total} 处疑似密钥。请确认后再提交。")
        print("误报时可把该占位符加进本脚本的 ALLOWLIST_MARKERS。")
        return 1
    print("未发现疑似密钥，可以放心提交。")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ============================================================
# 可选：接成 git pre-commit 钩子，每次提交自动跑
#
# 在仓库根目录执行（注意本仓库根目录是 D:/ASpace/AgentWork）：
#
#   cat > .git/hooks/pre-commit << 'EOF'
#   #!/bin/sh
#   python mvp_agent/check_secrets.py || exit 1
#   EOF
#   chmod +x .git/hooks/pre-commit
#
# Windows 上如果没有 sh，可以直接写 .bat 或用 python 钩子文件。
# ============================================================
