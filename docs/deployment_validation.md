# 第六阶段部署验收记录（用户人工验收完成）

## 当前状态

- 记录日期：2026-10-28（Asia/Shanghai）；准备、上线人工确认及首次真实Agent验收均在该日记录。
- 选定平台：Streamlit Community Cloud；未购买平台资源，首次真实模型验收会使用API额度，具体费用未取得。
- 本地Python：3.11.18；云端建议选择3.11，实际运行版本尚未取得平台日志确认。
- 当前阶段：本人确认线上首页、模拟数据、图表、来源链接、两级模式及异常输入检查结果正常，并提供首次真实Agent成功截图。第六阶段功能验收完成；部分平台元信息仍待独立核实。
- 公开HTTPS地址：https://netdiag-agent-fsgchtnhbusiaqejfvi76s.streamlit.app/ 。收到地址日期2026-10-28；云端实际Python版本及成功发布commit尚未确认。
- 目标仓库：https://github.com/lxa061031-max/NetDiag-Agent 。首次只读网页检查HTTP 200时为空仓库；本人上传后再次核实分支main，app.py位于仓库根目录。GitHub匿名API此前返回403，不把403直接归因为未登录，完整commit历史尚未核验。
- 2026-10-28只读检查GitHub网页得到main当前提交：`088ca41c0f74717ad7b090161a1b217078afab8d`。这是仓库main当时的标识；Cloud实际运行提交尚未从平台日志独立核实，不能断言两者相同。
- 本地未建立Git仓库、未找到Git命令；当前浏览器连接返回无可用浏览器，GitHub集成尚未连接。未执行上传/提交，未检查完整远程历史，未代办登录、授权或填写Secret。
- 版本记录：**NetDiag-Agent Competition Demo v1.0**，2026-10-28完成用户人工验收并冻结核心功能；这是本地文档中的版本标识，尚未创建Git标签或将该文档更新提交到仓库。

### 上传后仓库复核（2026-10-28）

按`dist/github_upload_20261028_031802_213404`的61个白名单文件访问公开main分支：56项HTTP成功且SHA256完全一致，无内容差异；其余5项HTTP 404：`.env.example`、`.gitignore`、`.streamlit/config.toml`、`.streamlit/secrets.toml.example`、`config/.gitkeep`。已确认入口、requirements、src、模拟CSV与知识库均存在。`config/.gitkeep`仅为空目录占位，不影响运行；其余配置/安全模板应补齐，尤其config.toml包含上传限制和禁用公开堆栈设置。

本次未读取远程真实.env或secrets.toml，未代为提交，未发起模型API请求。Cloud部署与在线验收仍未执行，不将仓库上传成功等同于应用部署成功。

后续修正记录：本人先补传.gitignore与.env.example，并将config.toml、secrets.toml.example从根目录移动到.streamlit。2026-10-28再次网页核实：仓库根目录存在.streamlit目录，其下有config.toml与secrets.toml.example；配置页HTTP 200，包含maxUploadSize、showErrorDetails、headless、gatherUsageStats配置项。这里只确认路径和配置项存在，不将其描述为新一轮全仓库哈希校验。config/.gitkeep为可省略的空目录占位。下一步先不填Secrets部署数据分析页面，通过后再由本人配置Secret并执行唯一一次真实Agent验收。

### 公开URL首次检查（2026-10-28）

匿名访问首页HTTP 200，最终域名仍为上述streamlit.app域名；健康路径/_stcore/health也返回HTTP 200，但正文是HTML而不是ok，因此本次不能据此确认应用后端健康或判定失败。浏览器连接尝试返回无可用浏览器，尚不能可视检查动态页面。等待本人确认NetDiag-Agent标题、240行模拟数据、适配表与图表均正常，或提供不含Secret的截图。未上传测试数据、未填写Secret、未点击诊断，真实API验收执行次数为0。

后续人工确认（2026-10-28）：本人回复“页面正常，240行，图表正常”。据此记录首页、内置模拟数据加载及图表人工验收通过；未把此回复扩展为上传CSV、适配确认、两级模式切换、异常输入或Agent已验收。当前进入本人配置Cloud Secrets步骤，尚未确认云端API配置成功，真实API验收仍为0次。

### Secrets及首次真实Agent验收（后续结果）

本人报告已更换密钥并配置Secrets。旧密钥曾随IDE上下文进入聊天，已要求撤销；这里只记录本人操作报告，不保存密钥、片段或指纹，不宣称独立检查过服务商撤销状态。随后本人提供四张业务截图，显示deepseek-flash真实API成功，依次执行analyze_network_metrics、detect_anomalies、search_fault_knowledge，均为ok。六部分报告完整，79条异常、22个异常行与独立本地复算一致，并明确无法确认根因。公开知识条目有3项，展开后的来源链接及证据JSON尚待核对。详见[首次线上验收记录](online_agent_acceptance.md)。

