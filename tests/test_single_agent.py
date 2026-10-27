from types import SimpleNamespace
import json

import pandas as pd
import pytest

from src.agent import (
    AgentConfig,
    AgentConfigurationError,
    AgentExecutionError,
    run_diagnosis,
)


class FakeResponses:
    def __init__(self, responses: list[object] | None = None, error: Exception | None = None):
        self._responses = list(responses or [])
        self._error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._responses.pop(0)


def _sample_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": ["t1", "t2", "t3", "t4", "t5"],
            "latency_ms": [10.0, 11.0, 12.0, 13.0, 100.0],
        }
    )


def _config() -> AgentConfig:
    return AgentConfig(
        api_key="secret-test-key",
        base_url="https://example.invalid/v1",
        model="test-model",
    )


def test_unconfigured_api_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(variable, raising=False)

    with pytest.raises(AgentConfigurationError, match="LLM_API_KEY"):
        run_diagnosis(_sample_data(), "分析异常")


def test_api_error_is_clear_and_does_not_expose_key() -> None:
    fake_responses = FakeResponses(error=RuntimeError("secret-test-key unavailable"))
    fake_client = SimpleNamespace(responses=fake_responses)

    with pytest.raises(AgentExecutionError) as error:
        run_diagnosis(
            _sample_data(), "分析异常", config=_config(), client=fake_client
        )

    assert "大模型 API 调用失败" in str(error.value)
    assert "secret-test-key" not in str(error.value)


def test_agent_tool_call_flow_uses_two_model_calls_and_real_results() -> None:
    first_response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_dataset_summary",
                arguments="{}",
                call_id="call_summary",
            ),
            SimpleNamespace(
                type="function_call",
                name="analyze_network_metrics",
                arguments='{"metrics":["latency_ms"]}',
                call_id="call_statistics",
            ),
            SimpleNamespace(
                type="function_call",
                name="detect_anomalies",
                arguments=(
                    '{"metrics":["latency_ms"],'
                    '"use_iqr":true,"max_results":5}'
                ),
                call_id="call_anomalies",
            ),
        ],
        output_text="",
    )
    final_report = """## 数据分析摘要
[实际检测结果] 当前数据包含 5 行。
## 检测到的异常
[实际检测结果] 检测到 1 个异常指标记录。
## 相关数据证据
[实际检测结果] latency_ms 最大值为 100。
## 可能的故障原因
[模型推测] 可能存在链路拥塞。
## 建议的排查步骤
检查异常时间点的链路状态。
## 无法确定的结论及其原因
无法确定根因，因为没有设备日志。"""
    second_response = SimpleNamespace(output=[], output_text=final_report)
    fake_responses = FakeResponses([first_response, second_response])
    fake_client = SimpleNamespace(responses=fake_responses)

    result = run_diagnosis(
        _sample_data(), "分析延迟异常", config=_config(), client=fake_client
    )

    assert result["mode"] == "real"
    assert result["model_calls"] == 2
    assert result["tool_calls_executed"] == 3
    assert result["report"] == final_report
    assert len(fake_responses.calls) == 2
    assert "tools" in fake_responses.calls[0]
    assert "tools" not in fake_responses.calls[1]
    assert fake_responses.calls[0]["reasoning"] == {"effort": "none"}
    assert fake_responses.calls[1]["reasoning"] == {"effort": "none"}
    assert fake_responses.calls[1]["max_output_tokens"] == 2000
    second_input = fake_responses.calls[1]["input"]
    tool_outputs = [
        item for item in second_input if isinstance(item, dict) and item.get("type") == "function_call_output"
    ]
    assert len(tool_outputs) == 3
    assert '"anomaly_count": 1' in tool_outputs[2]["output"]
    report_request = second_input[-1]
    assert report_request["role"] == "user"
    for section in (
        "数据分析摘要",
        "检测到的异常",
        "相关数据证据",
        "可能的故障原因",
        "建议的排查步骤",
        "无法确定的结论及其原因",
    ):
        assert f"## {section}" in report_request["content"]


def test_agent_blocks_tool_calls_over_limit() -> None:
    tool_calls = [
        SimpleNamespace(
            type="function_call",
            name="get_dataset_summary",
            arguments="{}",
            call_id=f"call_{index}",
        )
        for index in range(4)
    ]
    first_response = SimpleNamespace(output=tool_calls, output_text="")
    final_report = """## 数据分析摘要
[实际检测结果] 工具调用受到数量限制。
## 检测到的异常
[实际检测结果] 未执行异常检测。
## 相关数据证据
[实际检测结果] 已执行三个数据摘要工具。
## 可能的故障原因
[模型推测] 当前证据不足。
## 建议的排查步骤
重新提交更聚焦的任务。
## 无法确定的结论及其原因
没有异常检测结果，无法判断根因。"""
    second_response = SimpleNamespace(output=[], output_text=final_report)
    fake_responses = FakeResponses([first_response, second_response])

    result = run_diagnosis(
        _sample_data(),
        "汇总当前数据",
        config=_config(),
        client=SimpleNamespace(responses=fake_responses),
    )

    assert result["tool_calls_executed"] == 3
    assert result["tool_records"][3]["status"] == "blocked"
    assert result["tool_records"][3]["result"]["error"]["type"] == (
        "tool_call_limit_exceeded"
    )


