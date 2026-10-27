import json

import pandas as pd

from src.agent.tools import DatasetToolbox


def _sample_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": ["t1", "t2", "t3", "t4", "t5"],
            "latency_ms": [10.0, 11.0, 12.0, 13.0, 100.0],
            "device": ["A", "A", "A", "A", "A"],
        }
    )


def test_tool_parameter_validation() -> None:
    toolbox = DatasetToolbox(_sample_data())

    result = toolbox.execute(
        "analyze_network_metrics", {"metrics": ["missing_metric"]}
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "invalid_parameters"


def test_tools_execute_and_return_json_serializable_results() -> None:
    toolbox = DatasetToolbox(_sample_data())

    summary = toolbox.execute("get_dataset_summary", {})
    statistics = toolbox.execute(
        "analyze_network_metrics", {"metrics": ["latency_ms"]}
    )
    anomalies = toolbox.execute(
        "detect_anomalies",
        {"metrics": ["latency_ms"], "use_iqr": True, "max_results": 5},
    )

    assert summary["result"]["row_count"] == 5
    assert statistics["result"]["statistics"]["latency_ms"]["max"] == 100.0
    assert anomalies["result"]["anomaly_count"] == 1
    json.dumps([summary, statistics, anomalies], ensure_ascii=False, allow_nan=False)


def test_unknown_tool_is_handled_without_execution() -> None:
    result = DatasetToolbox(_sample_data()).execute("run_system_command", {})

    assert result == {
        "ok": False,
        "error": {
            "type": "unknown_tool",
            "message": "未知工具：run_system_command",
        },
    }


def test_knowledge_tool_search_and_invalid_input() -> None:
    toolbox = DatasetToolbox(_sample_data())

    matched = toolbox.execute(
        "search_fault_knowledge", {"query": "latency_ms 延迟异常排查"}
    )
    invalid = toolbox.execute("search_fault_knowledge", {"query": ""})

    assert matched["ok"] is True
    assert matched["result"]["match_count"] >= 1
    assert matched["result"]["results"][0]["source"]["verified"] is True
    assert invalid["ok"] is False
    assert invalid["error"]["type"] == "invalid_parameters"
    json.dumps(matched, ensure_ascii=False, allow_nan=False)
