# 异构网络数据自适应接入（第5E阶段）

## 设计边界

不同监控系统的字段名、单位、状态编码和采样方式不同，不能仅重命名后套用同一组阈值。系统保留原始 DataFrame，通过独立 Schema Mapping 描述分析权限；不写回上传CSV，不使用LLM、Embedding或新机器学习算法进行字段分类。不声称支持任意数据集。

本阶段冻结核心功能；未部署，未调用真实付费API，未修改历史实验和检测算法、阈值。

## Schema Mapping

`src/data_processing/schema.py` 本地识别字段，`describe_dataset` 返回完整适配描述。每个字段包含：

- `source_column`、`dtype`：原始名称、类型，工具仍以原名分析。
- `canonical_name`、`unit`：候选语义、明确单位；未知单位为 `null`。
- `confidence`、`mapping_source`：规则级别和来源，不是经实验校准的概率。
- `needs_confirmation`、`semantic_enabled`、`analysis_type`、`warnings`：确认需求、专业分析权限、分析级别和复核提示。

兼容已有 `source_type`、`metric_mapping`、`analysis_columns`；新映射位于 `schema_mapping`。陌生结构使用 `generic`，标准字段使用 `synthetic` 兼容结构，ICMP特征组合使用 `lcore_r1` 兼容结构。这些结构判断不认证文件来源；外部CSV的真实性、标签语义需人工核实。

只支持九种标准语义：`latency`、`packet_loss`、`cpu_usage`、`temperature`、`traffic_received`、`traffic_sent`、`jitter`、`error_count`、`drop_count`。

## 识别与置信度

|规则|示例|分值|处理|
|---|---|---:|---|
|exact_alias|latency_ms、packet_loss_pct、cpu_usage_pct|1.0|数值类型有效时允许语义分析|
|strong_alias|rtt、response_time、ICMP response time、loss_rate、device_cpu|0.9|允许语义解释；单位仍未知|
|weak_alias|delay、loss、cpu、temp|0.6|待确认，仅通用分析|
|unknown|metric_a、metric_b|0|不强制映射，仅通用分析|

安全阈值为0.9。字段必须为合法实数列，标签、时间和已识别的状态编码不作为指标；字符串、布尔、复数列不自动进入数值分析。别名只做大小写、下划线和空白规范化，不做任意子串猜测。

值分布只用于降低可信度：例如显式百分比超出0–100、毫秒/计数出现负值、没有有限有效值，降为待确认。**绝不从0–1、0–100等范围推断单位**。缺失值保留，非有限值仅在分析副本中按缺失处理。

## 人工确认与界面

“数据适配结果”表展示字段、dtype、候选语义、置信度、确认状态和专业分析权限。低置信度/未知数值字段可选择九种语义之一，或“保持通用数值字段”；默认“暂不确认”。

确认字典只传给当前会话的适配器和Agent，不写CSV或磁盘。控件键使用数据内容及结构指纹，防止不同上传文件错误复用确认；报告缓存签名也包含确认结果。确认语义不等于确认单位，单位未知仍禁止固定阈值。非法字段名、非数值字段、非法语义会被服务端拒绝。

## 两级分析

`src/data_processing/analysis.py` 负责路由，复用 `calculate_numeric_statistics` 和已有 `detect_anomalies`。

- Generic Analysis：合法数值指标的count、mean、median、std、min、max、p95和IQR；不做专业故障解释、不应用固定阈值。标签、时间、LCORE状态编码排除。
- Semantic Network Analysis：仅 `semantic_enabled=true` 的字段；语义和单位均符合已有规则时，才复用四项原有固定阈值。流量、抖动等没有既有固定规则的语义仍只使用IQR。
- `auto`：按字段逐一安全路由；注册工具支持 `analysis_mode`，旧调用不提供时默认auto。Agent每次分析最多8个字段，仍最多3次工具、2次模型请求。
- LCORE保持既有八字段默认选择与IQR-only策略，原量纲不变，不转换单位，不推断H/F或-1语义；其他适配数值字段可显式选择通用分析。
- IQR为0或有效样本不足4时沿用现有跳过逻辑，不能把未检出解释成健康。统计异常不等于已确认故障。

## Agent约束

模型上下文与公开证据链包含映射来源、权限和待确认状态。知识查询仅从前序真实异常中语义可靠的字段生成；只有未知字段的检测证据不能用于网络专业知识诊断，也不能因数据集里另有一个已识别字段而绕过限制。

未知语义或未知单位通过确定性提示加入证据的 `uncertainties` 和最终报告，六个必需报告部分及原有校验保留。映射不替代因果证据，模型仍必须说明无法确认根因。没有可用专业证据时，知识检索可能被阻止，任务完成度会如实显示未完成，不伪造来源。

## 本地验证（2026-10-28）

完整Pytest：**68 passed in 8.25s**，退出码0；原有47项全部保留并通过，新增21项，包括三个CSV用例、Streamlit AppTest与本地R1回归。全部Agent测试为Mock，不调用真实API。

|验证数据|实际结果|
|---|---|
|标准字段CSV|latency_ms/packet_loss_pct/cpu_usage_pct正确映射，置信度1.0|
|别名CSV|rtt/loss_rate/device_cpu正确映射，置信度0.9，单位null，不套固定阈值|
|未知字段CSV|metric_a/metric_b保留generic_numeric；统计与IQR正常；专业模式被拒绝|
|模拟数据|240行；4个网络语义字段；组合检测22个异常行、79条记录，保持原结果|
|本地LCORE-D R1|24,240行×42列；H=23,811、F=429（不展开语义）；默认8字段仅IQR，9,466个异常行、21,473条记录，保持原结果|

模拟数据SHA256：`1f9d2985e230c84b439601bc5e173f4c599910d17452e62225319354486e8528`。

R1 SHA256：`e2382475949174506bff1bdb28b80b67f5208896fdaa0b43e9e64000d06f3b33`。本地R1未分发时，仅真实文件回归测试skip，其余结构兼容测试仍执行。本次没有skip。

测试记录：[文本结果](stage_5e_pytest.txt)、[JUnit结果](stage_5e_pytest.xml)。通常运行 `python -m pytest -q`。本次原环境 `D:\conda_envs\pytorch\python.exe` 检查为0字节，使用同环境完整的 `pythonw.exe -X utf8 -m pytest -q --junitxml=docs/stage_5e_pytest.xml`，通过PowerShell `Start-Process -WindowStyle Hidden -Wait -PassThru` 重定向标准输出运行，未修改或修复系统环境。首次沙箱内AppTest临时目录清理受到权限限制，最终在获批执行环境运行正常，标准错误为空。

## 局限性与冻结建议

别名是人工维护的有限规则，无法保证任意字段名称或同名异义数据识别正确；时间仅识别常见名称或datetime类型，不自动解析时间格式/单位/时区。用户确认可能有误；不支持在本阶段人工填写/换算单位。语义启用不代表阈值存在或网络故障已被确认。未知单位字段只能用原量纲统计/IQR，并作有限语义参考。

本阶段未新增真实API验证；工具接口新增analysis_mode已经过Mock验证，真实服务兼容性仍需后续人工单次验收，不宣称已验证。LLM遵守文本解释约束仍有局限，应用层只强制工具执行权限与显式局限提示。

建议冻结核心功能；进入部署前先修复本机0字节Python控制台解释器，完成一次人工页面验收及必要的真实Agent兼容性确认。本阶段不执行部署。
