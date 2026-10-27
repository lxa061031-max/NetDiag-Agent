"""NetDiag-Agent 第三阶段 Streamlit 演示入口。"""

from pathlib import Path
import hashlib

import pandas as pd
import streamlit as st

from src.agent import (
    AgentConfigurationError,
    AgentExecutionError,
    get_agent_config_status,
    run_diagnosis,
)
from src.data_processing import (
    EmptyCSVError,
    build_data_summary,
    get_numeric_columns,
    read_csv,
)
from src.reporting import create_trend_figure
from src.tools import calculate_numeric_statistics
from src.data_processing.adapters import describe_dataset
from src.data_processing.schema import CANONICAL_NAMES
from src.data_processing.analysis import analyze_anomalies, prepare_analysis
from src.data_processing.upload_validation import read_uploaded_csv
from src.detection.config import detection_config
from src.agent.configuration import SUPPORTED_MODELS


PROJECT_ROOT = Path(__file__).resolve().parent
DEMO_DATA_PATH = PROJECT_ROOT / "data" / "demo" / "synthetic_network.csv"


st.set_page_config(page_title="NetDiag-Agent", page_icon="🌐", layout="wide")
st.title("🌐 NetDiag-Agent")
st.caption("面向校园网络运维的自适应智能故障诊断系统｜Competition Demo v1.0.1 本地版")

st.info(
    "当前版本支持 CSV 数据浏览、网络指标统计、基础异常检测，"
    "以及由大模型选择 Python 工具和本地知识的单 Agent 诊断。"
)

with st.expander("功能说明", expanded=True):
    st.markdown(
        """
        1. 上传 UTF-8 编码的 CSV，或直接使用项目内置的模拟演示数据。
        2. 查看数据预览、字段类型、缺失值与重复行等基础信息。
        3. 选择一个或多个数值字段，绘制交互式趋势图。
        4. 查看数据适配结果；通用数值字段用IQR，语义和单位明确的网络指标可使用既有固定阈值。
        5. 配置 API 后，用自然语言要求单 Agent 调用当前数据集分析工具。

        **注意：** 内置 CSV 是按固定规则生成的模拟数据，不是真实校园网络数据。
        """
    )

uploaded_file = st.file_uploader(
    "上传网络监控 CSV 文件",
    type=["csv"],
    help="仅CSV，UTF-8编码；最多10MB、50,000行、100列。请勿上传含个人信息或敏感网络信息的数据。",
)
use_demo = st.checkbox("未上传文件时使用模拟演示数据", value=True)


def load_selected_data() -> tuple[pd.DataFrame | None, str | None]:
    """根据页面选择加载上传文件或模拟数据。"""

    try:
        if uploaded_file is not None:
            return read_uploaded_csv(uploaded_file), f"上传文件：{uploaded_file.name}"
        if use_demo:
            return read_csv(DEMO_DATA_PATH), "模拟演示数据（非真实校园网络数据）"
    except UnicodeDecodeError:
        st.error("CSV编码无法识别，请另存为UTF-8编码后重试。")
        return None, None
    except pd.errors.ParserError:
        st.error("CSV格式无法解析，请检查表头、分隔符和引号。")
        return None, None
    except (EmptyCSVError, ValueError) as exc:
        st.error(f"CSV 读取失败：{exc}")
        return None, None
    return None, None


dataframe, data_source = load_selected_data()
schema_confirmations = {}
dataset_fingerprint = None

def reset_detection_settings():
    defaults = detection_config()
    for name, value in defaults["thresholds"].items():
        st.session_state[f"threshold_{name}"] = value
    st.session_state["iqr_multiplier"] = defaults["iqr_multiplier"]

with st.expander("异常检测参数", expanded=False):
    st.checkbox("恢复默认值", on_change=reset_detection_settings, key="reset_detection_defaults")
    defaults = detection_config()
    labels = {"latency_ms": "时延上限（ms）", "packet_loss_pct": "丢包率上限（%）",
              "cpu_usage_pct": "CPU上限（%）", "temperature_c": "温度上限（°C）"}
    for name, label in labels.items():
        st.number_input(label, min_value=(-273.15 if name == "temperature_c" else 0.0),
                        max_value=100.0 if name.endswith("_pct") else None,
                        value=defaults["thresholds"][name], key=f"threshold_{name}")
    st.number_input("IQR multiplier", min_value=0.01, value=defaults["iqr_multiplier"],
                    step=0.1, key="iqr_multiplier")
