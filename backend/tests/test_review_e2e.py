"""端到端测试：登录 → 上传合同 → 发起审查(RAG+LLM，异步轮询) → 拉取报告"""
import sys, json, time
import httpx
from helpers import _asset

BASE = "http://localhost:8000"
KEY_HEADERS = {"Authorization": ""}


def login(username, password):
    r = httpx.post(f"{BASE}/api/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def upload_contract(token):
    with open(_asset("test_contract.docx"), "rb") as f:
        files = {"file": ("采购合同.docx", f,
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        r = httpx.post(f"{BASE}/api/contracts/upload", files=files,
                       headers={"Authorization": f"Bearer {token}"}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def wait_review(review_id, headers, timeout=180):
    """审查为异步执行：轮询直到 done / failed"""
    deadline = time.time() + timeout
    status = "running"
    while time.time() < deadline:
        time.sleep(1)
        st = httpx.get(f"{BASE}/api/reviews/{review_id}/status", headers=headers).json()
        status = st["status"]
        if status != "running":
            return st
    raise TimeoutError(f"审查 {timeout}s 未完成")


def main():
    token = login("admin", "admin123")
    H = {"Authorization": f"Bearer {token}"}
    print("✅ 登录成功")

    # 1) 上传合同
    contract_id = upload_contract(token)
    print(f"✅ 合同上传并解析: id={contract_id}")

    # 2) 发起审查（异步：立即返回 running，后台跑 RAG + LLM）
    print("⏳ 发起审查（后台执行中...）")
    r = httpx.post(f"{BASE}/api/reviews", json={"contract_id": contract_id},
                   headers=H, timeout=30)
    print(f"   HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"   错误: {r.text[:500]}")
        sys.exit(1)
    queued = r.json()
    review_id = queued["id"]
    print(f"✅ 已提交: report_id={review_id}, status={queued['status']}")

    # 3) 轮询直到完成
    st = wait_review(review_id, H)
    if st["status"] == "failed":
        print(f"❌ 审查失败: {st.get('error_message')}")
        sys.exit(1)

    report = httpx.get(f"{BASE}/api/reviews/{review_id}", headers=H).json()
    print(f"✅ 审查完成: overall_risk={report['overall_risk']}, "
          f"has_rag={report['has_rag']}, 风险项 {len(report['risk_items'])} 条")

    # 4) 打印报告
    for it in report["risk_items"]:
        pos = "👍正面" if it["is_positive"] else f"⚠️{it['risk_level']}"
        print(f"   [{pos}] {it['category_name']} | {it['contract_snippet'][:40]}...")
        print(f"        问题: {(it['issue'] or '')[:60]}")
        print(f"        建议: {(it['suggestion'] or '')[:60]}")

    # 5) 再次拉取报告（验证持久化）
    r2 = httpx.get(f"{BASE}/api/reviews/{review_id}", headers=H)
    r2.raise_for_status()
    d = r2.json()
    assert d["id"] == report["id"] and len(d["risk_items"]) == len(report["risk_items"])
    print(f"✅ 报告持久化验证: GET /api/reviews/{d['id']} 返回一致")

    # 6) 导出 Word
    exp = httpx.get(f"{BASE}/api/reviews/{review_id}/export", headers=H, timeout=60)
    assert exp.status_code == 200 and len(exp.content) > 5000
    print(f"✅ 导出 Word 成功: {len(exp.content)} bytes")

    print("\n🎉 审查链路端到端通过")


if __name__ == "__main__":
    main()
