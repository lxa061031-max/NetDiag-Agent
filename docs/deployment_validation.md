# 第六阶段部署验收记录（尚未在线验收）

## 当前状态

- 记录日期：2026-10-28（Asia/Shanghai）。这是准备日期，**不是部署成功日期**。
- 选定平台：Streamlit Community Cloud；未使用付费资源。
- 本地Python：3.11.18；云端拟选择3.11，尚未创建云端环境。
- 当前阶段：本地部署准备完成；已提供目标GitHub仓库，等待本人上传或连接GitHub，之后再进行Cloud登录、授权与Secret填写。
- 公开HTTPS地址：尚未生成。
- 目标仓库：https://github.com/lxa061031-max/NetDiag-Agent 。本次只读网页检查HTTP 200，存在空仓库初始化提示，未看到app.py入口链接；GitHub匿名API返回403，未确认默认分支或commit hash，不把403直接归因为未登录。
- 本地未建立Git仓库、未找到Git命令；当前浏览器连接返回无可用浏览器，GitHub集成尚未连接。未执行上传/提交，未检查完整远程历史，未代办登录、授权或填写Secret。
- Competition Demo v1.0：尚未完成线上验收，不打发布标签；核心算法维持冻结。

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
- `dist/`为忽略的白名单上传产物，不是已提交的Git仓库。没有修改检测、适配、知识检索算法或历史实验结果。

## 需要本人操作：先GitHub，再Cloud

### 1. GitHub白名单文件上传（当前停止点）

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

## 在线验收表（尚未执行，不能填写成功）

|项目|结果|待记录证据|
|---|---|---|
|公开首页|待执行|未登录/无痕窗口打开HTTPS地址，无错误|
|模拟CSV上传|待执行|上传240行模拟CSV，预览、适配、图表、两级分析正常|
|真实Agent|待执行|只执行一次验收任务，记录首次成功或失败，不自动重复|
|知识检索与来源|待执行|同一次任务的实际工具记录、来源名称与可打开链接|
|无数据、空CSV、未知字段|待执行|不崩溃、提示明确；不点击额外Agent任务|
|Secret安全|本地准备已检查，云端待本人确认|Secret仅平台管理，公开页面/仓库/截图无真实密钥|

唯一真实Agent验收任务：

> 请分析当前上传的数据集，检查主要网络指标和异常情况，并基于实际数据给出有依据的诊断建议。如果证据不足，请明确说明。

该任务与独立Prompt清单不是批量执行计划。点击前记录次数，最多一次；失败时保留失败记录，不为得到成功截图自动重试。不得把历史本地真实API记录当作本次在线验收。

## 限制与发布条件

未取得公开地址，尚无云端依赖安装和真实API验证证据。当前依赖仅在本地Windows Python3.11.18验证，Linux云端仍待验证。云端资源、休眠及网络连通性受平台限制；本地原始LCORE数据不上传，线上使用模拟CSV或用户上传。

只有在线表全部验收完成后才能发布 **NetDiag-Agent Competition Demo v1.0**，并记录实际日期、commit hash及测试结果。尚不建议进入第七阶段。不得修改检测算法、历史实验或为了成功而重复付费验收。
