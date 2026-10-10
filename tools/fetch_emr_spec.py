# -*- coding: utf-8 -*-
"""
拉取 **EMR 独立后端** 的接口清单，存成 data/emr_api_spec.json。

EMR 不在 HIS 网关上（`/faith/*`），它是**另一个服务**：
    http://192.168.1.198:8021     ← 来自前端运行时配置 http://192.168.1.198:8088/config.js
                                    （打包默认值是 192.168.1.144:8033，那是别的院的，别用）
鉴权：**直接认 HIS 的 JWT**（`Authorization: Bearer <token>`），用 emradmin 或 admin 登录都行。

用法： python tools/fetch_emr_spec.py
"""
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
EMR = "http://192.168.1.198:8021"
HIS = "http://192.168.1.198:8081"


def main() -> int:
    s = requests.Session()
    s.proxies = {"http": None, "https": None}
    s.trust_env = False
    tok = s.post(f"{HIS}/login", json={"username": "emradmin", "password": "000000"},
                 timeout=15).json()["data"]
    r = s.get(f"{EMR}/v2/api-docs", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    if r.status_code != 200:
        print(f"[失败] EMR {EMR} 返回 {r.status_code}；先确认服务和 token")
        return 1
    d = r.json()
    out = ROOT / "data" / "emr_api_spec.json"
    out.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print(f"[产出] {out}")
    print(f"  路径 {len(d.get('paths', {}))} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
