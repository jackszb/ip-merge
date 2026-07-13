#!/usr/bin/env python3
"""
合并 IPv4 / IPv6 CIDR 规则脚本

读取仓库根目录 ip.json 中配置的下载链接，下载各链接指向的规则文件
（兼容不同的 "version" 字段），提取其中的 ip_cidr，
分别按 IPv4 / IPv6 去重、排序、合并相邻或重叠网段，
最终在 rules/ 目录下生成：
  - ipv4.json  （仅 IPv4，统一 version: 3）
  - ipv6.json  （仅 IPv6，统一 version: 3）
  - ip.json    （IPv4 在前、IPv6 在后的合集，统一 version: 3）
"""
import json
import os
import sys
import urllib.request
import ipaddress

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "ip.json")
RULES_DIR = os.path.join(ROOT, "rules")

OUTPUT_VERSION = 3


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"未找到配置文件: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_json(url, timeout=20):
    print(f"下载: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw)


def extract_cidrs(data):
    """从任意 version 的规则文件中提取全部 ip_cidr 条目"""
    result = []
    for rule in data.get("rules", []):
        for item in rule.get("ip_cidr", []):
            item = item.strip()
            if item:
                result.append(item)
    return result


def collapse(cidr_list, ip_version):
    """按指定版本过滤、去重、排序，并合并相邻/重叠网段"""
    networks = []
    for item in cidr_list:
        try:
            net = ipaddress.ip_network(item, strict=False)
        except ValueError as e:
            print(f"忽略无效条目: {item} ({e})", file=sys.stderr)
            continue
        if net.version != ip_version:
            continue
        networks.append(net)

    merged = list(ipaddress.collapse_addresses(networks))
    merged.sort(key=lambda n: (n.network_address, n.prefixlen))
    return [str(n) for n in merged]


def build_rule_json(cidr_list):
    return {
        "version": OUTPUT_VERSION,
        "rules": [
            {"ip_cidr": cidr_list}
        ]
    }


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def collect(urls):
    cidrs = []
    for url in urls:
        try:
            data = fetch_json(url)
            cidrs.extend(extract_cidrs(data))
        except Exception as e:
            print(f"下载或解析失败，已跳过: {url} ({e})", file=sys.stderr)
    return cidrs


def main():
    config = load_config()
    ipv4_urls = config.get("ipv4_urls", [])
    ipv6_urls = config.get("ipv6_urls", [])

    raw_ipv4 = collect(ipv4_urls)
    raw_ipv6 = collect(ipv6_urls)

    ipv4_merged = collapse(raw_ipv4, 4)
    ipv6_merged = collapse(raw_ipv6, 6)

    os.makedirs(RULES_DIR, exist_ok=True)

    write_json(os.path.join(RULES_DIR, "ipv4.json"), build_rule_json(ipv4_merged))
    write_json(os.path.join(RULES_DIR, "ipv6.json"), build_rule_json(ipv6_merged))

    combined = ipv4_merged + ipv6_merged  # ipv4 在前，ipv6 在后
    write_json(os.path.join(RULES_DIR, "ip.json"), build_rule_json(combined))

    print(
        f"完成: ipv4={len(ipv4_merged)} 条, "
        f"ipv6={len(ipv6_merged)} 条, 合计={len(combined)} 条"
    )


if __name__ == "__main__":
    main()
