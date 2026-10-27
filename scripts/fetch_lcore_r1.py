"""获取官方公开R1文件和元数据，不处理API密钥。"""

from urllib.request import Request, urlopen
from pathlib import Path
import json
import hashlib
from datetime import datetime, timedelta, timezone


def get(url: str) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.mendeley-public-dataset.1+json"}), timeout=45) as response:
        return response.read()


if __name__ == "__main__":
    page = get("https://data.mendeley.com/datasets/77sztrg5ks/2").decode()
    state = json.JSONDecoder().raw_decode(page.split("window.INITIAL_STATE = ", 1)[1])[0]
    snapshot = state["dataset"]["snapshot"]
    files_url = "https://data.mendeley.com/public-api/datasets/77sztrg5ks/files?folder_id=root&version=2"
    files = json.loads(get(files_url))
    root = Path(__file__).resolve().parents[1]
    metadata = {key: snapshot[key] for key in ("id", "version", "name", "description", "doi", "licence", "related_links", "custom_metadata")}
    metadata["files_endpoint"] = files_url
    metadata["files"] = files
    metadata["retrieved_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
    folders_url = "https://data.mendeley.com/public-api/datasets/77sztrg5ks/folders/2"
    metadata["folders"] = json.loads(get(folders_url))
    metadata["folder_files"] = {folder["name"]: json.loads(get(
        "https://data.mendeley.com/public-api/datasets/77sztrg5ks/files?folder_id=" + folder["id"] + "&version=2"
    )) for folder in metadata["folders"]}
    selected = next(item for item in files if item["filename"] == "LCORE-D R1.csv")
    path = root / "data/raw" / selected["filename"]
    content = path.read_bytes() if path.exists() else get(selected["content_details"]["download_url"])
    digest = hashlib.sha256(content).hexdigest()
    if digest != selected["content_details"]["sha256_hash"]:
        raise ValueError("R1 SHA-256与官方元数据不一致。")
    if not path.exists():
        path.write_bytes(content)
    metadata["r1_sha256"] = digest
    # 仅检查小型官方故障日志，以核实是否包含标签定义；不分析其他路由器。
    for item in metadata["folder_files"].get("Fault Log", []):
        if item["filename"] == "FAULT_LOG.csv":
            log_path = root / "data/raw/FAULT_LOG.csv"
            log = log_path.read_bytes() if log_path.exists() else get(item["content_details"]["download_url"])
            if hashlib.sha256(log).hexdigest() != item["content_details"]["sha256_hash"]:
                raise ValueError("故障日志哈希不匹配。")
            if not log_path.exists():
                log_path.write_bytes(log)
    (root / "data/raw/lcore_r1_source.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"root_file_count":len(files), "folders":metadata["folders"], "r1_bytes":len(content), "sha256_verified":digest}, ensure_ascii=True))
