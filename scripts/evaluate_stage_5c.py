"""仅读取已保存的首次真实记录与独立审阅，计算量化表，不请求API。"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_real_agent_experiment as experiment

OUT = ROOT / "docs" / "experiments"
EXPECTED = {
    "A": ({"overview"}, {"get_dataset_summary"}),
    "B": ({"metrics", "anomaly"}, {"analyze_network_metrics", "detect_anomalies"}),
    "C": ({"anomaly", "diagnostic"}, {"detect_anomalies", "search_fault_knowledge"}),
    "D": ({"uncertainty"}, {"detect_anomalies"}),
}


def main() -> None:
    review = json.loads((OUT / "stage_5c_assessment.json").read_text(encoding="utf-8"))
    rows = {}
    records = {}
    tool_success_count = complete_count = unnecessary_count = 0
    for task_id, (intents, required) in EXPECTED.items():
        record = json.loads((experiment.RECORDS_DIR / f"task_{task_id}.json").read_text(encoding="utf-8"))
        records[task_id] = record
        result = record.get("result") or record.get("trace", {})
        calls = result.get("tool_records", [])
        successful = {call["tool"] for call in calls if call["status"] == "ok"}
        manual = review["tasks"][task_id]
        tools_ok = required <= successful
        relevant = manual["tool_relevance"] == "Pass"
        all_requests = record["status"] == "success" and tools_ok and manual["all_explicit_requests"] == "Pass"
        tool_success_count += int(tools_ok)
        complete_count += int(all_requests)
        unnecessary_count += int(not relevant)
        rows[task_id] = [
            "Pass" if intents <= set(result.get("task_requirements", {}).get("intents", [])) else "Fail",
            manual["tool_relevance"],
            "Pass" if tools_ok else "Fail",
            "Pass" if relevant else "Fail",
            "Pass" if calls and all(call["status"] == "ok" for call in calls) else "Fail",
            manual["data_evidence"],
            ("Pass" if result.get("knowledge_references") else "Fail") if task_id == "C" else "N/A",
            manual["fact_inference_separation"], manual["uncertainty"],
            "Pass" if all_requests else "Fail",
        ]
    criteria = ["任务意图识别正确", "工具组合合理", "必需工具执行", "无明显无关工具调用", "Python工具真实成功", "报告使用真实数据依据", "存在知识来源", "事实与推断区分", "不确定性说明", "明确要求全部满足"]
    lines = ["## 第5C阶段量化评价", "", "数据来源为本轮首次DeepSeek真实记录；任务完成度包含业务约束补齐，不等于纯LLM自主选择成功率。", "技术项从日志计算，语义项由读取原始报告与工具结果后的代码审阅判定，审阅依据见 `stage_5c_assessment.json`。", "Pass=满足本检查项，Fail=不满足，N/A=本任务不要求。无关调用一行Pass表示未发现明显无关调用。", "", "| 检查项 | A | B | C | D |", "|---|---|---|---|---|"]
    for i, criterion in enumerate(criteria):
        lines.append("| " + " | ".join([criterion] + [rows[t][i] for t in EXPECTED]) + " |")
    total = len(records)
    lines += ["", f"- 任务完成率：{complete_count}/{total} = {complete_count/total:.0%}", f"- 必要工具调用正确率：{tool_success_count}/{total} = {tool_success_count/total:.0%}", f"- 无关工具调用率：{unnecessary_count}/{total} = {unnecessary_count/total:.0%}", "", "以上是4个固定任务的一次运行结果，不是统计显著性结论，也不等同于根因诊断准确率。", ""]
    for task_id in EXPECTED:
        manual = review["tasks"][task_id]
        lines += [f"### 任务{task_id}复核依据", "", manual["reason"], "", "局限：" + manual["limitations"], ""]
    metrics_path = OUT / "experiment_2_agent_tool_selection_stage_5c_review.md"
    metrics_path.write_text("\n".join(lines), encoding="utf-8")
    experiment.render()
    d = records["D"]
    d_result = d.get("result") or d.get("trace", {})
    uncertainty_lines = ["# 实验4：不确定性约束验证", "", "DeepSeek真实API运行记录，任务D首次结果。", "", "用户任务：" + d["task"], "", f"状态：{d['status']}；开始时间：{d['started_at']}。", "原始记录：`real_agent_records/stage_5c/task_D.json`。", "", "工具顺序：" + " → ".join(item["tool"] for item in d_result.get("tool_records", [])), "", "## 原始报告", "", d_result.get("report", "未返回报告"), "", "## 复核", "", review["tasks"]["D"]["reason"], "", "本实验支持该任务上的不确定性约束行为，不代表模型对所有措辞均能避免过度断言。", ""]
    (OUT / "experiment_4_uncertainty_validation.md").write_text("\n".join(uncertainty_lines), encoding="utf-8")
    metrics = {"task_count": total, "completed_tasks": complete_count, "required_tool_success_tasks": tool_success_count, "unnecessary_tool_tasks": unnecessary_count, "task_completion_rate": complete_count/total, "required_tool_success_rate": tool_success_count/total, "unnecessary_tool_call_rate": unnecessary_count/total, "checklist": rows}
    (OUT / "stage_5c_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=True))


if __name__ == "__main__":
    main()