try:
    active_detection_settings = detection_config({
        "thresholds": {name: st.session_state.get(f"threshold_{name}", value) for name, value in defaults["thresholds"].items()},
        "iqr_multiplier": st.session_state.get("iqr_multiplier", defaults["iqr_multiplier"]),
    })
except ValueError as exc:
    st.warning(f"异常参数无效，已使用默认值：{exc}")
    active_detection_settings = detection_config()

if dataframe is None:
    st.warning("请上传一个有效 CSV，或勾选使用模拟演示数据。")
else:
    st.success(f"已加载：{data_source}")
    # 内容和结构共同隔离不同上传文件的会话确认，绝不写回CSV。
    dataset_fingerprint = hashlib.sha256(
        pd.util.hash_pandas_object(dataframe, index=True).values.tobytes()
        + repr(list(zip(dataframe.columns, dataframe.dtypes.astype(str)))).encode("utf-8")
    ).hexdigest()
    adapter = describe_dataset(dataframe)
    st.subheader("数据适配结果")
    uncertain = [item for item in adapter["schema_mapping"] if item["needs_confirmation"]]
    if uncertain:
        st.info("该字段语义无法可靠确定，请人工确认；不确认则仅做通用统计与IQR，不套用专业阈值。")
        with st.expander("人工确认字段语义（仅当前会话，不修改原始CSV）"):
            for item in uncertain:
                choice = st.selectbox(
                    f"{item['source_column']} → 标准语义",
                    ["暂不确认", "保持通用数值字段", *CANONICAL_NAMES],
                    key=f"schema_{dataset_fingerprint}_{item['source_column']}",
                )
                if choice == "保持通用数值字段":
                    schema_confirmations[item["source_column"]] = None
                elif choice in CANONICAL_NAMES:
                    schema_confirmations[item["source_column"]] = choice
    adapter = describe_dataset(dataframe, confirmations=schema_confirmations)
    if not adapter["semantic_columns"]:
        st.info("未识别到本项目支持的网络监测语义字段。请使用项目支持的标准字段或兼容别名，并检查数据字段说明。Generic Analysis仍然可以使用。")
    st.dataframe(pd.DataFrame(adapter["schema_mapping"]).rename(columns={
        "source_column": "原始字段", "dtype": "类型", "canonical_name": "推测/确认语义",
        "unit": "已知单位", "confidence": "置信度", "needs_confirmation": "需要确认",
        "semantic_enabled": "参与专业分析", "mapping_source": "映射来源", "analysis_type": "分析级别", "warnings": "复核提示",
    }), width="stretch", hide_index=True)
    st.caption("语义确认不等于单位确认；未知单位不换算、不套用固定阈值。未识别字段只能进入通用分析。")

    st.subheader("数据预览")
    preview_rows = st.slider("预览行数", min_value=5, max_value=50, value=10, step=5)
    st.dataframe(dataframe.head(preview_rows), width="stretch")

    st.subheader("数据基本信息")
    summary = build_data_summary(dataframe)
    metric_columns = st.columns(5)
    metric_columns[0].metric("数据行数", summary["row_count"])
    metric_columns[1].metric("字段数", summary["column_count"])
    metric_columns[2].metric("数值字段", summary["numeric_column_count"])
    metric_columns[3].metric("缺失值", summary["missing_value_count"])
    metric_columns[4].metric("重复行", summary["duplicate_row_count"])

    dtype_table = pd.DataFrame(
        {
            "字段": dataframe.columns,
            "类型": dataframe.dtypes.astype(str).values,
            "缺失值": dataframe.isna().sum().values,
        }
    )
    st.dataframe(dtype_table, width="stretch", hide_index=True)

    numeric_columns = get_numeric_columns(dataframe)
    if numeric_columns:
        with st.expander("数值字段描述性统计"):
            st.dataframe(dataframe[numeric_columns].describe(), width="stretch")

        with st.expander("通用数值统计（含中位数与 P95，不代表已确认网络语义）"):
            network_statistics = calculate_numeric_statistics(dataframe)
            st.dataframe(
                pd.DataFrame.from_dict(network_statistics, orient="index"),
                width="stretch",
            )

        st.subheader("指标趋势图")
        default_columns = [
            column
            for column in ["latency_ms", "packet_loss_pct"]
            if column in numeric_columns
        ] or numeric_columns[:1]
        selected_columns = st.multiselect(
            "选择要绘制的数值列",
            options=numeric_columns,
            default=default_columns,
            help="可同时选择多个指标；不同量纲会共用同一纵轴。",
        )
        x_axis_options = ["数据行序号"] + dataframe.columns.tolist()
        default_x_index = (
            x_axis_options.index("timestamp")
            if "timestamp" in dataframe.columns
            else 0
        )
        selected_x = st.selectbox(
            "选择横轴",
            options=x_axis_options,
            index=default_x_index,
        )

        if selected_columns:
            figure = create_trend_figure(
                dataframe,
                selected_columns,
                None if selected_x == "数据行序号" else selected_x,
            )
            st.plotly_chart(figure, width="stretch")
        else:
            st.warning("请至少选择一个数值列后再绘图。")
    else:
        st.warning("当前数据不包含数值列，无法生成趋势图。")

    st.subheader("异常分析")
    analysis_mode_label = st.radio("分析模式", ["Semantic Network Analysis（语义网络分析）", "Generic Analysis（通用数值分析）"],
                                   index=0 if adapter["semantic_columns"] else 1)
    analysis_mode = "generic" if analysis_mode_label.startswith("Generic") else "semantic"
    supported_metrics = adapter["generic_numeric_columns"] if analysis_mode == "generic" else adapter["semantic_columns"]
    if supported_metrics:
        selected_analysis_metrics = st.multiselect(
            "选择异常检测指标",
            options=supported_metrics,
            default=supported_metrics,
        )
        _, selected_thresholds = prepare_analysis(dataframe, adapter, selected_analysis_metrics or supported_metrics, analysis_mode, settings=active_detection_settings)
        iqr_required = any(not rule for rule in selected_thresholds.values())
        use_iqr = st.checkbox("同时使用 IQR 统计规则", value=True, disabled=iqr_required)
        if iqr_required:
            st.caption("通用字段或未知单位只使用IQR；统计异常不等于已确认网络故障。IQR为0或有效样本不足时跳过该规则。")
        anomaly_result = (analyze_anomalies(dataframe, adapter, selected_analysis_metrics,
                                           mode=analysis_mode, use_iqr=True if iqr_required else use_iqr, settings=active_detection_settings)
                          if selected_analysis_metrics else {"anomaly_count": 0, "anomalous_row_count": 0, "anomalies": []})

        anomaly_metrics = st.columns(2)
        anomaly_metrics[0].metric("异常记录数", anomaly_result["anomaly_count"])
        anomaly_metrics[1].metric(
            "异常时间点/行数", anomaly_result["anomalous_row_count"]
        )

        if anomaly_result["anomalies"]:
            anomaly_table = pd.DataFrame(anomaly_result["anomalies"]).rename(
                columns={
                    "row_index": "行索引",
                    "timestamp": "异常时间点",
                    "metric": "异常指标",
                    "value": "实际值",
                    "trigger_rule": "触发规则",
                    "explanation": "异常原因",
                }
            )
            st.dataframe(anomaly_table, width="stretch", hide_index=True)
        elif selected_analysis_metrics:
            st.success("当前规则未检测到异常。")
        else:
            st.info("请选择至少一个指标进行异常检测。")

        with st.expander("当前固定阈值"):
            threshold_rows = [
                {
                    "指标": metric,
                    "下限": rule.get("min"),
                    "上限": rule.get("max"),
                }
                for metric, rule in selected_thresholds.items()
            ]
            st.dataframe(threshold_rows, width="stretch", hide_index=True)
    else:
        st.info(
            "当前模式没有可用指标。未知字段可切换到Generic Analysis，或先人工确认语义。"
        )

