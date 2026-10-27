"""基础异常检测的集中阈值配置。"""

import math
from collections.abc import Mapping

DEFAULT_THRESHOLD_RULES: dict[str, dict[str, float]] = {
    "latency_ms": {"max": 80.0},
    "packet_loss_pct": {"max": 5.0},
    "cpu_usage_pct": {"max": 85.0},
    "temperature_c": {"max": 65.0},
}

DEFAULT_IQR_MULTIPLIER = 1.5


def detection_config(value=None):
    """构造独立配置副本并验证；不修改默认值或原始数据。"""
    if value is None:
        value = {}
    if not isinstance(value, Mapping) or set(value) - {"thresholds", "iqr_multiplier"}:
        raise ValueError("检测配置仅支持 thresholds 和 iqr_multiplier。")
    supplied = value.get("thresholds", {})
    if not isinstance(supplied, Mapping) or set(supplied) - set(DEFAULT_THRESHOLD_RULES):
        raise ValueError("检测阈值包含不支持的字段。")
    thresholds = {}
    for name, rule in DEFAULT_THRESHOLD_RULES.items():
        raw = supplied.get(name, rule["max"])
        if raw is None or isinstance(raw, bool):
            raise ValueError(f"{name} 阈值必须是有效数值。")
        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} 阈值必须是有效数值。") from exc
        if not math.isfinite(number) or (name.endswith("_pct") and not 0 <= number <= 100) or (name == "latency_ms" and number < 0) or (name == "temperature_c" and number < -273.15):
            raise ValueError(f"{name} 阈值超出允许范围。")
        thresholds[name] = number
    raw_multiplier = value.get("iqr_multiplier", DEFAULT_IQR_MULTIPLIER)
    if raw_multiplier is None or isinstance(raw_multiplier, bool):
        raise ValueError("IQR multiplier 必须是大于0的有限数值。")
    try:
        multiplier = float(raw_multiplier)
    except (TypeError, ValueError) as exc:
        raise ValueError("IQR multiplier 必须是大于0的有限数值。") from exc
    if not math.isfinite(multiplier) or multiplier <= 0:
        raise ValueError("IQR multiplier 必须是大于0的有限数值。")
    return {"thresholds": thresholds, "iqr_multiplier": multiplier}
