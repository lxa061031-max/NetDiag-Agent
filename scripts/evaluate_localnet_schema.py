"""复现 LocalNetDynamics 字段语义核验，不发送数据或调用 API。"""
from pathlib import Path

import pandas as pd

from src.data_processing.adapters import describe_dataset
from src.data_processing.schema import is_non_metric


ROOT = Path(__file__).resolve().parents[1]
# 人工评估范围来自任务中明确给出的 14 个字段，不视作数据集官方字段字典。
EXPECTED = {
    "rtt_avg_ms": ("latency", "ms"), "rtt_median_ms": ("latency", "ms"),
    "jitter_ms": ("jitter", "ms"), "packet_loss_pct": ("packet_loss", "%"),
    "gateway_rtt_avg_ms": ("latency", "ms"), "gateway_jitter_ms": ("jitter", "ms"),
    "gateway_packet_loss_pct": ("packet_loss", "%"), "wifi_rssi_dbm": ("signal_strength", "dBm"),
    "wifi_rx_mbps": ("traffic_received", "Mbps"), "wifi_tx_mbps": ("traffic_sent", "Mbps"),
    "download_mbps": ("throughput", "Mbps"), "upload_mbps": ("throughput", "Mbps"),
    "speedtest_ping_ms": ("latency", "ms"), "lan_throughput_mbps": ("throughput", "Mbps"),
}
NETWORK_CANDIDATES = (
    "packets_sent", "packets_received", "tcp_connect_min_ms", "tcp_connect_median_ms",
    "dns_resolve_ms", "dns_recursive_ms", "http_ms", "download_loaded_latency_ms",
    "upload_loaded_latency_ms", "lan_retransmits", "rtt_resolution_ms",
)


def main():
    path = ROOT / "LocalNetDynamics.csv"
    if not path.exists():
        path = ROOT / "LocalNetDynamics_semantic_test.csv"
    df = pd.read_csv(path, low_memory=False)
    adapter = describe_dataset(df)
    items = {item["source_column"]: item for item in adapter["schema_mapping"]}
    missing = set(EXPECTED) - set(items)
    if missing:
        raise ValueError(f"目标字段不存在：{sorted(missing)}")
    labels = [name for name in df.columns if name.casefold().startswith("label_")]
    metadata = [name for name in df.columns if is_non_metric(name) and name not in labels]
    unknown = [name for name in NETWORK_CANDIDATES if name in items and items[name]["canonical_name"] is None]
    correct = lambda name: (items[name]["canonical_name"], items[name]["unit"]) == EXPECTED[name]
    matched = [name for name in EXPECTED if items[name]["canonical_name"] is not None]
    high = [name for name in EXPECTED if items[name]["semantic_enabled"]]
    mistaken_high = [name for name in high if not correct(name)]
    unexpected = [name for name in labels + metadata if items[name]["semantic_enabled"]]
    total = len(EXPECTED)
    lines = ["# LocalNetDynamics 语义映射验证", "",
             f"- 输入：`{path.name}`；{len(df)} 行、{len(df.columns)} 列。仅本地字段结构验证，不调用 API。",
             f"- 明确元数据：{len(metadata)} 列；`label_` 标签：{len(labels)} 列；目标网络字段：{total} 列。",
             f"- 成功推测语义：{len(matched)}/{total}；高置信度且允许专业分析：{len(high)}/{total}。",
             f"- Semantic Mapping Accuracy（语义和单位同时正确）：{sum(correct(n) for n in EXPECTED)}/{total} = {sum(correct(n) for n in EXPECTED)/total:.2%}。",
             f"- Coverage（获得非空语义，不等于允许专业分析）：{len(matched)}/{total} = {len(matched)/total:.2%}。",
             f"- High-Confidence Accuracy：{sum(correct(n) for n in high)}/{len(high)} = {sum(correct(n) for n in high)/len(high):.2%}。" if high else "- High-Confidence Accuracy：无高置信度映射，不可计算。",
             f"- 目标字段错误高置信度：{len(mistaken_high)}；明确标签/元数据错误高置信度：{len(unexpected)}。",
             "", "|字段|人工预期（语义 / 单位）|预测（语义 / 单位）|置信度|来源|专业分析|正确|",
             "|---|---|---|---:|---|---|---|"]
    for name, expected in EXPECTED.items():
        item = items[name]
        lines.append(f"|`{name}`|{expected[0]} / {expected[1]}|{item['canonical_name']} / {item['unit']}|{item['confidence']:.1f}|{item['mapping_source']}|{'是' if item['semantic_enabled'] else '否'}|{'是' if correct(name) else '否'}|")
    lines += ["", "待确认的未知网络候选（仅列事先人工选定的候选，不代表全部未知字段）：", "",
              ", ".join(f"`{name}`" for name in unknown) or "无", "",
              "指标中的人工预期来自本次任务，未声称经过数据集官方字段字典确认；14个字段不是随机样本，不能推广为全数据集准确率。",
              "空值字段即使字段名提供语义和单位，仍降为低置信度、需要确认；未知字段可进入通用分析。标签不参与指标分析。",
              "原始CSV未修改；此报告不评估网络故障检测准确率。", ""]
    output = ROOT / "docs" / "experiments" / "localnet_semantic_mapping.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:10]))


if __name__ == "__main__":
    main()
