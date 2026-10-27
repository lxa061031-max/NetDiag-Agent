"""基础异常检测的集中阈值配置。"""

DEFAULT_THRESHOLD_RULES: dict[str, dict[str, float]] = {
    "latency_ms": {"max": 80.0},
    "packet_loss_pct": {"max": 5.0},
    "cpu_usage_pct": {"max": 85.0},
    "temperature_c": {"max": 65.0},
}