def test_incomplete_report_has_clear_error() -> None:
    first_response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                name="get_dataset_summary",
                arguments="{}",
                call_id="call_summary",
            )
        ],
        output_text="",
    )
    incomplete_response = SimpleNamespace(
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        output_text="## 数据分析摘要\n[实际检测结果] 报告被截断。",
    )
    fake_responses = FakeResponses([first_response, incomplete_response])

    with pytest.raises(AgentExecutionError, match="输出长度上限"):
        run_diagnosis(
            _sample_data(),
            "分析延迟异常",
            config=_config(),
            client=SimpleNamespace(responses=fake_responses),
        )


def test_agent_integrates_knowledge_tool_result_into_report() -> None:
    first_response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                name="detect_anomalies",
                arguments=(
                    '{"metrics":["latency_ms"],'
                    '"use_iqr":true,"max_results":5}'
                ),
                call_id="call_anomalies",
            ),
            SimpleNamespace(
                type="function_call",
                name="search_fault_knowledge",
                arguments='{"query":"latency_ms 延迟升高 排查建议"}',
                call_id="call_knowledge",
            ),
        ],
        output_text="",
    )
    final_report = """## 数据分析摘要
[实际检测结果] 已分析延迟指标。
## 检测到的异常
[实际检测结果] 检测到延迟异常。
## 相关数据证据
[实际检测结果] 工具返回了异常记录。
## 可能的故障原因
[参考知识] RFC 7679 提供时延测量背景；[模型推测] 可能存在排队。
## 建议的排查步骤
[参考知识] 先比较历史基线，再核对丢包和队列。
## 无法确定的结论及其原因
[模型推测] 缺少路径和设备日志，无法确认根因。"""
    second_response = SimpleNamespace(output=[], output_text=final_report)
    fake_responses = FakeResponses([first_response, second_response])

    result = run_diagnosis(
        _sample_data(),
        "分析延迟异常原因并给出排查建议",
        config=_config(),
        client=SimpleNamespace(responses=fake_responses),
    )

    assert result["knowledge_search_performed"] is True
    assert result["knowledge_references"][0]["id"] == "latency-high"
    assert "[参考知识]" in result["report"]
    assert result["tool_calls_executed"] == 2
    knowledge_outputs = [
        item
        for item in fake_responses.calls[1]["input"]
        if isinstance(item, dict)
        and item.get("type") == "function_call_output"
        and "RFC 7679" in item.get("output", "")
    ]
    assert len(knowledge_outputs) == 1
    record = result["tool_records"][1]
    assert record["evidence_from_orders"] == [1]
    assert record["effective_arguments"]["query"].startswith("latency_ms ")
    evidence = result["evidence_chain"]
    assert evidence["observations"][0]["facts"]["anomalous_row_count"] == 1
    assert evidence["knowledge_evidence"][0]["source"]["url"].startswith("https://")
    assert evidence["inferences"][0]["type"] == "model_inference"
    assert "inferences" not in evidence["observations"][0]
    assert "无法确认根因" in evidence["uncertainties"][0]
    json.dumps(evidence, ensure_ascii=False, allow_nan=False)


def _overview_report() -> str:
    return """## 数据分析摘要
[实际检测结果] 当前数据5行。
## 检测到的异常
未执行异常检测。
## 相关数据证据
[实际检测结果] 数据摘要工具返回5行。
## 可能的故障原因
[模型推测] 当前任务不涉及根因诊断。
## 建议的排查步骤
如有诊断需求请补充设备日志并人工复核。
## 无法确定的结论及其原因
无法确认根因，需要链路利用率和接口队列信息。"""


def test_overview_runs_only_model_selected_tool() -> None:
    responses = FakeResponses([
        SimpleNamespace(output=[SimpleNamespace(type="function_call", name="get_dataset_summary", arguments="{}", call_id="summary")]),
        SimpleNamespace(output=[], output_text=_overview_report()),
    ])
    trace = {}
    result = run_diagnosis(_sample_data(), "概览规模和字段", config=_config(), client=SimpleNamespace(responses=responses), execution_trace=trace)
    assert [record["tool_name"] for record in result["tool_records"]] == ["get_dataset_summary"]
    assert result["tool_calls_executed"] == 1
    assert result["evidence_chain"]["knowledge_evidence"] == []
    assert result["tool_records"][0]["output_summary"]["row_count"] == 5
    assert trace["report"] == result["report"]


