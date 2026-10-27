"""只做离线安全检查和白名单打包，不登录、推送、读取真实密钥或调用API。"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".idea", "__pycache__", ".pytest_cache", ".venv", "venv", "dist"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".txt", ".log", ".csv", ".toml", ".ini", ".yml", ".yaml", ".xml", ".example"}
KEY_PATTERN = re.compile(
    r"sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|LLM_API_KEY\s*=\s*[\"']?[A-Za-z0-9_-]{20,}"
)
WINDOWS_PATH = re.compile(r"\b[A-Za-z]:[\\/]")


def secret_container(path: Path) -> bool:
    name = path.name.casefold()
    return ((name == ".env" or name.startswith(".env.")) and name != ".env.example") or (
        name.startswith("secrets") and name.endswith(".toml")
    )


def audit() -> dict:
    findings, absolute_paths, scanned = [], [], 0
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in relative.parts) or not path.is_file() or path.is_symlink() or secret_container(path):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".gitignore", ".env.example"}:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        scanned += 1
        for number, line in enumerate(text.splitlines(), 1):
            if KEY_PATTERN.search(line):
                findings.append({"file": relative.as_posix(), "line": number, "type": "potential_secret"})
            if path.suffix == ".py" and (relative.parts[0] == "src" or path.name == "app.py") and WINDOWS_PATH.search(line):
                absolute_paths.append({"file": relative.as_posix(), "line": number})
    return {"scanned_text_files": scanned, "potential_secrets": findings,
            "business_windows_paths": absolute_paths,
            "secret_files_read": False,
            "git_history": "本地未建立Git历史，远程历史需人工核实" if not (ROOT / ".git").exists() else "存在本地仓库，历史必须另行核验后再提交",
            "limitations": "规则扫描不能证明不存在所有形式的秘密；提交前仍需审阅变更。"}


def deployment_files() -> list[Path]:
    files = [ROOT / name for name in ("app.py", "requirements.txt", "README.md", ".gitignore", ".env.example", "pytest.ini")]
    for folder in ("src", "tests", "scripts"):
        files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file()
                     and p.suffix == ".py" and not p.is_symlink() and not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts))
    files.extend(ROOT / name for name in (
        "config/.gitkeep", "data/demo/synthetic_network.csv", "data/knowledge/network_faults.json",
        ".streamlit/config.toml", ".streamlit/secrets.toml.example",
        "docs/demo_prompts.md", "docs/deployment_validation.md", "docs/adaptive_data_ingestion.md",
        "docs/dataset_feasibility.md", "docs/stage_5e_pytest.txt", "docs/stage_5e_pytest.xml",
        "docs/stage_6_pytest.txt", "docs/stage_6_pytest.xml", "docs/stage_6_security_check.json",
    ))
    return sorted({p for p in files if p.is_file() and not secret_container(p)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="检查通过后生成新的GitHub上传目录和ZIP")
    args = parser.parse_args()
    result = audit()
    # 只输出文件和行号，不输出匹配内容、密钥或完整环境变量。
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["potential_secrets"] or result["business_windows_paths"]:
        raise SystemExit("安全检查有待复核项，停止打包。")
    if not args.build:
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    staging = ROOT / "dist" / f"github_upload_{stamp}"
    staging.mkdir(parents=True, exist_ok=False)
    archive = ROOT / "dist" / f"netdiag_deploy_{stamp}.zip"
    manifest = []
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in deployment_files():
            relative = path.relative_to(ROOT)
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            bundle.write(path, relative.as_posix())
            manifest.append({"path": relative.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    print(json.dumps({"staging": staging.relative_to(ROOT).as_posix(), "archive": archive.relative_to(ROOT).as_posix(),
                      "files": len(manifest), "manifest": manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
