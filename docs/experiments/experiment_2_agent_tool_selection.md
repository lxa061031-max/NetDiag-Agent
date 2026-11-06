# 实验2：Agent 工具选择与调用能力

> 本文件保留第五阶段初始状态与Mock测试说明。后续已按授权执行A/B/C各一次，首次真实结果见 [真实API记录](experiment_2_agent_tool_selection_real.md)，失败与遗漏也原样记录。以下“待完成”是初始阶段状态，不代表当前尚未执行。

## 真实 API 记录：待完成

用户已说明真实 API 和网页曾人工验收成功，但当前项目中未找到可核对的逐任务调用记录、工具结果及最终报告。此前的人工验收不能替代本实验三个固定任务的记录。本次没有请求真实 API，因此以下任务的实际工具、合理性、工具是否成功、数据依据及不确定性均为**未记录，无法判断**。

| 任务 | 固定用户任务 | 期望工具（仅作参考） | 真实 API 实际工具及评价 |
|---|---|---|---|
| A | 请告诉我当前数据集的基本情况，包括数据规模、字段和缺失值情况。 | `get_dataset_summary` | 未记录，无法判断 |
| B | 请分析当前网络指标，并检查是否存在网络异常，给出数据依据。 | `analyze_network_metrics`、`detect_anomalies` | 未记录，无法判断 |
| C | 请根据当前异常分析可能原因，并检索相关网络故障知识，给出排查建议。如果证据不足，请明确说明。 | `detect_anomalies`、`search_fault_knowledge` | 未记录，无法判断 |

## 自动化测试 Mock：不作为真实工具选择实验

运行全部 Pytest 时，`test_agent_tool_call_flow_uses_two_model_calls_and_real_results` 使用预设 Mock 响应指定三个调用：`get_dataset_summary`、`analyze_network_metrics`、`detect_anomalies`。三个工具对测试 DataFrame 实际执行，第二轮收到 Python 计算出的结果；Mock 报告中包含数据依据和不确定性说明。调用由测试预先指定，不能证明真实模型自主选择的合理性。

`test_agent_integrates_knowledge_tool_result_into_report` 使用预设 Mock 响应指定 `detect_anomalies` 和 `search_fault_knowledge`。测试验证知识结果进入第二轮请求、报告含 `[参考知识]`、并返回可展示来源；报告本身也是测试预设文本，不证明真实模型报告的质量或事实与推测区分能力。

## 人工补录方法

需要时人工分别执行 A、B、C，每个任务最多运行一次；保存运行时间、数据来源、实际工具名及每个状态、真实工具结果证据、完整报告和来源。逐项检查工具是否与任务相关、是否引用数据、是否区分事实与推测以及是否说明不确定性。真实 API 才标记为“真实 API 执行”，并注意保护密钥和敏感数据。