至此有截图证据的真实Agent验收为1次；没有为补截图重复调用。助手仅运行本地统计核对，没有使用密钥或发起额外模型请求。此前各节0次的描述是当时的历史状态，不是当前计数。

### 其余在线交互的人工确认

针对来源名称与链接、证据链、Generic / Semantic切换、无数据提示及按钮状态、空白CSV和未知字段CSV，用户随后回复“检查结果和你的一样”，按人工验收通过记录。助手没有可用的浏览器连接，未独立重现这些动态交互，也未追加截图或新模型调用。

## 已执行的本地检查

- `python -m pip install -r requirements.txt` 成功，退出码0，现有依赖均满足；未安装PyTorch或新增框架。固定已验证的Streamlit 1.66.1和OpenAI SDK 2.54.0，不全面升级依赖。
- 最终完整Pytest：**78 passed in 7.57s**，退出码0，原有68项保留。记录：[文本](stage_6_pytest.txt)、[JUnit](stage_6_pytest.xml)。Agent均使用Mock，未产生真实API费用。
- Streamlit本地启动：`python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501`；`/_stcore/health`返回HTTP 200、正文ok，首页HTTP 200。仅监听本机回环地址，不是公开部署。
- AppTest覆盖模拟数据页面、适配结果、两级分析、未配置API、无数据状态；上传解析单测覆盖空CSV、编码错误、非CSV、未知字段、大小/行列限制。不把AppTest称为线上浏览器验收。
- 安全规则扫描：未发现疑似真实密钥格式或业务代码中的Windows绝对路径。只报告文件/行号，不读取真实.env或Secrets文件，不输出匹配内容。记录：[安全检查](stage_6_security_check.json)。规则扫描不能保证不存在一切秘密，上传前仍需本人审阅。
- `.gitignore`排除.env、.env.*（保留.env.example）、虚拟环境、缓存、IDE目录、真实Secrets、根目录LCORE CSV和dist上传产物；data/raw与data/processed继续排除。
- 三个演示Prompt已保存到[demo_prompts.md](demo_prompts.md)。没有运行这些真实付费任务。

## Secrets与错误安全

配置优先级：系统环境变量 → 项目.env → Streamlit Secrets。云端不得上传.env；通过平台Secrets管理填写三个根级键。缺少配置时，数据分析可用，Agent按钮禁用。API错误只显示固定友好提示，不返回响应正文或Header；公开网页禁用完整堆栈。配置对象repr隐藏API密钥。

模版位于 `.streamlit/secrets.toml.example`，其中密钥为空。密钥只能由本人填到平台，不发到聊天、不放截图、不上传GitHub。助手未填写Secret、未接受OAuth授权，也未发起真实模型请求。

公共应用的Agent会消耗部署者额度；当前没有全站限流/身份验证。本人必须确认服务商预算和演示窗口，不能将每任务3工具/2模型请求理解为全站费用上限。未设置API时也可以先验收全部本地分析功能。

## 本阶段文件变更

- 修改：`.gitignore`、`requirements.txt`、`README.md`、`app.py`、`src/agent/single_agent.py`（只改配置读取与错误脱敏，工具选择流程不变）。
- 新增：`.streamlit/config.toml`、`.streamlit/secrets.toml.example`、`src/agent/configuration.py`、`src/data_processing/upload_validation.py`、`scripts/prepare_deployment.py`、`tests/test_deployment.py`。
- 文档与真实本地记录：`docs/demo_prompts.md`、本文件、`stage_6_pytest.txt`、`stage_6_pytest.xml`、`stage_6_security_check.json`。
- 后续验收记录及手工上传样本：`docs/online_agent_acceptance.md`、`tests/fixtures/deployment/blank.csv`、`tests/fixtures/deployment/unknown_metrics.csv`。不修改应用算法或增加工具。
- `dist/`为忽略的白名单上传产物，不是已提交的Git仓库。没有修改检测、适配、知识检索算法或历史实验结果。

## 部署操作过程（历史说明）

### 1. GitHub白名单文件上传

