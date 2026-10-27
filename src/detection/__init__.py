"""基础异常检测模块。"""

from .anomaly_detector import detect_anomalies
from .config import DEFAULT_THRESHOLD_RULES

__all__ = ["DEFAULT_THRESHOLD_RULES", "detect_anomalies"]
