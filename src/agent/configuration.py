"""部署配置兼容：系统环境/.env优先，缺少时读取Streamlit Secrets。"""

import os


CONFIG_NAMES = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")


def read_llm_settings() -> dict[str, str]:
    values = {name: os.getenv(name, "").strip() for name in CONFIG_NAMES}
    if all(values.values()):
        return values
    try:
        import streamlit as st
        from streamlit.errors import StreamlitSecretNotFoundError

        try:
            secrets = {name: st.secrets.get(name, "") for name in CONFIG_NAMES}
        except (FileNotFoundError, KeyError, StreamlitSecretNotFoundError):
            secrets = {}
    finally:
        # Streamlit加载根级Secrets时会导出环境变量；恢复原有非空配置优先级。
        for name, value in values.items():
            if value:
                os.environ[name] = value
    for name in CONFIG_NAMES:
        if not values[name] and isinstance(secrets.get(name), str):
            values[name] = secrets[name].strip()
    return values