1. 已收到目标仓库，本人在浏览器打开 https://github.com/lxa061031-max/NetDiag-Agent ；无需重复新建仓库。
2. 如需登录，验证码/密码只在官方页面本人输入，不发送密码、Token或Secret给助手。
3. Public会公开源码；Private需要Cloud获准访问该仓库。**可见性由本人决定，不代为更改。**
4. 本次白名单包复核61个文件，无缺失，生成目录与项目一致；扫描未发现疑似密钥或业务代码Windows绝对路径。可选择本人完成网页上传；也可自行连接GitHub后再检查可用的提交能力，不承诺未连接前已具备写权限。
5. 在仓库选择 **uploading an existing file**，或 **Add file → Upload files**。从 `dist/github_upload_.../` 目录上传其**内部内容**，保留src、data、.streamlit等相对结构，确保`app.py`位于仓库根目录。不要上传整个原始项目目录或只上传ZIP。
6. 上传预览中核对：必须有 `.gitignore`、`.env.example`、`.streamlit/config.toml`，不得有 `.env`、`secrets.toml`、原始R1和缓存。浏览器上传不应被当作.gitignore自动保护，必须使用白名单目录并检查文件清单。
7. 提交信息可填写 `Prepare Streamlit deployment candidate`，确认提交。若用现有仓库，必须先检查已有文件和历史，不能覆盖不明内容。

### 2. Streamlit Cloud登录、授权和配置（完成上一步后）

1. 本人打开 https://share.streamlit.io ，完成登录。遇GitHub OAuth授权时本人阅读权限；若可选仓库范围，只授权目标仓库。
2. 点击 **Create app → Yup, I have an app**（以实际页面为准）。
3. Repository填写`你的账号/NetDiag-Agent`，Branch选择实际默认分支（通常main），Main file path填写`app.py`。
4. **Advanced settings → Python version**选择`3.11`。
5. **Secrets**由本人输入以下TOML，仅将第一项等号右侧空字符串替换成自己的密钥，不要把密钥发回：

```toml
LLM_API_KEY = ""
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-flash"
```

6. 确认额度风险后由本人保存并点击 **Deploy**。也可以暂不填Secret先检查页面，稍后在应用设置的Secrets中配置。
7. 记录安装日志、云端实际Python版本、commit hash和生成的HTTPS地址；不要截图Secret编辑页。确认应用访问权限确实允许公开访问，而不是仅自己已登录时可见。

官方依据（2026-10-28核实）：[Cloud部署](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)、[Secrets管理](https://docs.streamlit.io/develop/concepts/connections/secrets-management)、[GitHub上传文件](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)。

## 在线验收表（用户人工确认）

|项目|结果|待记录证据|
|---|---|---|
|公开首页|人工确认通过，另有匿名HTTP 200|本人回复页面正常；助手未直接操作动态浏览器|
|模拟数据、上传与两级分析|用户按提示验收，240行及图表正常，模式切换正常|首轮上传控件未单独截图；截图为诊断结果，不能冒充完整上传原始日志|
|真实Agent|首次调用流程通过（本人业务截图）|3工具均ok、六部分报告完整；不重复付费调用|
|知识检索与来源|检索成功，3条标题见截图；用户确认来源链接和证据链检查结果正常|来源链接/展开内容为用户人工确认，助手未独立浏览|
|无数据、空CSV、未知字段|用户确认与预期一致|提示、按钮状态和通用分析按用户回复记录；未提供额外截图|
|Secret安全|本人报告已更换密钥并配置平台Secrets；截图未见密钥|服务商撤销状态未独立核验，不读取或索要密钥；仍需关闭IDE中的.env标签|

唯一真实Agent验收任务：

> 请分析当前上传的数据集，检查主要网络指标和异常情况，并基于实际数据给出有依据的诊断建议。如果证据不足，请明确说明。

该任务与独立Prompt清单不是批量执行计划。点击前记录次数，最多一次；失败时保留失败记录，不为得到成功截图自动重试。不得把历史本地真实API记录当作本次在线验收。

## 限制与发布条件

已取得公开地址、本人动态页面确认及真实Agent截图；来源链接、模式切换和异常输入由本人确认。云端实际Python版本及部署commit尚未独立核验，GitHub main标识已记录。截图不是完整原始API日志，Token/费用未知。云端资源、休眠及网络连通性受平台限制；本地原始LCORE数据不上传，线上使用模拟CSV或用户上传。当前公开应用没有全站限流/用户鉴权，单任务上限不能限制全站费用。

用户已确认在线表中要求的功能检查，本地记录以**NetDiag-Agent Competition Demo v1.0**标识冻结候选版本，记录日期、GitHub main当前提交和本地测试结果。因未核对Cloud实际运行commit且未创建Git标签，不声称完成Git标签发布或证明线上部署版本等于该提交。可以准备第七阶段；正式比赛前应核对平台运行版本与额度管理。不得修改检测算法、历史实验或为了成功而重复付费验收。
