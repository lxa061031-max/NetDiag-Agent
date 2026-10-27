"""生成仅供界面演示和自动化测试使用的模拟网络数据。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def generate_synthetic_network_data(
    sample_count: int = 240, seed: int = 20261026
) -> pd.DataFrame:
    """按固定随机种子生成正常样本，并注入少量同步异常。"""

    if sample_count < 20:
        raise ValueError("sample_count 至少为 20，才能生成正常与异常样本。")

    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2026-10-01 08:00:00", periods=sample_count, freq="min")
    latency = np.clip(rng.normal(25, 4, sample_count), 5, None)
    packet_loss = np.clip(rng.normal(0.25, 0.18, sample_count), 0, None)
    cpu_usage = np.clip(rng.normal(42, 8, sample_count), 5, 95)
    temperature = np.clip(rng.normal(46, 3, sample_count), 25, 80)

    anomaly_count = max(8, sample_count // 12)
    anomaly_indices = np.sort(rng.choice(sample_count, anomaly_count, replace=False))
    latency[anomaly_indices] += rng.uniform(65, 125, anomaly_count)
    packet_loss[anomaly_indices] += rng.uniform(5, 18, anomaly_count)
    cpu_usage[anomaly_indices] = np.clip(
        cpu_usage[anomaly_indices] + rng.uniform(30, 48, anomaly_count), 0, 100
    )
    temperature[anomaly_indices] += rng.uniform(8, 18, anomaly_count)

    labels = np.zeros(sample_count, dtype=int)
    labels[anomaly_indices] = 1
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "latency_ms": np.round(latency, 2),
            "packet_loss_pct": np.round(packet_loss, 2),
            "cpu_usage_pct": np.round(cpu_usage, 2),
            "temperature_c": np.round(temperature, 2),
            "anomaly_label": labels,
        }
    )


def save_synthetic_network_data(output_path: str | Path) -> Path:
    """生成数据并保存为 CSV。"""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generate_synthetic_network_data().to_csv(path, index=False)
    return path


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    saved_path = save_synthetic_network_data(
        project_root / "data" / "demo" / "synthetic_network.csv"
    )
    print(f"已生成模拟数据：{saved_path}")
