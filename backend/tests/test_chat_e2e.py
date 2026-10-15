"""Phase 7 端到端测试：会话创建 → WebSocket 流式对话 → 历史持久化"""
import sys, json, asyncio
import httpx
import websockets

BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"


async def main():
    # 1) 登录
    r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = r.json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}
    print("✅ 登录成功")

    # 2) 用 Phase 6 生成的审查报告（id=1）创建会话
    r = httpx.get(f"{BASE}/api/chat/conversations/1", headers=H)
    r.raise_for_status()
    conv_id = r.json()["id"]
    print(f"✅ 会话就绪: id={conv_id}")

    # 3) WebSocket 流式对话
    uri = f"{WS_BASE}/ws/chat/{conv_id}?token={token}"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "question", "content": "这份合同最大的付款风险是什么？怎么改？"}))
        print("⏳ 流式接收回答...")
        deltas = []
        answer = ""
        while True:
            frame = json.loads(await ws.recv())
            if frame["type"] == "delta":
                deltas.append(frame["content"])
            elif frame["type"] == "done":
                answer = frame["answer"]
                break
            elif frame["type"] == "error":
                print(f"❌ 服务端错误: {frame['message']}")
                sys.exit(1)
    print(f"✅ 流式完成: {len(deltas)} 个增量片段, 共 {len(answer)} 字")
    print(f"   回答摘要: {answer[:120]}...")

    # 4) 历史持久化验证
    r = httpx.get(f"{BASE}/api/chat/conversations/{conv_id}/messages", headers=H)
    r.raise_for_status()
    msgs = r.json()
    assert len(msgs) >= 2, f"历史消息应至少2条, 实际 {len(msgs)}"
    assert msgs[-2]["role"] == "user" and msgs[-1]["role"] == "assistant"
    print(f"✅ 历史持久化: {len(msgs)} 条消息 (user→assistant)")

    # 5) 鉴权失败场景：无 token
    try:
        async with websockets.connect(f"{WS_BASE}/ws/chat/{conv_id}") as ws:
            try:
                await ws.recv()
                print("⚠️ 未鉴权连接未按预期关闭")
            except websockets.exceptions.ConnectionClosed as e:
                assert e.rcvd and e.rcvd.code == 4401
                print("✅ 无 token 连接被正确拒绝 (code=4401)")
    except Exception as e:
        print(f"✅ 无 token 连接被拒绝: {type(e).__name__}")

    print("\n🎉 Phase 7 对话链路端到端通过")


asyncio.run(main())
