"""
日报生成模块（Gemini Flash + Pro，纯 requests 实现）
"""
import json
import time
import requests as _requests
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from config.settings import settings
from models.models import Product, DailyReport, Event
from utils.logger import get_logger

logger = get_logger(__name__)

FLASH_SUMMARY_PROMPT = """You are a disaster intelligence analyst. Based on the following disaster event data and AI analysis results, write a concise summary (3-5 sentences) in English.

Event Information:
{event_details}

AI Analysis Results:
{inference_results}

Write a factual, professional summary covering: what happened, where, estimated impact, and key observations from satellite imagery."""

PRO_REPORT_PROMPT = """You are a senior disaster intelligence analyst. Generate a comprehensive daily disaster monitoring report based on the following data.

Report Date: {date}
Total Events: {total_count}

Event Summaries:
{event_summaries}

Statistics:
- By Category: {category_stats}
- By Severity: {severity_stats}
- By Country: {country_stats}

Generate a professional report in Markdown format with these sections:
1. # Global Disaster Monitoring Daily Report — {date}
2. ## Executive Summary (2-3 paragraphs overview)
3. ## Key Statistics (tables)
4. ## High Priority Events (detail the top 3-5 most severe)
5. ## Trend Analysis (patterns, notable observations)
6. ## Recommendations

Use clear, professional language. Be factual and concise."""


def _extract_text(response_json: dict) -> str:
    """
    从 Gemini REST API 响应中提取正文文本。
    兼容 Gemini 2.5 Pro 的 thinking 模式：过滤掉 thought=true 的 parts，
    只拼接真正的回答 parts。
    """
    try:
        parts = response_json["candidates"][0]["content"]["parts"]
        texts = [p["text"] for p in parts if not p.get("thought", False) and "text" in p]
        return "\n".join(texts).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Gemini 响应格式异常: {e}\n原始响应: {json.dumps(response_json, ensure_ascii=False)[:500]}")


