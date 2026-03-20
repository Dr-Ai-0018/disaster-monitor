"""
推理引擎 — 执行 7 个灾害识别任务
参考: Image-Analyse/single_gpu_inference_bk.py
"""
import time
from typing import Dict, List, Any, Optional

from utils.logger import get_logger
from utils.image_processor import ImageProcessor

logger = get_logger(__name__)

# 任务类型 → prompt 前缀
TASK_PREFIX = {
    "IMG_CAP":     "[IMG_CAP]",
    "IMG_VQA":     "[IMG_VQA]",
    "IMG_CT":      "[IMG_CT]",
    "PIX_SEG":     "[PIX_SEG]",
    "PIX_CHG":     "[PIX_CHG]",
    "REG_DET_HBB": "[REG_DET_HBB]",
    "REG_VG":      "[REG_VG]",
}


class InferenceEngine:
    """灾害识别推理引擎"""

    def __init__(self, model, processor, config):
        self.model = model
        self.processor = processor
        self.config = config
        self.tasks_cfg = config.TASKS_CONFIG
        self.inference_cfg = config.INFERENCE_CONFIG
        self.max_image_size = config.MAX_IMAGE_SIZE

        import torch
        self.device = next(model.parameters()).device
        self.image_proc = ImageProcessor(max_size=self.max_image_size)

    # ── 主入口 ─────────────────────────────────────────

    def run_inference(
        self,
        pre_image_path: str,
        post_image_path: str,
        tasks: List[Dict],
        progress_callback=None,
        pause_callback=None,
    ) -> Dict[str, Any]:
        """
        执行全部推理任务。

        Args:
            pre_image_path: 灾前影像路径
            post_image_path: 灾后影像路径
            tasks: 任务列表（来自 task_data.tasks）

        Returns:
            { "task_1": {"type": ..., "result": ...}, ... }
        """
        logger.info(f"开始推理，共 {len(tasks)} 个任务")
        start = time.time()

        pre_img = self.image_proc.prepare_for_model(
            self.image_proc.load_image(pre_image_path)
        )
        post_img = self.image_proc.prepare_for_model(
            self.image_proc.load_image(post_image_path)
        )

        results: Dict[str, Any] = {}

        total_tasks = len(tasks)

        for index, task in enumerate(tasks, start=1):
            task_id = task.get("task_id", 0)
            task_type = task.get("type", "")
            prompt = task.get("prompt", "")
            key = f"task_{task_id}"

            if pause_callback:
                pause_callback()

            if progress_callback:
                progress_callback(task=task, index=index, total=total_tasks, phase="running")

            # 检查该任务是否启用
            if not self.tasks_cfg.get(task_type, {}).get("enabled", True):
                logger.info(f"任务 {task_id} ({task_type}) 已禁用，跳过")
                results[key] = {"type": task_type, "result": None, "skipped": True}
                if progress_callback:
                    progress_callback(task=task, index=index, total=total_tasks, phase="skipped")
                continue

            logger.info(f"执行任务 {task_id}: {task_type}")
            try:
                if task_type == "PIX_CHG":
                    result = self._run_change_detection(pre_img, post_img, prompt, task_type)
                else:
                    result = self._run_single(post_img, prompt, task_type)

                results[key] = {"type": task_type, "result": result}
                logger.info(f"任务 {task_id} 完成: {str(result)[:80]}")
                if progress_callback:
                    progress_callback(task=task, index=index, total=total_tasks, phase="completed")

            except Exception as e:
                logger.error(f"任务 {task_id} ({task_type}) 失败: {e}")
                results[key] = {"type": task_type, "result": None, "error": str(e)}
                if progress_callback:
                    progress_callback(
                        task=task,
                        index=index,
                        total=total_tasks,
                        phase="failed",
                        error=str(e),
                    )

        elapsed = time.time() - start
        logger.info(f"推理完成，耗时 {elapsed:.1f}s")
        return results

    # ── 单任务推理 ─────────────────────────────────────

    def _run_single(self, image, prompt: str, task_type: str) -> str:
        """单张影像推理（大多数任务）"""
        import torch

        prefix = TASK_PREFIX.get(task_type, "")
        full_prompt = f"<image>\n{prefix}\n{prompt}" if prefix else f"<image>\n{prompt}"
        max_tokens = self.tasks_cfg.get(task_type, {}).get("max_tokens", 300)

        inputs = self.processor(
            images=image,
            text=full_prompt,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=False,
                temperature=1.0,
            )

        decoded = self.processor.decode(outputs[0], skip_special_tokens=True)
        # 去掉 prompt 部分，只保留模型输出
        result = self._strip_prompt(decoded, full_prompt)
        return result.strip()

    # ── 变化检测任务 ───────────────────────────────────

    def _run_change_detection(self, pre_img, post_img, prompt: str, task_type: str) -> str:
        """
        变化检测：将灾前/灾后影像拼接后输入模型。
        如果模型支持多图输入则使用多图，否则水平拼接。
        """
        import torch
        from PIL import Image as PILImage

        prefix = TASK_PREFIX.get(task_type, "[PIX_CHG]")
        max_tokens = self.tasks_cfg.get(task_type, {}).get("max_tokens", 500)

        # 尝试多图输入
        try:
            full_prompt = f"<image><image>\n{prefix}\n{prompt}"
            inputs = self.processor(
                images=[pre_img, post_img],
                text=full_prompt,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)

            decoded = self.processor.decode(outputs[0], skip_special_tokens=True)
            return self._strip_prompt(decoded, full_prompt).strip()

        except Exception:
            # 降级：水平拼接灾前/灾后影像
            w1, h1 = pre_img.size
            w2, h2 = post_img.size
            target_h = max(h1, h2)
            combined = PILImage.new("RGB", (w1 + w2, target_h))
            combined.paste(pre_img, (0, 0))
            combined.paste(post_img, (w1, 0))

            return self._run_single(combined, prompt, task_type)

    # ── 工具 ───────────────────────────────────────────

    def _strip_prompt(self, decoded: str, prompt: str) -> str:
        """从解码结果中移除输入 prompt 部分"""
        # 模型通常会重复 prompt，取最后的新内容
        if prompt in decoded:
            return decoded[decoded.find(prompt) + len(prompt):]
        # 也可能有特殊分隔符
        for sep in ["ASSISTANT:", "Assistant:", "\nAssistant", "### Response:"]:
            if sep in decoded:
                return decoded.split(sep, 1)[-1]
        return decoded
