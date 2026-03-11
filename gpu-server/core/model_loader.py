"""
模型加载器
参考: Image-Analyse/single_gpu_inference_bk.py
"""
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class ModelLoader:
    """灾害识别模型加载器（HuggingFace AutoModel）"""

    def __init__(self, config):
        self.config = config
        self.model = None
        self.processor = None
        self.device = None

    def load_model(self):
        """加载模型和处理器到 GPU"""
        import torch
        from transformers import AutoProcessor, AutoModelForCausalLM

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"使用设备: {self.device}")

        model_path = self.config.MODEL_PATH
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"模型路径不存在: {model_path}\n"
                "请将模型文件放到 models/ 目录，或在 .env 中配置 MODEL_PATH"
            )

        logger.info(f"加载模型: {model_path}")
        model_cfg = self.config.MODEL_CONFIG

        precision = model_cfg.get("precision", "fp16")
        torch_dtype = torch.float16 if precision == "fp16" else torch.float32

        self.processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)

        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch_dtype,
            trust_remote_code=True,
            device_map="auto" if str(self.device) == "cuda" else None,
        )

        if str(self.device) != "cuda":
            self.model = self.model.to(self.device)

        self.model.eval()
        logger.info(f"模型加载完成，参数量: {self._count_params()}")

        # 预热
        warmup = model_cfg.get("warmup_iterations", 2)
        if warmup > 0:
            self._warmup(warmup)

    def _count_params(self) -> str:
        if self.model is None:
            return "N/A"
        total = sum(p.numel() for p in self.model.parameters())
        if total >= 1e9:
            return f"{total / 1e9:.1f}B"
        return f"{total / 1e6:.0f}M"

    def _warmup(self, iterations: int):
        """用随机图像预热模型，减少首次推理延迟"""
        import torch
        import numpy as np
        from PIL import Image as PILImage

        logger.info(f"模型预热 ({iterations} 次)...")
        dummy = PILImage.fromarray(
            np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
        )
        for _ in range(iterations):
            with torch.no_grad():
                inputs = self.processor(
                    images=dummy, text="Warmup", return_tensors="pt"
                ).to(self.device)
                _ = self.model.generate(**inputs, max_new_tokens=5)
        logger.info("预热完成")

    def is_loaded(self) -> bool:
        return self.model is not None and self.processor is not None
