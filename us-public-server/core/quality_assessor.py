"""
影像质量评估模块（GPT-4.1-mini）
"""
import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Tuple

from openai import OpenAI
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

QUALITY_PROMPT = """You are a satellite imagery quality analyst.
Evaluate the quality of this remote sensing image for disaster analysis purposes.

Score the image from 0-100 and assess:
1. Cloud coverage percentage (0-100%)
2. Overall clarity (clear / hazy / cloudy)
3. Presence of data gaps or black stripes
4. Suitability for disaster impact analysis

Respond ONLY with valid JSON in this exact format:
{
  "score": <0-100>,
  "cloud_coverage": <0-100>,
  "clarity": "<clear|hazy|cloudy>",
  "has_data_gaps": <true|false>,
  "pass": <true|false>,
  "issues": ["<issue1>", "<issue2>"],
  "recommendation": "<brief recommendation>"
}

A score >= 60 means "pass: true". Cloud coverage > 30% usually means fail."""


class QualityAssessor:
    """使用 GPT-4.1-mini Vision 评估遥感影像质量"""

    def __init__(self):
        self.cfg = settings.QUALITY_CONFIG
        self.enabled = self.cfg.get("enabled", True)
        self.fail_open = self.cfg.get("fail_open", settings.APP_ENV != "production")
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
        return self._client

    def _encode_image(self, path: Path) -> Tuple[str, str]:
        """Return mime + base64 payload, favoring downscaled PNG for huge GeoTIFFs."""
        max_dim = self.cfg.get("max_image_edge", 1024)

        if Image is None:
            logger.warning("Pillow 未安装，直接发送原始影像字节，可能体积较大")
            data = path.read_bytes()
            suffix = path.suffix.lower()
            mime = "image/tiff" if suffix == ".tif" else "image/png"
            return mime, base64.b64encode(data).decode()
        try:
            with Image.open(path) as img:
                img = img.convert("RGB")
                img.thumbnail((max_dim, max_dim))
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                payload = base64.b64encode(buffer.getvalue()).decode()
                return "image/png", payload
        except Exception as exc:
            logger.warning(f"转换影像为PNG失败，改用原始字节: {exc}")
            data = path.read_bytes()
            suffix = path.suffix.lower()
            mime = "image/tiff" if suffix == ".tif" else "image/png"
            return mime, base64.b64encode(data).decode()

    def _extract_response_content(self, response) -> str:
        """兼容不同 OpenAI / OpenAI-compatible 返回结构，提取文本内容。"""
        if response is None:
            raise ValueError("empty response")

        if isinstance(response, str):
            response = response.strip()
            if response.startswith("data:"):
                return self._extract_sse_content(response)
            return response

        if isinstance(response, dict):
            choices = response.get("choices") or []
            if choices:
                message = choices[0].get("message") or {}
                content = message.get("content", "")
                if isinstance(content, list):
                    return "".join(
                        p.get("text", "") for p in content if isinstance(p, dict)
                    ).strip()
                return str(content).strip()

            if "output_text" in response:
                return str(response.get("output_text", "")).strip()

        choices = getattr(response, "choices", None)
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", "") if message is not None else ""
            if isinstance(content, list):
                return "".join(
                    getattr(p, "text", "") if not isinstance(p, dict) else p.get("text", "")
                    for p in content
                ).strip()
            return str(content).strip()

        output_text = getattr(response, "output_text", None)
        if output_text is not None:
            return str(output_text).strip()

        raise ValueError(f"unknown response type: {type(response).__name__}")

    def _extract_sse_content(self, raw_text: str) -> str:
        """从 data: 开头的 SSE 文本中拼接最终 assistant 内容。"""
        chunks = []
        in_think_block = False

        for line in raw_text.splitlines():
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue

            payload = line[5:].strip()
            if payload == "[DONE]":
                continue

            try:
                item = json.loads(payload)
            except json.JSONDecodeError:
                continue

            for choice in item.get("choices") or []:
                delta = choice.get("delta") or {}
                piece = delta.get("content")
                if not piece:
                    continue

                if "<think>" in piece:
                    in_think_block = True
                if in_think_block:
                    if "</think>" in piece:
                        in_think_block = False
                    continue

                stripped = piece.strip()
                if stripped.startswith("code_execution "):
                    continue
                if stripped.startswith("web_search"):
                    continue
                if stripped.startswith("[WebSearch]"):
                    continue

                chunks.append(piece)

        return "".join(chunks).strip()

    def _extract_json_object(self, content: str) -> Optional[Dict]:
        """从文本中提取首个完整 JSON 对象。"""
        start = content.find("{")
        if start < 0:
            return None

        depth = 0
        in_string = False
        escaped = False

        for idx in range(start, len(content)):
            ch = content[idx]

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = content[start:idx + 1]
                    return json.loads(candidate)

        return None

    def assess_image(self, image_path: str) -> Optional[Dict]:
        """
        评估单张影像质量。
        返回评估结果字典，或 None（评估失败）。
        """
        if not self.enabled:
            logger.info("质量评估已禁用，直接通过")
            return {"score": 80, "pass": True, "cloud_coverage": 10, "clarity": "clear",
                    "has_data_gaps": False, "issues": [], "recommendation": "Disabled"}

        path = Path(image_path)
        if not path.exists():
            logger.error(f"影像文件不存在: {image_path}")
            return None

        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY 未配置，跳过质量评估")
            return {"score": 70, "pass": True, "cloud_coverage": 15, "clarity": "clear",
                    "has_data_gaps": False, "issues": [], "recommendation": "API key not set"}

        try:
            # 下采样并编码
            mime, img_b64 = self._encode_image(path)

            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": QUALITY_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=300,
                temperature=0,
            )

            content = self._extract_response_content(response)
            result = self._extract_json_object(content)
            if result is not None:
                logger.info(
                    f"质量评估完成: score={result.get('score')}, "
                    f"cloud={result.get('cloud_coverage')}%, pass={result.get('pass')}"
                )
                return result

            logger.warning(f"质量评估响应格式异常: {content[:200]}")
            return None

        except Exception as e:
            logger.error(f"质量评估失败: {e}")
            return None

    def assess_pair(self, pre_path: str, post_path: str) -> Dict:
        """
        评估灾前/灾后影像对的综合质量。
        返回合并结果。
        """
        pre_result = self.assess_image(pre_path)
        post_result = self.assess_image(post_path)

        if pre_result is None and post_result is None:
            return {"score": 0, "pass": False, "error": "两张影像均评估失败"}

        scores = []
        if pre_result:
            scores.append(pre_result.get("score", 0))
        if post_result:
            scores.append(post_result.get("score", 0))

        avg_score = sum(scores) / len(scores)
        threshold = self.cfg.get("pass_score_threshold", 60)

        combined_pass = avg_score >= threshold
        if pre_result and not pre_result.get("pass", False):
            combined_pass = False
        if post_result and not post_result.get("pass", False):
            combined_pass = False

        if not combined_pass and self.fail_open:
            logger.warning(
                f"质量评估未通过 (score={avg_score:.1f}) 但 fail_open 启用，强制放行"
            )
            combined_pass = True

        return {
            "score": round(avg_score, 1),
            "pass": combined_pass,
            "pre_result": pre_result,
            "post_result": post_result,
        }
