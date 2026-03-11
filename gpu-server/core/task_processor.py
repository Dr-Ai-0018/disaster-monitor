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


class TaskProcessor:
    """GPU 任务处理器"""

    def __init__(self, api_client, inference_engine):
        self.api = api_client
        self.engine = inference_engine
        self.temp_dir = Path(settings.STORAGE_CONFIG.get("temp_dir", "temp"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeat_interval = settings.HEARTBEAT_INTERVAL_SECONDS

    def process_task(self, task: Dict) -> bool:
        """
        处理单个任务完整流程：
        下载影像 → 推理 → 回传结果
        """
        task_uuid = task["uuid"]
        task_data = task.get("task_data", {})
        logger.info(f"── 开始处理任务: {task_uuid[:8]} ──")

        # 心跳辅助函数
        last_heartbeat = time.time()

        def heartbeat_if_needed():
            nonlocal last_heartbeat
            if time.time() - last_heartbeat >= self.heartbeat_interval:
                self.api.update_heartbeat(task_uuid)
                last_heartbeat = time.time()

        pre_path = self.temp_dir / f"{task_uuid}_pre.tif"
        post_path = self.temp_dir / f"{task_uuid}_post.tif"

        try:
            # ── 1. 下载影像 ──────────────────────────
            logger.info("步骤1: 下载灾前影像")
            if not self.api.download_image(task_data["pre_image_url"], str(pre_path)):
                raise RuntimeError("灾前影像下载失败")
            heartbeat_if_needed()

            logger.info("步骤2: 下载灾后影像")
            if not self.api.download_image(task_data["post_image_url"], str(post_path)):
                raise RuntimeError("灾后影像下载失败")
            heartbeat_if_needed()

            # ── 2. 推理 ───────────────────────────────
            logger.info("步骤3: 执行推理")
            start_ts = time.time()

            inference_result = self.engine.run_inference(
                str(pre_path),
                str(post_path),
                task_data.get("tasks", []),
            )

            processing_time = time.time() - start_ts
            heartbeat_if_needed()

            # ── 3. 回传结果 ──────────────────────────
            logger.info("步骤4: 提交结果")
            model_info = {
                "model_name": settings.MODEL_NAME,
                "model_version": settings.MODEL_VERSION,
                "worker_id": settings.WORKER_ID,
            }

            if not self.api.submit_result(task_uuid, inference_result, processing_time, model_info):
                raise RuntimeError("结果提交失败")

            logger.info(f"✅ 任务完成: {task_uuid[:8]} ({processing_time:.1f}s)")
            return True

        except Exception as e:
            err_detail = traceback.format_exc()
            logger.error(f"❌ 任务失败: {task_uuid[:8]} - {e}")
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
