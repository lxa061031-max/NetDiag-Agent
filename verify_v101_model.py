"""每个模型仅首次运行一次；结果独占创建，失败也保留，不打印密钥。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.agent import AgentConfig, run_diagnosis
from src.agent.configuration import validate_model_override

PROMPT = "请检查当前数据是否异常，并依据数据说明不能确定的结论。"
parser = argparse.ArgumentParser()
parser.add_argument("--choice", choices=["default", "pro"], required=True)
args = parser.parse_args()
out_path = ROOT / "docs" / "experiments" / f"v101_model_{args.choice}.json"
record = {"choice": args.choice, "status": "started", "mode": "real_api", "prompt": PROMPT,
          "started_at_utc": datetime.now(timezone.utc).isoformat()}
with out_path.open("x", encoding="utf-8") as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
trace = {}
try:
    config = AgentConfig.from_environment()
    url = urlparse(config.base_url)
    if url.scheme != "https" or url.hostname != "api.deepseek.com" or url.username or url.password:
        raise ValueError("仅允许 DeepSeek 官方HTTPS地址。")
    model = config.model if args.choice == "default" else "deepseek-v4-pro"
    validate_model_override(model)
    record["model"] = model
    result = run_diagnosis(pd.read_csv(ROOT / "data/demo/synthetic_network.csv"), PROMPT,
                           config=config, model_override=model, execution_trace=trace)
    record.update(status="success", tool_records=result["tool_records"],
                  model_records=result["model_records"], report=result["report"],
                  evidence_chain=result["evidence_chain"])
except Exception as exc:
    cause = exc.__cause__
    record.update(status="failed", error_type=type(exc).__name__,
                  error_message=str(exc) if type(exc).__name__ in {"AgentConfigurationError", "AgentExecutionError"} else "配置或执行失败；未记录异常正文。",
                  cause_type=type(cause).__name__ if cause else None,
                  http_status=getattr(cause, "status_code", None),
                  tool_records=trace.get("tool_records", []), model_records=trace.get("model_records", []))
record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
print(json.dumps({"choice": args.choice, "model": record.get("model"), "status": record["status"],
                  "error_type": record.get("error_type"), "cause_type": record.get("cause_type"),
                  "http_status": record.get("http_status"), "tool_count": len(record["tool_records"]),
                  "report_generated": bool(record.get("report"))}, ensure_ascii=False))
