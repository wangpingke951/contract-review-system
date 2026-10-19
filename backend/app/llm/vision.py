"""
app/llm/vision.py — 多模态（VLM）文字提取

图片合同不做本地 OCR，直接交给多模态大模型识别：
- 走 OpenAI 兼容的 chat/completions（image_url 传 base64 data URI）
- 豆包 doubao-vision / 通义 qwen-vl-plus / 硅基流动 Qwen2.5-VL / OpenAI gpt-4o-mini 均可用
- 配置项 VISION_MODEL 必填；VISION_API_KEY / VISION_BASE_URL 留空则继承 LLM 配置

相比本地 PaddleOCR：
- 无需安装 300MB+ 运行时与模型文件
- 对倾斜、拍照、带表格的扫描件鲁棒性更好，还能顺带纠正错别字
"""
from __future__ import annotations

import base64
import io
from typing import Optional

import httpx
from PIL import Image

from app.config import get_settings

# 送模型前把长边压到这个尺寸：再大对识别无增益，只烧 token
MAX_IMAGE_SIDE = 2000
JPEG_QUALITY = 88

EXTRACT_PROMPT = """你是一个合同扫描件文字提取器。请逐字提取图片中的全部可见文字，按原始阅读顺序输出纯文本。

要求：
1. 保留标题、条款编号、段落换行等排版结构
2. 表格按行输出，同一行的单元格之间用 | 分隔
3. 不要翻译、不要总结、不要补充原文没有的内容
4. 不要输出 markdown 代码块标记，不要任何解释性文字
5. 如果图片中确实没有任何可读文字，只输出：[NO_TEXT]"""


class VisionExtractor:
    """OpenAI 兼容协议的多模态文字提取器"""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @staticmethod
    def _to_data_uri(image_bytes: bytes) -> str:
        """统一转 JPEG 并缩放，返回 data URI（控制请求体积）"""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img = img.convert("RGB")
            w, h = img.size
            longest = max(w, h)
            if longest > MAX_IMAGE_SIDE:
                scale = MAX_IMAGE_SIDE / longest
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            payload = buf.getvalue()
        except Exception:
            # Pillow 解不开就原样送（少数格式它不支持但模型能收）
            payload = image_bytes
        return "data:image/jpeg;base64," + base64.b64encode(payload).decode("ascii")

    async def extract_text(self, image_bytes: bytes) -> str:
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACT_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": self._to_data_uri(image_bytes)},
                        },
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
        text = (data["choices"][0]["message"]["content"] or "").strip()
        # 容忍模型自作主张加代码块
        if text.startswith("```"):
            lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
            text = "\n".join(lines).strip()
        return text


def get_vision_extractor() -> tuple[Optional[VisionExtractor], str]:
    """
    返回 (提取器, 不可用原因)。
    配置缺失时提取器为 None，原因文案直接回给用户，避免「识别失败」这种无指向的报错。
    """
    s = get_settings()

    if s.LLM_PROVIDER == "mock" and not s.VISION_MODEL:
        return None, (
            "图片合同需要多模态模型识别，当前为 mock 模式无法识图。"
            "请在 backend/.env 配置 VISION_MODEL（如 doubao-vision / qwen-vl-plus / Qwen/Qwen2.5-VL-7B-Instruct）"
            "及 VISION_API_KEY 后重启后端；也可改用 PDF / Word 格式上传"
        )

    api_key = s.VISION_API_KEY or s.LLM_API_KEY
    model = s.VISION_MODEL
    base_url = s.VISION_BASE_URL or s.LLM_BASE_URL

    if not model:
        return None, (
            "多模态识别未配置：请在 backend/.env 设置 VISION_MODEL"
            "（如 doubao-vision / qwen-vl-plus / Qwen/Qwen2.5-VL-7B-Instruct）"
        )
    if not api_key:
        return None, "多模态识别未配置：请在 backend/.env 设置 VISION_API_KEY（留空则继承 LLM_API_KEY）"
    if not base_url:
        return None, "多模态识别未配置：请在 backend/.env 设置 VISION_BASE_URL（留空则继承 LLM_BASE_URL）"

    return VisionExtractor(base_url=base_url, api_key=api_key, model=model), ""
