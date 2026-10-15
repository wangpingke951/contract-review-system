"""Phase 5 RAG 管线端到端测试：切块 → 向量化(本地) → ChromaDB 入库 → 检索"""
import sys, asyncio
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), ".."))

KNOWLEDGE_DOC = """审查指引：采购合同风险要点

第一条 合同标的
审查采购合同标的条款时，应确认设备型号、数量、单价、技术参数在正文中或附件中明确列明，避免"一批""若干"等模糊表述。附件应作为合同组成部分并在正文中援引。

第二条 合同金额
合同金额应当同时使用大写与小写金额，并明确是否含税、税费承担方。仅有小写金额或未约定含税口径的，属于金额条款缺陷，应提示补充。

第三条 付款方式
付款条件应与履约进度挂钩，避免"货到后30日内一次性付款"这类对采购方不利的条款。建议约定验收合格后分期支付，并保留5%-10%质保金，质保期满后支付。

第四条 违约责任
违约金比例应双向对等，单方设置高额违约金（超过合同金额20%）而对方违约金缺失或极低的，属于显失公平条款，应提示调整。同时应约定迟延交付的按日计罚标准。

第五条 争议解决
争议解决条款应关注管辖约定。对方所在地法院管辖对采购方不利，建议约定为我方所在地法院或双方认可的仲裁机构。约定仲裁的应写明具体仲裁委员会名称。

第六条 保密条款
保密条款应双向对等，明确保密范围、保密期限（一般不超过5年）及违约责任。仅约束一方的保密条款应要求修改为双向。
"""

QUERY = "采购合同的付款方式有什么风险？货到一次性付款好吗？"


async def main():
    from app.rag.chunker import chunk_knowledge_text
    from app.rag.embedding import get_embedding
    from app.rag import vectorstore

    # 1) 切块
    chunks = chunk_knowledge_text(
        KNOWLEDGE_DOC, source_doc_id=1, source_filename="采购审查指引.txt", category="guide"
    )
    print(f"✅ 切块完成: {len(chunks)} 个 chunk")
    for c in chunks:
        print(f"   [{c.metadata['chunk_index']}] {c.metadata['section_title']} ({len(c.text)}字)")

    # 2) 向量化（本地模型，首次运行会下载 onnx 模型）
    emb = get_embedding()
    texts = [c.text for c in chunks]
    vectors = await emb.embed_batch(texts)
    print(f"✅ 向量化完成: {len(vectors)} 条, 维度={len(vectors[0])}")

    # 3) 入库
    metadatas = [c.metadata for c in chunks]
    ids = vectorstore.upsert_chunks(chunks=texts, metadatas=metadatas, embeddings=vectors)
    print(f"✅ ChromaDB 入库: {len(ids)} 条, collection 总数={vectorstore.count_chunks()}")

    # 4) 检索
    qvec = await emb.embed_text(QUERY)
    hits = vectorstore.similarity_search(query_embedding=qvec, query_text=None, k=4)
    print(f"✅ 检索 '{QUERY[:20]}...': {len(hits)} 条命中")
    for h in hits:
        print(f"   sim={h['similarity']:.3f} | {h['metadata']['section_title']} | {h['text'][:50]}...")

    # 5) retriever 对话检索
    from app.rag.retriever import retrieve_for_chat
    ev = await retrieve_for_chat("违约金比例多少合适？")
    print(f"✅ retrieve_for_chat: {len(ev)} 条证据")

    await asyncio.sleep(0)
    print("\n🎉 Phase 5 RAG 管线全部通过")

asyncio.run(main())
