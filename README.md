# NetDiag-Agent

面向校园网络运维的自适应智能故障诊断系统。当前核心功能已冻结，正在进行第六阶段部署验收；尚未宣布在线验收通过或发布 Competition Demo v1.0。

> Agent 仅处理当前页面已加载的数据，可调用三个只读分析工具和一个本地知识检索工具。包含结构化证据链与不确定性说明，不使用多智能体、向量数据库或复杂机器学习模型。

## 已实现功能

- 中文 Streamlit 首页与功能提示
- CSV 上传和数据预览
- 行数、字段数、数值字段、缺失值、重复行统计
- 数值列选择和 Plotly 交互式趋势图
- 数值指标的 count、mean、min、max、std、median 和 p95 统计
- 针对默认网络指标的固定阈值与 IQR 异常检测
- 异常时间点、指标、实际值、触发规则和原因展示
- 单 Agent 自然语言诊断和实际工具调用记录
- 数据集摘要、网络指标统计、异常检测和本地故障知识检索四个工具
- 异构CSV语义映射、当前会话人工确认、Generic / Semantic两级分析
- 最多三次工具执行、两次模型请求和受限输出长度
- 固定随机种子的模拟数据生成器
- 数据读取、字段校验和可视化自动化测试

## 环境要求

- Python 3.11
- Windows、macOS 或 Linux

### Windows PowerShell

```powershell
cd NetDiag-Agent
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

### macOS / Linux

```bash
cd NetDiag-Agent
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

启动后，终端会显示本地访问地址，通常为 `http://localhost:8501`。

## 大模型 API 配置

项目沿用已经人工验收的 OpenAI Python SDK Responses API 与 DeepSeek 配置，本阶段不切换接口或模型。示例模型为 `deepseek-flash`，实际可用性以服务商账户和接口为准。

程序会自动读取项目根目录的 `.env`。该文件已被 `.gitignore` 排除，真实密钥不要写入源码、README 或提交到仓库。

### Windows 初学者配置

1. 用记事本或 VS Code 打开项目根目录的 `.env`。
2. 找到 `LLM_API_KEY=`，在等号后粘贴自己的API密钥；不要发送密钥给助手。
3. 保持 `LLM_BASE_URL=https://api.deepseek.com` 不变。
4. 保持已验收的 `LLM_MODEL=deepseek-flash` 配置并保存文件。
5. 如果网页正在运行，先在终端按 `Ctrl+C`，再运行 `python -m streamlit run app.py`。

`.env.example` 是不含密钥的配置模板。页面不会显示密钥，也不会在缺少配置或 API 失败时冒充真实 Agent。系统环境变量仍可使用，并且优先于 `.env` 中的同名配置。

单次任务最多执行三个工具和两次模型请求。程序只把任务、字段元信息以及 Python 工具结果发给模型，不会默认发送完整 CSV。

## 部署与安全

优先平台为 Streamlit Community Cloud，入口为 `app.py`。部署时在 **Advanced settings** 选择 Python **3.11**，并由本人在平台 **Secrets** 中填写 `.streamlit/secrets.toml.example` 的三个配置项，不要上传真实 `.env` 或 `secrets.toml`。配置读取优先级为系统环境变量、项目 `.env`、Streamlit Secrets。未配置API时，CSV分析仍可使用。

Streamlit固定为本地已验证的1.66.1、OpenAI SDK固定为2.54.0，其余依赖保留原有范围，不要求安装PyTorch。可用 `python -m pip install -r requirements.txt` 和 `python -m pytest -q` 验证。

上传仅接受CSV，限制10MB、50,000行、100列。只读取数据，不保存或执行上传文件。请勿上传个人信息或敏感网络资料；点击诊断会向模型服务商发送任务、字段元信息和工具摘要。

**公开成本提醒：** 公共网页的访问者也能消耗平台配置的API额度。当前无全站限流或用户鉴权；请本人先确认服务商预算/额度限制，必要时只在演示时配置Secret，演示结束后移除。服务商是否提供硬额度上限需自行核实，不能把单任务工具上限当作全站费用上限。

离线检查：`python scripts/prepare_deployment.py`。生成白名单上传目录与ZIP：`python scripts/prepare_deployment.py --build`。产物位于被Git忽略的 `dist/`；不包含真实密钥、原始LCORE CSV、IDE目录或缓存。ZIP用于传递/备份，**不能直接作为GitHub仓库的应用入口**，必须上传其内部文件并保留目录结构。

登录、OAuth授权、源码可见性选择、Secret填写和发布确认均由本人操作，不自动绕过。详细步骤和未完成项见 [部署验收记录](docs/deployment_validation.md)，三个固定演示任务见 [演示Prompt](docs/demo_prompts.md)。

## 运行测试

```bash
python -m pytest -q
```

## 模拟数据说明

`data/demo/synthetic_network.csv` 是**模拟数据，不是真实校园网络数据**。生成器位于 `src/data_processing/synthetic_data.py`，默认使用固定随机种子 `20261026` 生成 240 个按分钟排列的样本：

- 正常延迟约为 25 ms，丢包率约为 0.25%，CPU 使用率约为 42%，温度约为 46°C；
- 随机选取 20 个时间点，同步提高延迟、丢包率、CPU 使用率和温度；
- `anomaly_label=0` 表示正常模拟样本，`anomaly_label=1` 表示人工注入的异常模拟样本；
- 数值经过合理范围裁剪并保留两位小数，生成结果可由固定种子复现。

重新生成演示数据：

```bash
python -m src.data_processing.synthetic_data
```

## 数据集调查

LCORE-D 的核实结果、已确认限制和下一步建议见 `docs/dataset_feasibility.md`。公开原始数据未纳入仓库。
