"""配置持久化管理，JSON 格式"""

import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/voice_typing")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "engine": "alibaba",            # "alibaba" | "volcengine"
    "alibaba_api_key": "",          # 阿里云 DashScope API Key（ASR + 润色共用）
    "volc_asr_api_key": "",         # 豆包语音控制台 API Key（X-Api-Key，与方舟 Key 独立）
    "volc_asr_resource_id": "volc.seedasr.sauc.duration",  # 豆包流式语音识别 2.0 小时版
    "overlay_style": "glass",       # 浮窗外观：glass / minimal / neon / aurora
    "hotkey": [],                      # 无默认快捷键，首次运行由用户在「设置」中录制
    "first_run": True,
    "custom_vocabulary": [],        # 自定义热词列表：["CUDA", "GitHub", "Python"]
    "phrase_id": "",                # 阿里云热词表ID（UUID，由VocabularyService创建）
    "polish_strength": "medium",    # 润色强度：light / medium / strong
    "polish_provider": "",          # 润色模型：off / deepseek / glm / minimax（空=按已填 Key 推断）
    "realtime_polish": False,       # 录音过程中提前润色（默认关闭，只在最终文本后润色）
    "deepseek_api_key": "",         # DeepSeek API Key
    "glm_api_key": "",              # 智谱 GLM API Key
    "minimax_api_key": "",          # MiniMax API Key
    "doubao_api_key": "",           # 豆包 ARK API Key（旧版润色，保留兼容）
    "doubao_endpoint_id": "",       # 豆包推理接入点 ID（旧版润色，保留兼容）
    "volc_boosting_table_id": "",   # 火山 ASR 热词表 ID（控制台创建，做识别偏置）
    "stats": {
        "total_seconds": 0,          # 累计录音秒数
        "total_characters": 0,       # 累计识别字符数
        "total_sessions": 0,         # 累计录音次数
        "install_date": "",          # 首次使用日期 ISO 格式
    },
    "history": [],                   # [{text, timestamp, engine, chars}, ...] 最近 100 条
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_PATH, "r") as f:
        data = json.load(f)
    # 合并缺失的默认值
    for k, v in DEFAULT_CONFIG.items():
        if k not in data:
            data[k] = v
    # 旧版润色厂商（千问/豆包方舟）已下线，置空以便按已填 Key 重新推断
    if data.get("polish_provider") in ("qwen", "doubao"):
        data["polish_provider"] = ""
    return data


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def build_correct_words(config):
    """从词库构建火山 ASR 内联错词映射 {别名: 正词}（仅对填了别名的词条生效）"""
    mapping = {}
    for item in config.get("custom_vocabulary", []):
        if not isinstance(item, dict):
            continue
        term = item.get("term", "")
        alias_str = item.get("alias", "")
        if not term or not alias_str:
            continue
        for alias in alias_str.split(","):
            alias = alias.strip()
            if alias:
                mapping[alias] = term
    return mapping