st.divider()
st.subheader("智能故障诊断 Agent")
agent_config_status = get_agent_config_status()
configured_model = agent_config_status.get("model") or SUPPORTED_MODELS["DeepSeek Flash"]
model_options = list(SUPPORTED_MODELS.values())
if configured_model not in model_options:
    model_options.insert(0, configured_model)
selected_model = st.selectbox("诊断模型", options=model_options, index=model_options.index(configured_model),
                              format_func=lambda model: next((label for label, value in SUPPORTED_MODELS.items() if value == model), f"不支持的环境配置：{model}"),
                              key="diagnosis_model")
st.caption("Flash适合快速分析；V4 Pro适合更复杂诊断，实际可用性和费用以服务商账户为准。")
if selected_model not in SUPPORTED_MODELS.values():
    st.warning("环境配置的模型不受支持，请选择列表中的DeepSeek模型。")
if agent_config_status["configured"]:
    st.info(
        "API 配置已就绪，但尚未验证。只有本次 API 调用成功后，"
        "结果才会标记为“真实 Agent 模式”。"
    )
    st.caption(
        f"当前选择：{selected_model}｜"
        "API Key：已配置"
    )
else:
    missing_variables = [
        name
        for name, configured in agent_config_status["variables"].items()
        if not configured
    ]
    st.warning(
        "模型API尚未配置，数据分析功能仍可使用，但Agent诊断功能不可用。"
        "缺少：" + "、".join(missing_variables) + "。请在本地.env或平台Secrets中配置。"
    )

