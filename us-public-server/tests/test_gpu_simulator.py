"""
Latest Model Open API 测试器

保留原文件名以兼容历史文档，但测试目标已改为：
1. 直接调用 Latest Model Open API
2. 验证 submit / status / result 三段链路
3. 不再使用旧版内网 GPU Worker pull/heartbeat/result 流程
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import settings
from core.latest_model_client import LatestModelClient


DEFAULT_TASKS = [
    {
        "task_id": 1,
        "task": "IMG_CAP",
        "type": "IMG_CAP",
        "prompt": "[IMG_CAP] Describe this satellite image in detail, focusing on visible land features, structures, and any signs of damage or disaster impact.",
    },
    {
        "task_id": 2,
        "task": "IMG_VQA",
        "type": "IMG_VQA",
        "prompt": "[IMG_VQA] Is there visible disaster impact (damage, destruction, flooding, fire, or other hazards) in this image? Answer only: Yes or No.",
    },
]


class LatestModelApiTester:
    def __init__(self):
        self.client = LatestModelClient()

    def _resolve_image(self) -> str:
        cli_value = os.getenv("TEST_IMAGE_PATH", "").strip()
        if cli_value:
            return cli_value

        storage = ROOT / "storage" / "images"
        for path in storage.rglob("*"):
            if path.suffix.lower() in {".tif", ".tiff", ".png", ".jpg", ".jpeg"}:
                return str(path)
        raise FileNotFoundError("未找到测试影像。请设置 TEST_IMAGE_PATH 环境变量。")

    def run(self) -> int:
        print("=" * 72)
        print("Latest Model Open API 测试")
        print("=" * 72)
        print(f"Endpoint: {settings.LATEST_MODEL_ENDPOINT}")
        print(f"Configured: {self.client.is_configured()}")

        if not self.client.is_configured():
            print("❌ LATEST_MODEL_ENDPOINT / LATEST_MODEL_API_KEY 未配置")
            return 1

        image_path = self._resolve_image()
        print(f"Image: {image_path}")

        try:
            submit = self.client.submit_tasks(image_path, DEFAULT_TASKS)
            print("\n[1] 提交成功")
            print(json.dumps(submit, ensure_ascii=False, indent=2)[:1200])

            job_id = submit.get("job_id")
            if not job_id:
                print("❌ 返回里没有 job_id")
                return 2

            print(f"\n[2] 轮询状态 job_id={job_id}")
            last_status = None
            for _ in range(min(self.client.max_polls, 10)):
                payload = self.client.get_job_status(job_id)
                status = str(payload.get("status") or "").lower()
                if status != last_status:
                    print(f"  status={status} payload={json.dumps(payload, ensure_ascii=False)[:400]}")
                    last_status = status
                if status == "succeeded":
                    break
                if status == "failed":
                    print("❌ 远端任务失败")
                    print(json.dumps(payload, ensure_ascii=False, indent=2)[:1200])
                    return 3
                time.sleep(self.client.poll_interval)

            result = self.client.get_job_result(job_id)
            print("\n[3] 获取结果成功")
            print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
            print("\n✅ Latest Model Open API 链路正常")
            return 0
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            return 9


if __name__ == "__main__":
    raise SystemExit(LatestModelApiTester().run())
