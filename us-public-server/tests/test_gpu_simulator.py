"""
GPU Server 模拟器 - 用于本地测试完整流程
模拟 GPU Worker 拉取任务、执行推理、回传结果
"""
import sys
import time
import json
import requests
from pathlib import Path
from typing import Dict, List

# 配置
API_BASE_URL = "http://127.0.0.1:2335"
API_TOKEN = "iWjBU3Dnbhrr9_QyXUP1jyD5mqfC0OA0tvBHRy-92m8"  # 需要先用 create_token.py 生成
WORKER_ID = "test-gpu-worker-1"

# 模拟推理结果
MOCK_INFERENCE_RESULT = {
    "task_1": {
        "type": "IMG_CAP",
        "result": "A flooded urban area with submerged buildings and debris-filled water. Residential structures are partially underwater, indicating severe flooding impact."
    },
    "task_2": {
        "type": "IMG_VQA",
        "result": "Yes, there is visible water damage and flooding throughout the area."
    },
    "task_3": {
        "type": "IMG_CT",
        "result": "Flood disaster in residential zone. Multiple buildings affected. Water level approximately 2-3 meters. Estimated impact: 50+ structures."
    },
    "task_4": {
        "type": "PIX_SEG",
        "result": "Segmentation mask: Water bodies (60%), Buildings (25%), Roads (10%), Vegetation (5%)"
    },
    "task_5": {
        "type": "PIX_CHG",
        "result": "Change detection: New flooded areas detected in 45% of the region. Significant water accumulation in previously dry zones."
    },
    "task_6": {
        "type": "REG_DET_HBB",
        "result": "Detected objects: 23 damaged buildings, 5 submerged vehicles, 3 debris clusters"
    },
    "task_7": {
        "type": "REG_VG",
        "result": "Visual grounding: Flooded residential area located at center-left of image, spanning approximately 500x400 pixels"
    }
}


class GPUSimulator:
    """GPU Worker 模拟器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Token": API_TOKEN,
            "Content-Type": "application/json",
        })

    def test_connection(self):
        """测试连接"""
        print("=" * 60)
        print("🔗 测试 API 连接...")
        try:
            resp = self.session.get(f"{API_BASE_URL}/health", timeout=5)
            resp.raise_for_status()
            print(f"✅ 连接成功: {resp.json()}")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print(f"   请确保服务器运行在 {API_BASE_URL}")
            return False

    def pull_tasks(self, limit: int = 3) -> List[Dict]:
        """拉取任务"""
        print("\n" + "=" * 60)
        print(f"📥 拉取任务 (limit={limit})...")
        try:
            resp = self.session.get(
                f"{API_BASE_URL}/api/tasks/pull",
                params={"worker_id": WORKER_ID, "limit": limit},
                timeout=10
            )
            resp.raise_for_status()
            tasks = resp.json().get("tasks", [])
            print(f"✅ 拉取到 {len(tasks)} 个任务")
            for i, task in enumerate(tasks, 1):
                print(f"   [{i}] UUID: {task['uuid'][:16]}... | Event: {task.get('event_id', 'N/A')}")
            return tasks
        except Exception as e:
            print(f"❌ 拉取失败: {e}")
            return []

    def update_heartbeat(self, task_uuid: str) -> bool:
        """更新心跳"""
        try:
            resp = self.session.put(
                f"{API_BASE_URL}/api/tasks/{task_uuid}/heartbeat",
                json={"worker_id": WORKER_ID},
                timeout=5
            )
            resp.raise_for_status()
            print(f"   💓 心跳更新: {task_uuid[:16]}...")
            return True
        except Exception as e:
            print(f"   ⚠️  心跳失败: {e}")
            return False

    def simulate_inference(self, task: Dict) -> Dict:
        """模拟推理过程"""
        task_uuid = task["uuid"]
        print(f"\n🤖 模拟推理: {task_uuid[:16]}...")
        
        # 模拟下载影像
        print("   [1/3] 下载灾前影像... (模拟)")
        time.sleep(0.5)
        
        # 更新心跳
        self.update_heartbeat(task_uuid)
        
        print("   [2/3] 下载灾后影像... (模拟)")
        time.sleep(0.5)
        
        # 模拟推理
        print("   [3/3] 执行 AI 推理... (模拟)")
        time.sleep(1.0)
        
        return MOCK_INFERENCE_RESULT

    def submit_result(self, task_uuid: str, inference_result: Dict, processing_time: float) -> bool:
        """提交结果"""
        print(f"\n📤 提交结果: {task_uuid[:16]}...")
        try:
            payload = {
                "worker_id": WORKER_ID,
                "status": "success",
                "inference_result": inference_result,
                "processing_time_seconds": processing_time,
                "model_info": {
                    "model_name": "disaster-recognition-v1-mock",
                    "model_version": "1.0.0-test",
                    "worker_id": WORKER_ID,
                }
            }
            resp = self.session.put(
                f"{API_BASE_URL}/api/tasks/{task_uuid}/result",
                json=payload,
                timeout=30
            )
            resp.raise_for_status()
            print(f"✅ 结果提交成功")
            return True
        except Exception as e:
            print(f"❌ 提交失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   响应: {e.response.text[:200]}")
            return False

    def process_task(self, task: Dict) -> bool:
        """处理单个任务"""
        task_uuid = task["uuid"]
        print("\n" + "─" * 60)
        print(f"开始处理任务: {task_uuid}")
        
        start_time = time.time()
        
        # 模拟推理
        inference_result = self.simulate_inference(task)
        
        processing_time = time.time() - start_time
        
        # 提交结果
        success = self.submit_result(task_uuid, inference_result, processing_time)
        
        if success:
            print(f"✅ 任务完成: {task_uuid[:16]}... ({processing_time:.1f}s)")
        else:
            print(f"❌ 任务失败: {task_uuid[:16]}...")
        
        return success

    def run_test_cycle(self):
        """运行一次完整测试循环"""
        print("\n" + "=" * 60)
        print("🚀 开始 GPU Worker 模拟测试")
        print("=" * 60)
        
        # 1. 测试连接
        if not self.test_connection():
            return False
        
        # 2. 拉取任务
        tasks = self.pull_tasks(limit=3)
        
        if not tasks:
            print("\n⚠️  暂无待处理任务")
            print("   提示: 请先运行以下步骤创建测试数据:")
            print("   1. 手动触发 RSOE 数据抓取")
            print("   2. 或通过 API 创建测试事件")
            return False
        
        # 3. 处理每个任务
        success_count = 0
        for i, task in enumerate(tasks, 1):
            print(f"\n处理任务 [{i}/{len(tasks)}]")
            if self.process_task(task):
                success_count += 1
            time.sleep(1)  # 任务间隔
        
        # 4. 总结
        print("\n" + "=" * 60)
        print(f"📊 测试完成: {success_count}/{len(tasks)} 成功")
        print("=" * 60)
        
        return success_count > 0


def main():
    print("""
╔════════════════════════════════════════════════════════════╗
║         GPU Server 模拟器 - 本地测试工具                    ║
╚════════════════════════════════════════════════════════════╝

配置:
  API 地址: {api}
  Worker ID: {worker}
  API Token: {token}

使用前请确保:
  1. 公网服务器已启动 (python main.py)
  2. 已创建 API Token (python database/create_token.py)
  3. 数据库中有待处理的任务

""".format(api=API_BASE_URL, worker=WORKER_ID, token=API_TOKEN[:20] + "..."))
    
    simulator = GPUSimulator()
    
    try:
        simulator.run_test_cycle()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
