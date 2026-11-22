# -*- coding: utf-8 -*-
"""规则化验收器：不需要 AI，也不需要 DSH 开着。

由 Windows 任务计划每 5 分钟跑一次（见 tools/install_task.py），也可以手动：

    python auto_verify.py            # 跑一次，打印结论
    python auto_verify.py --quiet    # 只写日志（给任务计划用）
    python auto_verify.py --dry      # 只看会怎么判，不写回

它只处理任务里写了 auto 规则的项，也就是"能机器判"的部分：

    "auto": {
        "min_evidence_files": 1,          # 成果目录里除提示文件外至少几个文件
        "url_required": true,             # 必须在 txt 里出现一个 http(s) 链接
        "url_hosts": ["github.com", "gitee.com"],   # 链接域名白名单（可选）
        "min_commits": 1                  # 仅对 github 仓库：至少几次提交
    }

没写 auto 的项原样留给人工/AI 复核，脚本不碰。
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
TASKS = BASE / "tasks.json"
QUEUE = BASE / "verify-queue.jsonl"
RESULTS = BASE / "verify-result.jsonl"
LOG = BASE / "auto_verify.log"
HINT = "放这里.txt"
UA = {"User-Agent": "todo-sidebar-auto-verify/1.0", "Accept": "application/json"}


def jload(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def jlines(p):
    try:
        return [l for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def log(msg, quiet):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    if not quiet:
        print(line)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def evidence_files(d):
    p = Path(d)
    if not p.exists():
        return []
    return [f for f in p.iterdir() if f.is_file() and f.name != HINT]


def find_url(files):
    pat = re.compile(r"https?://[^\s\"'<>）)]+")
    for f in files:
        if f.suffix.lower() not in (".txt", ".md", ""):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        m = pat.search(text)
        if m:
            return m.group(0).rstrip(".,;)")
    return None


def http_code(url, timeout=12):
    req = urllib.request.Request(url, headers=UA, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def github_repo(url):
    """返回 (owner, repo) 或 None。"""
    try:
        u = urllib.parse.urlparse(url)
    except Exception:
        return None
    if "github.com" not in (u.netloc or ""):
        return None
    parts = [p for p in (u.path or "").split("/") if p]
    if len(parts) < 2:
        return None
    return parts[0], parts[1].replace(".git", "")


def github_check(owner, repo):
    """返回 dict(public=?, commits=n) 或 (None, 原因)。"""
    api = "https://api.github.com/repos/%s/%s" % (owner, repo)
    try:
        req = urllib.request.Request(api, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            info = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, "仓库不存在或不是公开的（API 404）"
        return None, "GitHub API 返回 %s，暂时无法核实" % e.code
    except Exception as e:
        return None, "连不上 GitHub API（%s）" % type(e).__name__

    commits = None
    try:
        cu = "https://api.github.com/repos/%s/%s/commits?per_page=100" % (owner, repo)
        with urllib.request.urlopen(urllib.request.Request(cu, headers=UA), timeout=12) as r:
            commits = len(json.loads(r.read().decode("utf-8")))
    except Exception:
        commits = None
    return dict(public=not info.get("private", False), commits=commits), ""


def judge(item, d):
    """返回 (verdict, reason) 或 (None, 说明为什么跳过)。"""
    rule = item.get("auto") or {}
    files = evidence_files(d)
    body_files = [f for f in files]
    need_files = rule.get("min_evidence_files")
    if need_files is not None and len(body_files) < need_files:
        return "fail", "成果目录里只有 %d 个文件，要求至少 %d 个" % (len(body_files), need_files)

    url = find_url(files)
    if rule.get("url_required"):
        if not url:
            return "fail", "没找到链接：请在成果目录里放一个 txt，里面写仓库地址"
        hosts = rule.get("url_hosts") or []
        if hosts and not any(h in url for h in hosts):
            return "fail", "链接不在允许的域名里（要求 %s）" % " / ".join(hosts)
        code = http_code(url)
        if code is None:
            return "fail", "链接打不开（无响应）：%s" % url
        if code >= 400:
            return "fail", "链接返回 HTTP %d：%s" % (code, url)
        gh = github_repo(url)
        if gh and rule.get("min_commits"):
            info, why = github_check(*gh)
            if info is None:
                return None, "跳过：%s" % why
            if info["commits"] is not None and info["commits"] < int(rule["min_commits"]):
                return "fail", "仓库只有 %d 次提交，要求 ≥%d" % (info["commits"], rule["min_commits"])
    return "pass", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    tasks = jload(TASKS, {})
    if not tasks:
        log("没有 tasks.json，退出", args.quiet)
        return 0

    items = {}
    for d in tasks.get("days", []):
        for it in d.get("items", []):
            items[it.get("id")] = it
    for it in tasks.get("week", []):
        items[it.get("id")] = it

    decided = set()
    for line in jlines(RESULTS):
        try:
            decided.add(json.loads(line).get("id"))
        except Exception:
            pass

    n = 0
    for line in jlines(QUEUE):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        iid = rec.get("id")
        if not iid or iid in decided:
            continue
        item = items.get(iid)
        if not item:
            log("跳过 %s：任务里找不到这条" % iid, args.quiet)
            continue
        if not item.get("auto"):
            log("跳过 %s：没写 auto 规则，留给人工复核" % iid, args.quiet)
            continue
        verdict, reason = judge(item, rec.get("dir"))
        if verdict is None:
            log("%s：%s" % (iid, reason), args.quiet)
            continue
        out = {"id": iid, "verdict": verdict, "reason": reason, "by": "auto", "ts": time.time()}
        log("%s -> %s %s" % (iid, verdict, reason), args.quiet)
        if args.dry:
            continue
        with open(RESULTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
        decided.add(iid)
        n += 1

    log("本次写入 %d 条结论" % n, args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
