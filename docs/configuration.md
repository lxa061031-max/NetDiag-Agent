# NetDiag-Agent v1.0.1 配置说明

本版是本地配置化优化；原有数据、阈值默认值、异常算法、Agent工具循环与历史实验结果保持不变。当前线上版本不会自动因本地修改而更新，尚未进行v1.0.1云端部署或在线验收。

## 模型

本地依次使用系统环境变量、项目`.env`、Streamlit Secrets获取`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`；已有环境变量优先。界面“诊断模型”默认选`LLM_MODEL`，未配置时显示Flash；每个会话可切换：

|界面|API模型ID|提示|
|---|---|---|
|DeepSeek Flash|`deepseek-flash`|快速分析|
|DeepSeek V4 Pro|`deepseek-v4-pro`|更复杂诊断，费用和可用性以实际账户为准|

两个选项复用同一Agent和Responses API。未知运行时覆盖值会拒绝；若环境中是其他模型，界面显示不支持并禁用诊断，需选择受支持模型。密钥不显示也不写回配置。项目不要求创建新密钥或购买服务。

模型ID与接口依据：[DeepSeek Responses API官方文档](https://api-docs.deepseek.com/api/create-response/)，[官方模型与价格说明](https://api-docs.deepseek.com/quick_start/pricing/)。官方支持不等于任何账户均有权限；额度和实际调用结果以账户为准。公共Cloud应用的用户可能消耗部署者额度。

## 异常检测参数

展开“异常检测参数”可设置以下默认上限和IQR倍数：

|原指标|默认上限|允许范围|
|---|---:|---|
|latency_ms|80 ms|有限数值，≥0|
|packet_loss_pct|5%|有限数值，0–100|
|cpu_usage_pct|85%|有限数值，0–100|
|temperature_c|65 °C|有限数值，≥−273.15|
|IQR multiplier|1.5|有限数值，>0；页面最小0.01|

默认值来自原有集中配置，非行业标准。IQR上下界为Q1−k×IQR、Q3+k×IQR；已有算法对于有效值不足4或IQR为0会跳过该统计规则。固定阈值与IQR为并集。

页面的“恢复默认值”勾选框每次切换都会恢复所有参数。设置仅存在当前Streamlit会话，不修改Python文件、`.env`、Secrets、原始CSV或历史实验；新会话使用默认值。非法数值经服务端验证并提示，页面回退到默认值。数值列的上下限仅是使用约束，不代表已经校准的网络故障边界。

页面和Agent均使用同一会话设置；Agent的工具结果记录实际字段、固定阈值、是否使用IQR及实际倍数。模型不能自定阈值。报告可能由模型选择描述细节，工具结果才是配置和计算依据；用户修改配置后旧报告不再作为当前配置的结果显示。

## 标准语义与别名

`src/data_processing/schema.py`的`SEMANTIC_REGISTRY`集中维护12种语义：latency、packet_loss、cpu_usage、temperature、traffic_received、traffic_sent、jitter、error_count、drop_count、throughput、signal_strength、snr。`delay_variation`作为`jitter`的别名，保持旧内部名称兼容。名称中的下划线和空白会规范化，例如`loss_rate`与`loss rate`匹配同一强别名；按规范化后的不同名称计，共54个别名，额外的LCORE接口模式表达式不计入。

常见例子：`latency_ms`、`rtt`、`response_time`；`packet_loss_pct`、`loss_rate`；`rx_bytes`、`tx_bits`；`delay_variation`、`throughput`、`rssi`和`snr`。这些是项目支持的常见字段名称，不代表已核实所有公开数据集使用这些名称，也不代表自动确认单位。原字段名保留，多个字段可映射到同一语义；字段数量不受语义数量限制。

精确别名1.0、强别名0.9、弱别名0.6、未知0；弱或未知数值字段需要人工确认。确认仅作用于当前会话。单位不由数值分布推断；没有明确兼容单位时，即便语义识别，也不能套用固定阈值。CPU和温度是设备监控指标，不强行声称遵循同一RFC。

Generic Analysis可对合法数值字段做统计与IQR；Semantic Network Analysis仅接受可靠映射或人工确认的网络语义。未知字段不阻止预览或通用分析。如果没有可靠语义，页面提示使用标准字段/兼容别名，同时保留Generic。LCORE-D R1使用既有原始字段，单位和标签语义不强制猜测，固定阈值不套用，只执行IQR。

## v1.0.1 真实模型验收

2026-10-28，使用相同简短任务和模拟数据，每个模型各执行一次真实Agent任务，SDK自动重试关闭。Flash成功：detect_anomalies → analyze_network_metrics；V4 Pro成功：detect_anomalies；均生成报告。每个Agent任务可包含最多两次模型请求；没有因为结果不同而重复试验。

原始记录：[Flash](experiments/v101_model_default.json)、[V4 Pro](experiments/v101_model_pro.json)。它们记录当前运行结果，不覆盖历史实验；结果不代表模型在所有数据或账户中均可用。
