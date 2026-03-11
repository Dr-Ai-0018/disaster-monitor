"""
影像预处理工具
"""
from pathlib import Path
from typing import Optional
import numpy as np

try:
    from PIL import Image
    import rasterio
    from rasterio.enums import Resampling
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

from utils.logger import get_logger

logger = get_logger(__name__)


class ImageProcessor:
    """遥感影像预处理器"""

    def __init__(self, max_size: int = 1024):
        self.max_size = max_size

    def load_image(self, image_path: str) -> Optional["Image.Image"]:
        """
        加载影像（支持 GeoTIFF 和普通图像格式）。
        返回 PIL Image（RGB）。
        """
        path = Path(image_path)
        if not path.exists():
            logger.error(f"影像文件不存在: {image_path}")
            return None

        suffix = path.suffix.lower()

        # GeoTIFF 使用 rasterio 读取
        if suffix in (".tif", ".tiff") and HAS_RASTERIO:
            return self._load_geotiff(image_path)

        # 普通格式使用 PIL
        try:
            from PIL import Image as PILImage
            img = PILImage.open(image_path).convert("RGB")
            logger.debug(f"PIL 加载影像: {path.name} {img.size}")
            return img
        except Exception as e:
            logger.error(f"PIL 加载失败: {image_path} - {e}")
            return None

    def _load_geotiff(self, image_path: str) -> Optional["Image.Image"]:
        """用 rasterio 加载 GeoTIFF 并返回 PIL RGB 图像"""
        try:
            from PIL import Image as PILImage
            with rasterio.open(image_path) as src:
                # 读取前三个波段（RGB）
                count = min(src.count, 3)
                bands = []
                for i in range(1, count + 1):
                    band = src.read(i)
                    # 归一化到 0-255
                    band_min, band_max = band.min(), band.max()
                    if band_max > band_min:
                        band = ((band - band_min) / (band_max - band_min) * 255).astype(np.uint8)
                    else:
                        band = np.zeros_like(band, dtype=np.uint8)
                    bands.append(band)

                if len(bands) == 1:
                    bands = bands * 3  # 灰度 → RGB

                rgb = np.stack(bands, axis=-1)
                img = PILImage.fromarray(rgb, mode="RGB")
                logger.debug(f"rasterio 加载 GeoTIFF: {Path(image_path).name} {img.size}")
                return img
        except Exception as e:
            logger.error(f"rasterio 加载失败: {image_path} - {e}")
            return None

    def resize_keep_aspect(self, image: "Image.Image", max_size: Optional[int] = None) -> "Image.Image":
        """按最长边缩放，保持宽高比"""
        max_size = max_size or self.max_size
        w, h = image.size
        if max(w, h) <= max_size:
            return image
        scale = max_size / max(w, h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        from PIL import Image as PILImage
        return image.resize((new_w, new_h), PILImage.LANCZOS)

    def prepare_for_model(self, image: "Image.Image") -> "Image.Image":
        """缩放到模型输入尺寸"""
        return self.resize_keep_aspect(image, self.max_size)