def test_knowledge_without_prior_detection_is_not_executed() -> None:
    responses = FakeResponses([
        SimpleNamespace(output=[SimpleNamespace(type="function_call", name="search_fault_knowledge", arguments='{"query":"latency_ms"}', call_id="knowledge")]),
        SimpleNamespace(output=[], output_text=_overview_report()),
    ])
    result = run_diagnosis(_sample_data(), "解释异常", config=_config(), client=SimpleNamespace(responses=responses))
    assert result["tool_records"][0]["result"]["error"]["type"] == "evidence_required"
    assert result["knowledge_references"] == []
    assert result["tool_calls_executed"] == 0


def test_report_without_root_cause_uncertainty_is_rejected_and_traced() -> None:
    responses = FakeResponses([
        SimpleNamespace(output=[SimpleNamespace(type="function_call", name="get_dataset_summary", arguments="{}", call_id="summary")]),
        SimpleNamespace(output=[], output_text=_overview_report().replace("无法确认根因", "已确认根因")),
    ])
    trace = {}
    with pytest.raises(AgentExecutionError, match="未说明无法确认根因"):
        run_diagnosis(_sample_data(), "概览", config=_config(), client=SimpleNamespace(responses=responses), execution_trace=trace)
    assert len(trace["tool_records"]) == 1
    assert len(trace["model_records"]) == 2
    assert "已确认根因" in trace["report"]


def test_root_cause_uncertainty_accepts_equivalent_wording() -> None:
    responses = FakeResponses([
        SimpleNamespace(output=[SimpleNamespace(type="function_call", name="get_dataset_summary", arguments="{}", call_id="summary")]),
        SimpleNamespace(output=[], output_text=_overview_report().replace("无法确认根因", "无法确认任何根因")),
    ])
    result = run_diagnosis(_sample_data(), "数据基本情况", config=_config(), client=SimpleNamespace(responses=responses))
    assert result["success"] is True


def test_missing_knowledge_is_completed_from_actual_detection() -> None:
    responses = FakeResponses([
        SimpleNamespace(output=[SimpleNamespace(type="function_call", name="detect_anomalies", arguments='{"metrics":["latency_ms"],"use_iqr":true,"max_results":5}', call_id="detection")]),
        SimpleNamespace(output=[], output_text=_overview_report().replace("## 可能的故障原因", "[参考知识] RFC 7679 提供时延测量参考。\n## 可能的故障原因")),
    ])
    result = run_diagnosis(_sample_data(), "分析异常原因并检索知识和排查建议", config=_config(), client=SimpleNamespace(responses=responses))
    assert [record["tool"] for record in result["tool_records"]] == ["detect_anomalies", "search_fault_knowledge"]
    assert result["tool_records"][1]["origin"] == "requirement_guard"
    assert result["tool_records"][1]["effective_arguments"]["query"] == "latency_ms 网络异常"
    assert result["task_completion"]["complete"] is True
    assert result["evidence_chain"]["knowledge_evidence"][0]["detection_orders"] == [1]
    assert len(responses.calls) == 2


def test_completion_does_not_exceed_three_calls() -> None:
    responses = FakeResponses([
        SimpleNamespace(output=[SimpleNamespace(type="function_call", name="get_dataset_summary", arguments="{}", call_id=f"summary_{i}") for i in range(3)]),
        SimpleNamespace(output=[], output_text=_overview_report()),
    ])
    result = run_diagnosis(_sample_data(), "检索故障知识并给出排查建议", config=_config(), client=SimpleNamespace(responses=responses))
    assert len(result["tool_records"]) == 3
    assert result["task_completion"]["complete"] is False
    assert "知识检索未完成" in result["report"]


def test_uncertainty_task_does_not_force_knowledge() -> None:
    responses = FakeResponses([
        SimpleNamespace(output=[SimpleNamespace(type="function_call", name="detect_anomalies", arguments='{"metrics":["latency_ms"],"use_iqr":true,"max_results":5}', call_id="detection")]),
        SimpleNamespace(output=[], output_text=_overview_report()),
    ])
    result = run_diagnosis(_sample_data(), "能否确定网络异常的唯一根因？如果不能，请说明还需要哪些额外数据。", config=_config(), client=SimpleNamespace(responses=responses))
    assert result["task_requirements"]["knowledge_required"] is False
    assert result["task_completion"]["complete"] is True
    assert len(result["tool_records"]) == 1
