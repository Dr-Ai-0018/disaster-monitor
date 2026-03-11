"""
影像质量评估模块（GPT-4.1-mini）
"""
import base64
import json
from pathlib import Path
from typing import Optional, Dict

from openai import OpenAI
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

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
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
        return self._client

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
            # 将影像编码为 base64
            suffix = path.suffix.lower()
            mime = "image/tiff" if suffix == ".tif" else "image/png"
            img_b64 = base64.b64encode(path.read_bytes()).decode()

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

            content = response.choices[0].message.content.strip()
            # 提取 JSON
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(content[start:end])
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

        return {
            "score": round(avg_score, 1),
            "pass": combined_pass,
            "pre_result": pre_result,
            "post_result": post_result,
        }
