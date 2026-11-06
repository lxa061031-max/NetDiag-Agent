# 实验3：本地知识检索

固定查询使用现有 `search_fault_knowledge` 直接运行；相关性依据预先指定的目标条目是否出现，属于简单规则检查。

| 查询 | 返回条目 | 目标条目命中/无匹配正确 | 来源 |
|---|---|---|---|
| 网络时延明显升高应该排查什么？ | 网络时延升高 | 是 | [RFC 7679: A One-Way Delay Metric for IPPM](https://www.rfc-editor.org/rfc/rfc7679.html) |
| 网络丢包率持续升高的常见原因有哪些？ | 丢包率升高 | 是 | [RFC 7680: A One-Way Loss Metric for IPPM](https://www.rfc-editor.org/rfc/rfc7680.html) |
| 设备CPU使用率过高可能对网络造成什么影响？ | 网络设备 CPU 利用率过高 | 是 | [Cisco: Report Problems with High CPU/QFP on Routers to TAC](https://www.cisco.com/c/en/us/support/docs/technical-details/222469-reporting-problems-effectively-to-tac-se.html) |
| DNS解析失败应该如何排查？ | DNS 解析失败或 SERVFAIL | 是 | [RFC 9520: Negative Caching of DNS Resolution Failures](https://www.rfc-editor.org/rfc/rfc9520.html) |
| 量子网络光源漂移如何处理？ | 本地知识库中没有匹配条目，不能提供知识来源。 | 是 | 无 |

查询数量：5；4 个有目标查询中目标命中：4/4；无匹配提示正确：是；来源完整率：4/4（100.0%）。

来源名称与 URL 来自知识库返回值；完整率只检查非空，不代表链接永久可访问或内容能证明现场根因。知识条目仅为排查参考，本实验未运行模型，无法验证真实报告中事实与推测的区分。

复现：`python scripts/run_experiments.py`。
