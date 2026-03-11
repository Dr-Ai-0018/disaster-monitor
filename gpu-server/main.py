"""
GPU 服务器主程序 — 轮询任务并推理
"""
import sys
import time
import signal
import shutil
from pathlib import Path

from config.settings import settings
from utils.logger import setup_logger, get_logger

setup_logger(log_file=settings.LOG_FILE, level=settings.LOG_LEVEL)
logger = get_logger(__name__)


class GPUWorker:
    """GPU Worker 主控"""

    def __init__(self):
        self.running = True
        self.api_client = None
        self.inference_engine = None
        self.task_processor = None

        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

    def _on_signal(self, signum, frame):
        logger.info(f"收到信号 {signum}，准备退出...")
        self.running = False

    # ── 初始化 ─────────────────────────────────────────

    def initialize(self):
        logger.info("=" * 60)
        logger.info(f"  GPU Worker 启动: {settings.WORKER_ID}")
        logger.info(f"  API 地址: {settings.API_BASE_URL}")
        logger.info(f"  模型路径: {settings.MODEL_PATH}")
        logger.info("=" * 60)

        # 验证配置
        settings.validate()

        # 确保目录存在
        Path(settings.TEMP_DIR).mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        Path("cache").mkdir(exist_ok=True)

        # 初始化 API 客户端
        logger.info("初始化 API 客户端...")
        from core.api_client import DisasterAPIClient
        self.api_client = DisasterAPIClient()

        # 测试连接
        if not self.api_client.test_connection():
            raise ConnectionError(
                f"无法连接到公网服务器: {settings.API_BASE_URL}\n"
                "请检查 API_BASE_URL 和网络连接"
            )

        # 加载模型
        logger.info("加载推理模型...")
        from core.model_loader import ModelLoader
        loader = ModelLoader(settings)
        loader.load_model()

        # 初始化推理引擎
        logger.info("初始化推理引擎...")
        from core.inference_engine import InferenceEngine
        self.inference_engine = InferenceEngine(
            model=loader.model,
            processor=loader.processor,
            config=settings,
        )

        # 初始化任务处理器
        logger.info("初始化任务处理器...")
        from core.task_processor import TaskProcessor
        self.task_processor = TaskProcessor(self.api_client, self.inference_engine)

        logger.info("✅ 初始化完成")

    # ── 主循环 ─────────────────────────────────────────

    def run(self):
        poll_interval = settings.POLL_INTERVAL_SECONDS
        max_per_pull = settings.MAX_TASKS_PER_PULL

        logger.info(f"Worker 运行中，轮询间隔: {poll_interval}s，每次最多: {max_per_pull} 任务")

        while self.running:
            try:
                logger.info("\n" + "─" * 50)
                logger.info("轮询任务...")

                tasks = self.api_client.pull_tasks(limit=max_per_pull)

                if not tasks:
                    logger.info("暂无待处理任务")
                else:
                    logger.info(f"获取到 {len(tasks)} 个任务")
                    for i, task in enumerate(tasks, 1):
                        if not self.running:
                            break
                        logger.info(f"处理任务 [{i}/{len(tasks)}]")
                        self.task_processor.process_task(task)

                if self.running:
                    logger.info(f"等待 {poll_interval}s 后下次轮询...")
                    # 分段等待，支持快速响应退出信号
                    for _ in range(poll_interval):
                        if not self.running:
                            break
                        time.sleep(1)

            except KeyboardInterrupt:
                logger.info("收到中断，退出...")
                break
            except Exception as e:
                logger.error(f"主循环异常: {e}", exc_info=True)
                logger.info("等待 60s 后重试...")
                time.sleep(60)

        logger.info("Worker 已停止")

    # ── 清理 ───────────────────────────────────────────

    def cleanup(self):
        logger.info("清理资源...")
        temp = Path(settings.TEMP_DIR)
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
            temp.mkdir()
        logger.info("清理完成")


# ── 入口 ───────────────────────────────────────────────

def main():
    worker = GPUWorker()
    try:
        worker.initialize()
        worker.run()
    except Exception as e:
        logger.error(f"Worker 启动失败: {e}", exc_info=True)
        sys.exit(1)
    finally:
        worker.cleanup()


if __name__ == "__main__":
    main()
