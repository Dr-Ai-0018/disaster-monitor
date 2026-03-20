"""
任务处理器 — 协调整个推理流程
"""
import time
import traceback
from pathlib import Path
from typing import Dict

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class PauseRequested(Exception):
    """任务收到暂停请求"""

    pass


class TaskProcessor:
    """GPU 任务处理器"""

    def __init__(self, api_client, inference_engine):
        self.api = api_client
        self.engine = inference_engine
        self.temp_dir = Path(settings.STORAGE_CONFIG.get("temp_dir", "temp"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeat_interval = settings.HEARTBEAT_INTERVAL_SECONDS

    def _build_step_details(self, tasks):
        return {
            "pipeline": [
                {"key": "download_pre", "label": "下载灾前影像", "status": "pending"},
                {"key": "download_post", "label": "下载灾后影像", "status": "pending"},
                {"key": "inference", "label": "执行推理任务", "status": "pending"},
                {"key": "submit", "label": "提交结果", "status": "pending"},
            ],
            "inference_tasks": [
                {
                    "task_id": task.get("task_id", index),
                    "type": task.get("type", "UNKNOWN"),
                    "label": task.get("prompt") or task.get("type", "UNKNOWN"),
                    "status": "pending",
                }
                for index, task in enumerate(tasks, start=1)
            ],
        }

    def _set_pipeline_status(self, step_details, key, status):
        for item in step_details.get("pipeline", []):
            if item.get("key") == key:
                item["status"] = status
                return

    def _set_inference_task_status(self, step_details, task_id, status, error=None):
        for item in step_details.get("inference_tasks", []):
            if item.get("task_id") == task_id:
                item["status"] = status
                if error:
                    item["error"] = error
                elif "error" in item:
                    item.pop("error", None)
                return

    def _raise_if_pause_requested(
        self,
        task_uuid: str,
        response,
        current_step: int,
        total_steps: int,
        step_details,
        message: str,
    ):
        if not response or not response.get("should_pause"):
            return

        logger.info(f"收到暂停指令: {task_uuid[:8]}")
        self.api.acknowledge_pause(
            task_uuid,
            message=message,
            current_step=current_step,
            total_steps=total_steps,
            step_details=step_details,
        )
        raise PauseRequested(message)

    def process_task(self, task: Dict) -> bool:
        """
        处理单个任务完整流程：
        下载影像 → 推理 → 回传结果
        """
        task_uuid = task["uuid"]
        task_data = task.get("task_data", {})
        inference_tasks = task_data.get("tasks", [])
        total_steps = max(len(inference_tasks) + 3, 4)
        step_details = self._build_step_details(inference_tasks)
        logger.info(f"── 开始处理任务: {task_uuid[:8]} ──")

        # 心跳辅助函数
        last_heartbeat = time.time()
        current_step = 0

        def heartbeat_if_needed():
            nonlocal last_heartbeat
            if time.time() - last_heartbeat >= self.heartbeat_interval:
                response = self.api.update_heartbeat(task_uuid)
                last_heartbeat = time.time()
                self._raise_if_pause_requested(
                    task_uuid,
                    response,
                    current_step,
                    total_steps,
                    step_details,
                    message="任务已在当前步骤边界暂停",
                )

        def sync_progress(stage, message, step_index, progress_percent=None):
            nonlocal last_heartbeat, current_step
            current_step = step_index
            response = self.api.update_progress(
                task_uuid,
                stage=stage,
                message=message,
                current_step=step_index,
                total_steps=total_steps,
                step_details=step_details,
                progress_percent=progress_percent,
            )
            last_heartbeat = time.time()
            self._raise_if_pause_requested(
                task_uuid,
                response,
                step_index,
                total_steps,
                step_details,
                message=f"任务已在「{message}」后暂停",
            )

        pre_path = self.temp_dir / f"{task_uuid}_pre.tif"
        post_path = self.temp_dir / f"{task_uuid}_post.tif"

        try:
            # ── 1. 下载影像 ──────────────────────────
            current_step = 1
            self._set_pipeline_status(step_details, "download_pre", "running")
            sync_progress("downloading_pre", "正在下载灾前影像", current_step)
            logger.info("步骤1: 下载灾前影像")
            if not self.api.download_image(task_data["pre_image_url"], str(pre_path)):
                raise RuntimeError("灾前影像下载失败")
            self._set_pipeline_status(step_details, "download_pre", "completed")
            heartbeat_if_needed()

            current_step = 2
            self._set_pipeline_status(step_details, "download_post", "running")
            sync_progress("downloading_post", "正在下载灾后影像", current_step)
            logger.info("步骤2: 下载灾后影像")
            if not self.api.download_image(task_data["post_image_url"], str(post_path)):
                raise RuntimeError("灾后影像下载失败")
            self._set_pipeline_status(step_details, "download_post", "completed")
            heartbeat_if_needed()

            # ── 2. 推理 ───────────────────────────────
            self._set_pipeline_status(step_details, "inference", "running")
            sync_progress("inferencing", "正在准备执行推理任务", 3)
            logger.info("步骤3: 执行推理")
            start_ts = time.time()

            def on_inference_progress(task, index, total, phase, error=None):
                nonlocal current_step
                task_id = task.get("task_id", index)
                task_type = task.get("type", "UNKNOWN")
                current = 2 + index
                current_step = current
                heartbeat_if_needed()
                status_map = {
                    "running": "running",
                    "completed": "completed",
                    "failed": "failed",
                    "skipped": "skipped",
                }
                self._set_inference_task_status(
                    step_details,
                    task_id,
                    status_map.get(phase, "pending"),
                    error=error,
                )
                phase_message = {
                    "running": f"正在执行推理子任务 {index}/{total}: {task_type}",
                    "completed": f"已完成推理子任务 {index}/{total}: {task_type}",
                    "failed": f"推理子任务失败 {index}/{total}: {task_type}",
                    "skipped": f"已跳过推理子任务 {index}/{total}: {task_type}",
                }.get(phase, f"推理子任务状态更新 {index}/{total}: {task_type}")
                sync_progress(
                    "inferencing",
                    phase_message,
                    current,
                )

            inference_result = self.engine.run_inference(
                str(pre_path),
                str(post_path),
                inference_tasks,
                progress_callback=on_inference_progress,
                pause_callback=heartbeat_if_needed,
            )

            processing_time = time.time() - start_ts
            self._set_pipeline_status(step_details, "inference", "completed")
            heartbeat_if_needed()

            # ── 3. 回传结果 ──────────────────────────
            current_step = total_steps
            self._set_pipeline_status(step_details, "submit", "running")
            sync_progress("submitting", "正在提交推理结果", current_step)
            logger.info("步骤4: 提交结果")
            model_info = {
                "model_name": settings.MODEL_NAME,
                "model_version": settings.MODEL_VERSION,
                "worker_id": settings.WORKER_ID,
            }

            if not self.api.submit_result(task_uuid, inference_result, processing_time, model_info):
                raise RuntimeError("结果提交失败")

            self._set_pipeline_status(step_details, "submit", "completed")
            logger.info(f"✅ 任务完成: {task_uuid[:8]} ({processing_time:.1f}s)")
            return True

        except PauseRequested as e:
            logger.info(f"⏸️ 任务暂停: {task_uuid[:8]} - {e}")
            return False
        except Exception as e:
            err_detail = traceback.format_exc()
            logger.error(f"❌ 任务失败: {task_uuid[:8]} - {e}")
            if current_step <= 1:
                self._set_pipeline_status(step_details, "download_pre", "failed")
            elif current_step == 2:
                self._set_pipeline_status(step_details, "download_post", "failed")
            elif current_step < total_steps:
                self._set_pipeline_status(step_details, "inference", "failed")
            else:
                self._set_pipeline_status(step_details, "submit", "failed")
            self.api.update_progress(
                task_uuid,
                stage="failed",
                message=f"任务失败: {e}",
                current_step=current_step,
                total_steps=total_steps,
                step_details=step_details,
                progress_percent=min(99, int((current_step / max(total_steps, 1)) * 100)),
            )
            self.api.report_failure(
                task_uuid,
                reason=str(e),
                error_details=err_detail[:2000],
                can_retry=True,
            )
            return False

        finally:
            self._cleanup(task_uuid)

    def _cleanup(self, task_uuid: str):
        """清理临时文件"""
        for suffix in ["_pre.tif", "_post.tif"]:
            p = self.temp_dir / f"{task_uuid}{suffix}"
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        logger.debug(f"临时文件已清理: {task_uuid[:8]}")
