"""
配置文件管理工具 - 读写 .env 和 config.json
支持运行时配置热更新（写文件 + 更新内存 settings 对象）
"""
import json
from pathlib import Path
from typing import Any

# 路径相对于 us-public-server/（即 uvicorn 的工作目录）
_ENV_PATH = Path(".env")
_CONFIG_PATH = Path("config.json")


# ── .env 读写 ─────────────────────────────────────────

def _get_env_path() -> Path:
    if _ENV_PATH.exists():
        return _ENV_PATH
    raise FileNotFoundError(f".env 文件不存在: {_ENV_PATH.resolve()}")


def read_env() -> dict:
    """读取 .env 文件为 dict（跳过注释行和空行）"""
    result = {}
    try:
        with open(_get_env_path(), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    result[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return result


def write_env_keys(updates: dict) -> bool:
    """批量更新 .env 中的若干 key，不存在则追加，保留注释和格式"""
    try:
        env_path = _get_env_path()
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        written = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            matched = False
            for key, value in updates.items():
                if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                    new_lines.append(f"{key}={value}\n")
                    written.add(key)
                    matched = True
                    break
            if not matched:
                new_lines.append(line)

        # 追加未找到的 key
        for key, value in updates.items():
            if key not in written:
                new_lines.append(f"{key}={value}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        from utils.logger import get_logger
        get_logger(__name__).error(f"写入 .env 失败: {e}")
        return False


# ── config.json 读写 ──────────────────────────────────

def _get_config_path() -> Path:
    if _CONFIG_PATH.exists():
        return _CONFIG_PATH
    alt = Path(__file__).parent.parent / "config.json"
    if alt.exists():
        return alt
    raise FileNotFoundError("config.json 不存在")


def read_config_json() -> dict:
    try:
        with open(_get_config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_config_json(data: dict) -> bool:
    try:
        with open(_get_config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        from utils.logger import get_logger
        get_logger(__name__).error(f"写入 config.json 失败: {e}")
        return False


def set_nested(obj: dict, path: list, value: Any):
    """按键路径列表设置嵌套字典的值，中间层不存在时自动创建"""
    for key in path[:-1]:
        obj = obj.setdefault(key, {})
    obj[path[-1]] = value


# ── 内存热更新 ─────────────────────────────────────────

def apply_to_settings(env_updates: dict):
    """将 env key→value 同步更新到内存 settings 对象，使其立即生效（无需重启）"""
    try:
        from config.settings import settings
        for env_key, value in env_updates.items():
            # env key 转 settings 属性名（全大写 → 驼峰有对应关系，直接按 env key 同名属性赋值）
            attr = env_key  # settings 属性和 env key 同名
            if hasattr(settings, attr):
                # 类型推断：如果原始属性是 int/float/bool 就做类型转换
                orig = getattr(settings, attr)
                if isinstance(orig, bool):
                    setattr(settings, attr, str(value).lower() in ("true", "1", "yes"))
                elif isinstance(orig, int):
                    try:
                        setattr(settings, attr, int(value))
                    except (ValueError, TypeError):
                        setattr(settings, attr, value)
                elif isinstance(orig, float):
                    try:
                        setattr(settings, attr, float(value))
                    except (ValueError, TypeError):
                        setattr(settings, attr, value)
                else:
                    setattr(settings, attr, value)
    except Exception as e:
        from utils.logger import get_logger
        get_logger(__name__).warning(f"内存热更新 settings 失败: {e}")
