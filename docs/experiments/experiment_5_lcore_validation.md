# 实验5：LCORE-D V2 R1跨结构验证

## 数据来源与标签核实

[官方发布页](https://data.mendeley.com/datasets/77sztrg5ks/2)，DOI：10.17632/77sztrg5ks.2。Akanksha singh、Ratneshwer Gupta，2025-12-17，CC BY 4.0。
这是公开GNS3仿真ISP监控数据，不是校园生产网数据。
官方SHA-256校验通过：`e2382475949174506bff1bdb28b80b67f5208896fdaa0b43e9e64000d06f3b33`；实际24240行、42列，原生数值dtype共39列。
class分布：`{'H': 23811, 'F': 429}`。**标签语义尚未由官方说明确认**。官方metadata、根文件及Fault Log未提供H/F明确映射，因此不计算TP/FP/TN/FN、Precision/Recall/F1。

## 适配与字段

详见 [完整字段表](lcore_r1_schema.md)。适配器仅描述字段角色、可分析指标及不确定性，不重命名原列或换算单位。
选择8个ICMP与接口收发量字段，不使用时间、class、状态或拓扑作为统计检测特征。

## 原始量纲统计

| 字段 | count | mean | median | std | min | max | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ICMP loss | 24240 | 9.42587 | 0 | 28.5542 | -1 | 100 | 100 |
| ICMP response time | 24240 | 0.0351131 | 0.0268 | 0.0775515 | -1 | 0.996 | 0.0496 |
| U_ Bits_ received | 24240 | 2.84676e+06 | 3.09161e+06 | 1.26912e+06 | -1 | 6.25118e+06 | 4.492e+06 |
| U_ Bits_ sent | 24240 | 45213.8 | 43709 | 18249.4 | -1 | 296656 | 59488.8 |
| B1_Bits_ received | 24240 | 50869 | 45320 | 22046.6 | -1 | 393584 | 78152.1 |
| B1_Bits_ sent | 24240 | 903725 | 1.01989e+06 | 274932 | -1 | 1.2837e+06 | 1.12962e+06 |
| P1_ Bits_ received | 24240 | 9339.74 | 4345 | 12687.7 | -1 | 193752 | 42288 |
| P1_Bits _sent | 24240 | 177699 | 5803 | 531374 | -1 | 3.72786e+06 | 1.81987e+06 |

## 统计异常检测

复用现有detect_anomalies，仅传入空固定阈值规则并启用默认1.5倍IQR。未调参。任一指标触发视为异常行。
异常行：9466；比例：39.0512%；指标级异常记录：21473。统计异常不等于已确认故障。

| 字段 | 异常记录数 |
|---|---:|
| B1_Bits_ sent | 4465 |
| B1_Bits_ received | 3929 |
| U_ Bits_ sent | 3693 |
| P1_Bits _sent | 3435 |
| ICMP response time | 3307 |
| P1_ Bits_ received | 2644 |
| ICMP loss | 0 |
| U_ Bits_ received | 0 |

IQR为0而被现有算法跳过的字段：`['ICMP loss']`。这些字段的0条统计异常不代表没有网络问题，本阶段未修改既有算法。

示例仅取前8条，不代表全量分布：

```json
[
  {
    "row_index": 0,
    "timestamp": 1760264160,
    "metric": "U_ Bits_ sent",
    "value": -1.0,
    "trigger_rule": "IQR 下界",
    "explanation": "低于 IQR 下界 33022.88，差值 33023.88"
  },
  {
    "row_index": 0,
    "timestamp": 1760264160,
    "metric": "B1_Bits_ received",
    "value": -1.0,
    "trigger_rule": "IQR 下界",
    "explanation": "低于 IQR 下界 27667.50，差值 27668.50"
  },
  {
    "row_index": 0,
    "timestamp": 1760264160,
    "metric": "B1_Bits_ sent",
    "value": -1.0,
    "trigger_rule": "IQR 下界",
    "explanation": "低于 IQR 下界 678125.00，差值 678126.00"
  },
  {
    "row_index": 1,
    "timestamp": 1760264220,
    "metric": "ICMP response time",
    "value": 0.0,
    "trigger_rule": "IQR 下界",
    "explanation": "低于 IQR 下界 0.00，差值 0.00"
  },
  {
    "row_index": 1,
    "timestamp": 1760264220,
    "metric": "U_ Bits_ sent",
    "value": -1.0,
    "trigger_rule": "IQR 下界",
    "explanation": "低于 IQR 下界 33022.88，差值 33023.88"
  },
  {
    "row_index": 1,
    "timestamp": 1760264220,
    "metric": "B1_Bits_ received",
    "value": -1.0,
    "trigger_rule": "IQR 下界",
    "explanation": "低于 IQR 下界 27667.50，差值 27668.50"
  },
  {
    "row_index": 1,
    "timestamp": 1760264220,
    "metric": "B1_Bits_ sent",
    "value": -1.0,
    "trigger_rule": "IQR 下界",
    "explanation": "低于 IQR 下界 678125.00，差值 678126.00"
  },
  {
    "row_index": 2,
    "timestamp": 1760264280,
    "metric": "U_ Bits_ sent",
    "value": -1.0,
    "trigger_rule": "IQR 下界",
    "explanation": "低于 IQR 下界 33022.88，差值 33023.88"
  }
]
```

## Agent任务E与公开证据链

DeepSeek真实API首次执行；不重试、不发送完整CSV，模型仅接收数据描述、受限工具摘要与最多20条示例。
用户任务：请分析当前LCORE-D R1数据集，概括主要网络指标，识别统计异常，并说明当前证据能够确认什么、不能确认什么。若需要参考网络故障知识，请检索相关来源。
状态：success；开始时间：2026-10-28T01:00:27.409435+08:00。
原始记录：`real_agent_records/stage_5d/task_E.json`。

| 顺序 | 工具 | 来源 | 状态 |
|---|---|---|---|
| 1 | analyze_network_metrics | llm | ok |
| 2 | detect_anomalies | llm | ok |
| 3 | search_fault_knowledge | requirement_guard | ok |

### 模型原始报告

## 数据分析摘要
[实际检测结果] 数据集 LCORE-D V2 R1-compatible schema 共 24240 行、42 字段（GNS3 仿真 ISP 监控数据，非校园生产网）。对 8 个分析字段统计：ICMP loss 均值 9.43、中位数 0、P95 为 100、最大值 100；ICMP response time 均值 0.0351、中位数 0.0268、P95 为 0.0496、最大值 0.996。接口收发量中，U_ Bits_ received 均值 2846755（P95 4491998），U_ Bits_ sent 均值 45214；B1_Bits_ sent 均值 903725；P1_ Bits_ received 均值 9340，P1_Bits _sent 均值 177699。各字段最小值均为 -1.0，编码含义未确认，未换算单位。

## 检测到的异常
[实际检测结果] IQR（倍数 1.5）检测：异常记录 21473 条，涉及行 9466 行，明细被截断（is_truncated=true），仅返回前 20 条样本。样本集中在时间戳 1760264160–1760264880 附近，触发“IQR 下界”的主要是 U_ Bits_ sent、B1_Bits_ received、B1_Bits_ sent 取值为 -1.0 的记录，以及若干 ICMP response time 为 0.0 的记录。ICMP loss 因 IQR 为 0 被跳过，这不代表健康。这些是统计离群，不等于故障。

## 相关数据证据
[实际检测结果] 异常来源与分析口径：分析字段仅限 ICMP 丢包/响应与 U/B1/P1 三接口收发量，未使用标签、时间、状态编码或拓扑字段。异常样本中的 -1.0 与统计最小值一致，提示缺失/占位编码可能主导了下界触发。
[参考知识] RFC 2330（IP 性能指标框架）指出：须先确认指标定义、单位、方向和采样周期，并检查缺失值、时间连续性与测量端资源，数据质量不足时只能提出排查方向。RFC 7679（单向时延指标）指出：单一时延指标不能判断问题位于链路、设备还是端点。

## 可能的故障原因
[模型推测] 大量 -1 占位值被计入统计，可能使 IQR 下界偏移并放大异常计数；ICMP 响应时间为 0 与丢包偏高的组合，可能反映测量端或路径中断时段，也可能仅是记录缺失。上述均为基于统计形态的推测，工具不验证因果。

## 建议的排查步骤
1. [实际检测结果+参考知识] 先按 RFC 2330 核对字段定义、单位、采样周期，明确 -1 编码，并重做剔除占位值后的 IQR 统计。
2. 取异常时段前后窗口，比对同接口历史基线（参考 RFC 7679 的分时段基线比对方法）。
3. 补充链路利用率、接口队列/错误计数、丢包与错误计数、设备日志与拓扑路径信息，分跳定位。
4. 对 9466 行样本做时间分布核查，区分持续性事件与零散离群。

## 无法确定的结论及其原因
[实际检测结果] 当前工具不能验证因果，无法确认根因，也无法确认是否存在真实网络故障。原因：异常明细被截断，样本时间范围不代表全量分布；-1 编码、单位、时区未确认；H/F 语义无官方映射，未计算标签指标；知识库仅提供方法论参考，未匹配到针对该数据集的具体故障条目。建议由网络运维人员结合上述补充数据人工复核。

### 结构化公开证据

```json
{
  "observations": [
    {
      "source_tool_order": 1,
      "facts": {
        "ICMP loss": {
          "count": 24240,
          "mean": 9.425866336630362,
          "min": -1.0,
          "max": 100.0,
          "std": 28.554164259667687,
          "median": 0.0,
          "p95": 100.0
        },
        "ICMP response time": {
          "count": 24240,
          "mean": 0.035113114684405936,
          "min": -1.0,
          "max": 0.996,
          "std": 0.07755151385953173,
          "median": 0.0268,
          "p95": 0.0496
        },
        "U_ Bits_ received": {
          "count": 24240,
          "mean": 2846755.1574257426,
          "min": -1.0,
          "max": 6251176.0,
          "std": 1269119.7503131158,
          "median": 3091610.5,
          "p95": 4491998.1
        },
        "U_ Bits_ sent": {
          "count": 24240,
          "mean": 45213.807590759076,
          "min": -1.0,
          "max": 296656.0,
          "std": 18249.367528192146,
          "median": 43709.0,
          "p95": 59488.79999999999
        },
        "B1_Bits_ received": {
          "count": 24240,
          "mean": 50869.03469471947,
          "min": -1.0,
          "max": 393584.0,
          "std": 22046.56544836905,
          "median": 45320.0,
          "p95": 78152.15
        },
        "B1_Bits_ sent": {
          "count": 24240,
          "mean": 903725.3278052806,
          "min": -1.0,
          "max": 1283704.0,
          "std": 274931.566405283,
          "median": 1019889.5,
          "p95": 1129624.4
        },
        "P1_ Bits_ received": {
          "count": 24240,
          "mean": 9339.739727722772,
          "min": -1.0,
          "max": 193752.0,
          "std": 12687.741228593979,
          "median": 4345.0,
          "p95": 42288.0
        },
        "P1_Bits _sent": {
          "count": 24240,
          "mean": 177698.8056930693,
          "min": -1.0,
          "max": 3727864.0,
          "std": 531374.2291630334,
          "median": 5803.0,
          "p95": 1819867.7999999984
        }
      }
    },
    {
      "source_tool_order": 2,
      "facts": {
        "anomaly_count": 21473,
        "anomalous_row_count": 9466
      }
    }
  ],
  "tool_evidence": [
    {
      "tool": "analyze_network_metrics",
      "order": 1,
      "selection_origin": "llm",
      "result": {
        "metrics": [
          "ICMP loss",
          "ICMP response time",
          "U_ Bits_ received",
          "U_ Bits_ sent",
          "B1_Bits_ received",
          "B1_Bits_ sent",
          "P1_ Bits_ received",
          "P1_Bits _sent"
        ],
        "statistics": {
          "ICMP loss": {
            "count": 24240,
            "mean": 9.425866336630362,
            "min": -1.0,
            "max": 100.0,
            "std": 28.554164259667687,
            "median": 0.0,
            "p95": 100.0
          },
          "ICMP response time": {
            "count": 24240,
            "mean": 0.035113114684405936,
            "min": -1.0,
            "max": 0.996,
            "std": 0.07755151385953173,
            "median": 0.0268,
            "p95": 0.0496
          },
          "U_ Bits_ received": {
            "count": 24240,
            "mean": 2846755.1574257426,
            "min": -1.0,
            "max": 6251176.0,
            "std": 1269119.7503131158,
            "median": 3091610.5,
            "p95": 4491998.1
          },
          "U_ Bits_ sent": {
            "count": 24240,
            "mean": 45213.807590759076,
            "min": -1.0,
            "max": 296656.0,
            "std": 18249.367528192146,
            "median": 43709.0,
            "p95": 59488.79999999999
          },
          "B1_Bits_ received": {
            "count": 24240,
            "mean": 50869.03469471947,
            "min": -1.0,
            "max": 393584.0,
            "std": 22046.56544836905,
            "median": 45320.0,
            "p95": 78152.15
          },
          "B1_Bits_ sent": {
            "count": 24240,
            "mean": 903725.3278052806,
            "min": -1.0,
            "max": 1283704.0,
            "std": 274931.566405283,
            "median": 1019889.5,
            "p95": 1129624.4
          },
          "P1_ Bits_ received": {
            "count": 24240,
            "mean": 9339.739727722772,
            "min": -1.0,
            "max": 193752.0,
            "std": 12687.741228593979,
            "median": 4345.0,
            "p95": 42288.0
          },
          "P1_Bits _sent": {
            "count": 24240,
            "mean": 177698.8056930693,
            "min": -1.0,
            "max": 3727864.0,
            "std": 531374.2291630334,
            "median": 5803.0,
            "p95": 1819867.7999999984
          }
        }
      }
    },
    {
      "tool": "detect_anomalies",
      "order": 2,
      "selection_origin": "llm",
      "result": {
        "anomaly_count": 21473,
        "anomalous_row_count": 9466,
        "analyzed_metrics": [
          "ICMP loss",
          "ICMP response time",
          "U_ Bits_ received",
          "U_ Bits_ sent",
          "B1_Bits_ received",
          "B1_Bits_ sent",
          "P1_ Bits_ received",
          "P1_Bits _sent"
        ],
        "is_truncated": true,
        "method": "IQR only; multiplier=1.5",
        "interpretation": "统计异常不等于已确认故障；原值保留，单位/-1编码和H/F语义未确认。IQR为0时现有算法跳过该字段，不表示健康。",
        "skipped_zero_iqr_metrics": [
          "ICMP loss"
        ]
      }
    }
  ],
  "knowledge_evidence": [
    {
      "id": "latency-high",
      "title": "网络时延升高",
      "source": {
        "name": "RFC 7679: A One-Way Delay Metric for IPPM",
        "url": "https://www.rfc-editor.org/rfc/rfc7679.html",
        "verified": true
      },
      "limitations": "单一时延指标不能确定问题位于链路、设备还是端点。",
      "tool_order": 3,
      "detection_orders": [
        2
      ],
      "query": "时延 监控数据 U_ Bits_ sent B1_Bits_ received B1_Bits_ sent ICMP response time",
      "selection_origin": "requirement_guard"
    },
    {
      "id": "measurement-data-insufficient",
      "title": "监控数据异常或证据不足",
      "source": {
        "name": "RFC 2330: Framework for IP Performance Metrics",
        "url": "https://www.rfc-editor.org/rfc/rfc2330.html",
        "verified": true
      },
      "limitations": "数据质量不足时只能提出排查方向，不能确认故障根因。",
      "tool_order": 3,
      "detection_orders": [
        2
      ],
      "query": "时延 监控数据 U_ Bits_ sent B1_Bits_ received B1_Bits_ sent ICMP response time",
      "selection_origin": "requirement_guard"
    }
  ],
  "inferences": [
    {
      "type": "model_inference",
      "text": "大量 -1 占位值被计入统计，可能使 IQR 下界偏移并放大异常计数；ICMP 响应时间为 0 与丢包偏高的组合，可能反映测量端或路径中断时段，也可能仅是记录缺失。上述均为基于统计形态的推测，工具不验证因果。"
    }
  ],
  "uncertainties": [
    "当前工具不验证故障因果，无法确认根因；需要异常时间对应的链路利用率、接口队列/错误计数、设备日志和拓扑信息，由人工复核。",
    {
      "type": "model_statement",
      "text": "[实际检测结果] 当前工具不能验证因果，无法确认根因，也无法确认是否存在真实网络故障。原因：异常明细被截断，样本时间范围不代表全量分布；-1 编码、单位、时区未确认；H/F 语义无官方映射，未计算标签指标；知识库仅提供方法论参考，未匹配到针对该数据集的具体故障条目。建议由网络运维人员结合上述补充数据人工复核。"
    },
    "LCORE的H/F官方对应含义、单位、时间单位/时区和-1编码未确认；统计偏离不等于已确认故障。"
  ],
  "dataset_adapter": {
    "source_type": "lcore_r1",
    "dataset_name": "LCORE-D V2 R1-compatible schema",
    "row_count": 24240,
    "numeric_columns": [
      "ICMP loss",
      "ICMP response time",
      "U_ Bits_ received",
      "U_ Bits_ sent",
      "U_Inbound_ packets_ discarded",
      "U_ Inbound_ packets_ with _errors",
      "U_Outbound_ packets_ with_ errors",
      "U_Outbound_ packets_ discarded",
      "U_ Speed",
      "B1_Bits_ received",
      "B1_Bits_ sent",
      "B1_ Inbound_ packets_ discarded",
      "B1_Inbound_ packets_ with_ errors",
      "B1_Outbound_ packets_ with_ errors",
      "B1_ Outbound_ packets_ discarded",
      "B1_Speed",
      "P1_ Bits_ received",
      "P1_Bits _sent",
      "P1_ Inbound_ packets_ discarded",
      "P1_Inbound _packets_ with_ errors",
      "P1_ Outbound_ packets_ discarded",
      "P1_ Outbound _packets_ with_ errors",
      "P1_Speed",
      "Uptime (network)",
      "Hop_to_server",
      "Hop_to_core",
      "downstream_dependents"
    ],
    "categorical_columns": [
      "U_ Duplex_ status",
      "U_Interface_ type",
      "U_ Operational_ status",
      "B1_ Duplex _status",
      "B1_ Interface_ type",
      "B1_Operational_ status",
      "P1_ Duplex_ status",
      "P1_ Interface_ type",
      "P1_Operational _status",
      "SNMP agent availability",
      "Device_name",
      "path_up"
    ],
    "timestamp_column": "timestamp",
    "label_column": "class",
    "metric_mapping": {
      "ICMP loss": "icmp_loss",
      "ICMP response time": "icmp_response_time",
      "U_ Bits_ received": "interface_u_receive",
      "U_ Bits_ sent": "interface_u_send",
      "B1_Bits_ received": "interface_b1_receive",
      "B1_Bits_ sent": "interface_b1_send",
      "P1_ Bits_ received": "interface_p1_receive",
      "P1_Bits _sent": "interface_p1_send"
    },
    "analysis_columns": [
      "ICMP loss",
      "ICMP response time",
      "U_ Bits_ received",
      "U_ Bits_ sent",
      "B1_Bits_ received",
      "B1_Bits_ sent",
      "P1_ Bits_ received",
      "P1_Bits _sent"
    ],
    "unsupported_columns": [
      "ICMP ping"
    ],
    "metadata": {
      "label_semantics_verified": false,
      "label_meanings": {},
      "label_semantics_note": "标签语义尚未由官方说明确认",
      "source_url": "https://data.mendeley.com/datasets/77sztrg5ks/2",
      "source_description": "GNS3仿真ISP网络公开监控数据，不是校园生产网数据",
      "units_and_timestamp_timezone": "未由官方字段字典确认；不换算单位",
      "negative_values": "保留负数原值；-1编码含义未确认，可能影响统计和IQR",
      "selection_basis": "优先ICMP丢包/响应及三个接口收发量；不使用标签、时间、状态编码或拓扑字段作为检测特征。"
    }
  },
  "task": {
    "input": "请分析当前LCORE-D R1数据集，概括主要网络指标，识别统计异常，并说明当前证据能够确认什么、不能确认什么。若需要参考网络故障知识，请检索相关来源。",
    "requirements": {
      "intents": [
        "metrics",
        "anomaly",
        "diagnostic"
      ],
      "required_tools": [
        "analyze_network_metrics",
        "detect_anomalies",
        "search_fault_knowledge"
      ],
      "knowledge_required": true
    },
    "completion": {
      "complete": true,
      "missing_tools": [],
      "message": "必需工具已执行；报告质量仍需校验。"
    }
  }
}
```

## 独立复核与局限

本地统计和Agent工具结果一致；若任务E生成报告成功，则支持跨字段结构的统计、IQR和公开证据输出链路可运行，不代表模型解释完全正确。实际工具选择、状态、输入输出摘要、来源、响应ID和usage保存在原始JSON中；知识工具若origin为requirement_guard，不能记作模型主动检索。
模型原始报告中的“大量-1占位值可能主导/放大异常”只是假设，编码也未获官方确认。实际每个选定字段仅有16–17个负值，不能据此前20条样本解释9466行异常；不得把该推测作为已验证原因。模型提出的剔除占位值建议必须先确认编码规则，本阶段未执行该清洗或额外调参。
ICMP ping有1个不可解析值，本阶段不静默清洗。原始负数保留：`{'ICMP loss': 17, 'ICMP response time': 17, 'U_ Bits_ received': 16, 'U_ Bits_ sent': 16, 'B1_Bits_ received': 16, 'B1_Bits_ sent': 16, 'P1_ Bits_ received': 16, 'P1_Bits _sent': 16}`。-1编码含义未确认，可能影响分位数和异常数量。
单位、时间单位/时区、接口前缀与累积/速率口径尚缺官方字段字典；字段名解释属于分析候选，不是故障定位依据。全样本分位数为本文件描述性统计，不是跨设备泛化评价。仅验证R1，没有分析R2–R7。
复现：`python scripts/fetch_lcore_r1.py`获取官方文件并校验；`python scripts/validate_lcore_r1.py`只运行本地验证；`--real-agent`执行一次E，已有记录时拒绝重复付费。原CSV受.gitignore排除，来源核验摘要保存于lcore_r1_provenance.json。
没有将统计异常当作故障标签，也没有宣称真实校园网部署或准确诊断所有故障。
