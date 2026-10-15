"""测试脚本：上传 .docx 合同 → 解析 → 返回结构化章节"""
import urllib.request, json, base64, mimetypes
import sys as _sys
_sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from helpers import _asset

BASE = "http://localhost:8000"

# —— 1. 登录拿 token ——
login_data = json.dumps({"username": "admin", "password": "admin123"}).encode()
req = urllib.request.Request(
    f"{BASE}/api/auth/login", data=login_data,
    headers={"Content-Type": "application/json"}
)
resp = json.loads(urllib.request.urlopen(req).read())
token = resp["access_token"]
print(f"✅ 登录成功, role={resp['role']}")

# —— 2. 用 requests 风格的 multipart 上传 ——
# Python 原生 urllib 做 multipart 比较麻烦，用 httpx（已在 requirements.txt 里）
import httpx

with open(_asset("test_contract.docx"), "rb") as f:
    files = {"file": ("采购合同.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.post(f"{BASE}/api/contracts/upload", files=files, headers=headers, timeout=30)

result = r.json()
print(f"✅ HTTP {r.status_code}")
print(f"   Full response: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
if isinstance(result, dict) and "data" in result and result["data"]:
    d = result["data"]
    print(f"   合同 ID: {d['id']}")
    print(f"   文件名: {d['filename']}")
    print(f"   状态: {d['status']}")
    print(f"   字数: {d['word_count']}")
    print(f"   章节数: {len(d['sections'])}")
    print(f"   中文检测: {d['language']}")
    for s in d["sections"]:
        print(f"   - [{s['level']}] {s['title']}")
else:
    print(f"   错误: {result}")
