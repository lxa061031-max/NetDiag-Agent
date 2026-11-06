# LocalNetDynamics 语义映射验证

- 输入：`LocalNetDynamics.csv`；54617 行、67 列。仅本地字段结构验证，不调用 API。
- 明确元数据：20 列；`label_` 标签：6 列；目标网络字段：14 列。
- 成功推测语义：14/14；高置信度且允许专业分析：13/14。
- Semantic Mapping Accuracy（语义和单位同时正确）：14/14 = 100.00%。
- Coverage（获得非空语义，不等于允许专业分析）：14/14 = 100.00%。
- High-Confidence Accuracy：13/13 = 100.00%。
- 目标字段错误高置信度：0；明确标签/元数据错误高置信度：0。

|字段|人工预期（语义 / 单位）|预测（语义 / 单位）|置信度|来源|专业分析|正确|
|---|---|---|---:|---|---|---|
|`rtt_avg_ms`|latency / ms|latency / ms|0.9|structured_pattern|是|是|
|`rtt_median_ms`|latency / ms|latency / ms|0.9|structured_pattern|是|是|
|`jitter_ms`|jitter / ms|jitter / ms|1.0|exact_alias|是|是|
|`packet_loss_pct`|packet_loss / %|packet_loss / %|1.0|exact_alias|是|是|
|`gateway_rtt_avg_ms`|latency / ms|latency / ms|0.9|structured_pattern|是|是|
|`gateway_jitter_ms`|jitter / ms|jitter / ms|0.9|structured_pattern|是|是|
|`gateway_packet_loss_pct`|packet_loss / %|packet_loss / %|0.9|structured_pattern|是|是|
|`wifi_rssi_dbm`|signal_strength / dBm|signal_strength / dBm|0.9|structured_pattern|是|是|
|`wifi_rx_mbps`|traffic_received / Mbps|traffic_received / Mbps|0.9|structured_pattern|是|是|
|`wifi_tx_mbps`|traffic_sent / Mbps|traffic_sent / Mbps|0.9|structured_pattern|是|是|
|`download_mbps`|throughput / Mbps|throughput / Mbps|0.9|structured_pattern|是|是|
|`upload_mbps`|throughput / Mbps|throughput / Mbps|0.9|structured_pattern|是|是|
|`speedtest_ping_ms`|latency / ms|latency / ms|0.9|structured_pattern|是|是|
|`lan_throughput_mbps`|throughput / Mbps|throughput / Mbps|0.6|structured_pattern|否|是|

待确认的未知网络候选（仅列事先人工选定的候选，不代表全部未知字段）：

`packets_sent`, `packets_received`, `tcp_connect_min_ms`, `tcp_connect_median_ms`, `dns_resolve_ms`, `dns_recursive_ms`, `http_ms`, `lan_retransmits`, `rtt_resolution_ms`

指标中的人工预期来自本次任务，未声称经过数据集官方字段字典确认；14个字段不是随机样本，不能推广为全数据集准确率。
空值字段即使字段名提供语义和单位，仍降为低置信度、需要确认；未知字段可进入通用分析。标签不参与指标分析。
原始CSV未修改；此报告不评估网络故障检测准确率。