st.caption("页面不会在配置缺失或调用失败时自动切换为模拟模式。")
agent_task = st.text_area(
    "自然语言诊断任务",
    placeholder="例如：分析当前网络数据的主要异常，并给出按优先级排列的排查步骤。",
    max_chars=2000,
)
start_diagnosis = st.button(
    "开始诊断",
    type="primary",
    disabled=not agent_config_status["configured"] or dataframe is None or selected_model not in SUPPORTED_MODELS.values(),
)

dataset_signature = (
    data_source,
    dataset_fingerprint,
    tuple(sorted(schema_confirmations.items())),
    selected_model,
    tuple(sorted(active_detection_settings["thresholds"].items())),
    active_detection_settings["iqr_multiplier"],
)
if start_diagnosis:
    if not agent_task.strip():
        st.error("请输入诊断任务。")
    else:
        try:
            with st.spinner("Agent 正在选择并执行分析工具……"):
                agent_result = run_diagnosis(dataframe, agent_task, schema_confirmations=schema_confirmations,
                                             model_override=selected_model, detection_settings=active_detection_settings)
            st.session_state["agent_diagnosis"] = {
                "dataset_signature": dataset_signature,
                "result": agent_result,
            }
        except (AgentConfigurationError, AgentExecutionError) as exc:
            st.session_state.pop("agent_diagnosis", None)
            st.error(str(exc))
        except Exception:
            st.session_state.pop("agent_diagnosis", None)
            st.error("诊断服务暂时不可用，请稍后重试；本次不会自动重试。")

saved_diagnosis = st.session_state.get("agent_diagnosis")
if (
    saved_diagnosis
    and saved_diagnosis["dataset_signature"] == dataset_signature
):
    result = saved_diagnosis["result"]
    st.success(
        f"真实 Agent 模式：API 调用成功，模型 {result['model']}，"
        f"执行工具 {result['tool_calls_executed']} 次。"
    )
    st.markdown("#### 实际工具调用记录")
    for index, record in enumerate(result["tool_records"], start=1):
        with st.expander(
            f"{index}. {record['tool']}（{record['status']}）"
        ):
            st.json(
                {
                    "order": record.get("order", index),
                    "success": record.get("success", record["status"] == "ok"),
                    "input_summary": record.get("input_summary", record["arguments"]),
                    "output_summary": record.get("output_summary"),
                    "arguments": record["arguments"],
                    "result": record["result"],
                }
            )
    st.markdown("#### 最终诊断报告")
    st.markdown(result["report"])
    with st.expander("【证据链】数据事实 → 工具检测 → 参考知识 → 模型推断 → 不确定性"):
        st.json(result.get("evidence_chain", {}))
    st.markdown("#### 参考知识与来源")
    knowledge_references = result.get("knowledge_references", [])
    if knowledge_references:
        for reference in knowledge_references:
            with st.expander(reference["title"]):
                st.markdown("**相关排查建议**")
                for step in reference["troubleshooting_steps"]:
                    st.markdown(f"- {step}")
                source = reference["source"]
                verification = "已核实" if source["verified"] else "待核实"
                st.markdown(f"**来源：** {source['name']}（{verification}）")
                st.link_button("打开来源", source["url"])
                st.caption(f"局限：{reference['limitations']}")
    elif result.get("knowledge_search_performed"):
        st.info("本地知识库中没有匹配条目，本次报告未引用外部来源。")
    else:
        st.caption("本次任务未调用知识检索工具。")