def _call_gemini(model: str, prompt: str, timeout: int = 60) -> str:
    """
    调用 Gemini REST API，返回纯文本结果。
    自动处理 thinking 模型（2.5 Pro）和普通模型（Flash）。
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未配置")

    url = f"{settings.GEMINI_BASE_URL}/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    api_key = settings.GEMINI_API_KEY
    # sk- 开头说明是中转站，用 Bearer 认证；否则用官方 ?key= 参数
    if api_key.startswith("sk-"):
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        resp = _requests.post(url, headers=headers, json=payload, timeout=timeout)
    else:
        resp = _requests.post(url, params={"key": api_key}, json=payload, timeout=timeout)

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API 错误 {resp.status_code}: {resp.text[:300]}")

    return _extract_text(resp.json())


class ReportGenerator:
    """使用 Gemini 生成灾害日报（纯 requests，无官方 SDK 依赖）"""

    # ── 单事件摘要（Gemini Flash） ────────────────────────

    def generate_event_summary(self, product: Product) -> Optional[str]:
        """为单个成品生成摘要"""
        if not settings.GEMINI_API_KEY:
            return "Summary generation skipped (no API key configured)."

        try:
            event_details = {}
            inference_results = {}
            try:
                event_details = json.loads(product.event_details) if product.event_details else {}
                inference_results = json.loads(product.inference_result) if product.inference_result else {}
            except Exception:
                pass

            inference_text = ""
            for k, v in inference_results.items():
                if isinstance(v, dict):
                    t = v.get("type", k)
                    r = v.get("result", "")
                    inference_text += f"- {t}: {str(r)[:200]}\n"

            prompt = FLASH_SUMMARY_PROMPT.format(
                event_details=json.dumps(event_details, indent=2)[:800],
                inference_results=inference_text[:800],
            )

            summary = _call_gemini(settings.GEMINI_FLASH_MODEL, prompt, timeout=30)
            logger.info(f"[{product.uuid[:8]}] 摘要生成完成")
            return summary

        except Exception as e:
            logger.error(f"摘要生成失败 {product.uuid}: {e}")
            return None

    # ── 批量生成未摘要的成品摘要 ────────────────────────────

    def generate_pending_summaries(self, db: Session, limit: int = 50) -> int:
        """批量生成未生成摘要的成品"""
        products = (
            db.query(Product)
            .filter(Product.summary_generated == 0)
            .limit(limit)
            .all()
        )

        generated = 0
        for product in products:
            summary = self.generate_event_summary(product)
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            if summary:
                product.summary = summary
                product.summary_generated = 1
                product.summary_generated_at = now_ms
                generated += 1
            product.updated_at = now_ms

        db.commit()
        logger.info(f"批量摘要生成完成: {generated}/{len(products)}")
        return generated

    # ── 生成日报（Gemini Pro） ────────────────────────────

    def generate_daily_report(self, db: Session, report_date: str) -> Optional[DailyReport]:
        """
        生成指定日期的灾害日报。
        report_date: 'YYYY-MM-DD'
        """
        logger.info(f"开始生成日报: {report_date}")
        start_time = time.time()

        try:
            date_dt = datetime.strptime(report_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            logger.error(f"日期格式错误: {report_date}")
            return None

        start_ms = int(date_dt.timestamp() * 1000)
        end_ms = int((date_dt + timedelta(days=1)).timestamp() * 1000)

        # 优先查询当日成品
        products = (
            db.query(Product)
            .filter(
                Product.created_at >= start_ms,
                Product.created_at < end_ms,
            )
            .all()
        )

        # 回退：查询最近 7 天所有成品（不限 summary_generated，因为下面会补充生成）
        if not products:
            since_ms = int((date_dt - timedelta(days=7)).timestamp() * 1000)
            products = (
                db.query(Product)
                .filter(Product.created_at >= since_ms)
                .order_by(Product.created_at.desc())
                .limit(20)
                .all()
            )

        if not products:
            logger.warning(f"日期 {report_date} 无可用成品（最近 7 天也无数据）")
            return None

        # 确保每条成品都有摘要
        for product in products:
            if not product.summary:
                product.summary = self.generate_event_summary(product)
                if product.summary:
                    product.summary_generated = 1
                    product.summary_generated_at = int(datetime.now(timezone.utc).timestamp() * 1000)

        db.commit()

        # 统计信息
        category_stats: dict = {}
        severity_stats: dict = {}
        country_stats: dict = {}

        for p in products:
            if p.event_category:
                category_stats[p.event_category] = category_stats.get(p.event_category, 0) + 1
            if p.event_country:
                country_stats[p.event_country] = country_stats.get(p.event_country, 0) + 1
            event = db.query(Event).filter(Event.uuid == p.uuid).first()
            if event and event.severity:
                severity_stats[event.severity] = severity_stats.get(event.severity, 0) + 1

        # 构建摘要列表
        summaries = []
        for p in products[:20]:
            summaries.append(
                f"**{p.event_title or 'Unknown'}** ({p.event_country or 'N/A'}): "
                f"{(p.summary or 'No summary available.')[:300]}"
            )

        if not settings.GEMINI_API_KEY:
            report_content = self._generate_fallback_report(
                report_date, products, category_stats, severity_stats, country_stats
            )
        else:
            report_content = self._call_gemini_pro(
                report_date, summaries, category_stats, severity_stats, country_stats
            )

        generation_time = time.time() - start_time
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        existing = db.query(DailyReport).filter(DailyReport.report_date == report_date).first()
        if existing:
            existing.report_content = report_content
            existing.report_title = f"全球灾害监测日报 — {report_date}"
            existing.event_count = len(products)
            existing.category_stats = json.dumps(category_stats)
            existing.severity_stats = json.dumps(severity_stats)
            existing.country_stats = json.dumps(country_stats)
            existing.generated_at = now_ms
            existing.generation_time_seconds = generation_time
            daily_report = existing
        else:
            daily_report = DailyReport(
                report_date=report_date,
                report_content=report_content,
                report_title=f"全球灾害监测日报 — {report_date}",
                event_count=len(products),
                category_stats=json.dumps(category_stats),
                severity_stats=json.dumps(severity_stats),
                country_stats=json.dumps(country_stats),
                generated_at=now_ms,
                generated_by=settings.GEMINI_PRO_MODEL,
                generation_time_seconds=generation_time,
            )
            db.add(daily_report)

        db.commit()
        logger.info(f"日报生成完成: {report_date} ({generation_time:.1f}s, {len(products)} 事件)")
        return daily_report

    def _call_gemini_pro(
        self, date, summaries, category_stats, severity_stats, country_stats
    ) -> str:
        try:
            prompt = PRO_REPORT_PROMPT.format(
                date=date,
                total_count=len(summaries),
                event_summaries="\n\n".join(summaries),
                category_stats=json.dumps(category_stats, ensure_ascii=False),
                severity_stats=json.dumps(severity_stats, ensure_ascii=False),
                country_stats=json.dumps(country_stats, ensure_ascii=False),
            )
            return _call_gemini(settings.GEMINI_PRO_MODEL, prompt, timeout=120)
        except Exception as e:
            logger.error(f"Gemini Pro 调用失败: {e}")
            return self._generate_fallback_report(
                date, [], category_stats, severity_stats, country_stats
            )

    def _generate_fallback_report(
        self, date, products, category_stats, severity_stats, country_stats
    ) -> str:
        """Gemini 不可用时生成简单报告"""
        lines = [
            f"# 全球灾害监测日报 — {date}",
            "",
            "## 执行摘要",
            "",
            f"本日报涵盖 **{len(products)}** 个已分析的灾害事件。",
            "",
            "## 统计信息",
            "",
            "### 按灾害类型",
            "",
        ]
        for cat, cnt in sorted(category_stats.items(), key=lambda x: -x[1]):
            lines.append(f"- **{cat}**: {cnt} 件")

        lines += ["", "### 按严重程度", ""]
        for sev, cnt in sorted(severity_stats.items(), key=lambda x: -x[1]):
            lines.append(f"- **{sev}**: {cnt} 件")

        lines += ["", "### 按国家/地区", ""]
        for country, cnt in sorted(country_stats.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"- **{country}**: {cnt} 件")

        lines += ["", "---", f"*报告生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*"]
        return "\n".join(lines)
