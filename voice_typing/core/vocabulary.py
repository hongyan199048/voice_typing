"""热词表管理 — 通过 DashScope VocabularyService 创建/更新 phrase_id；词典导入 / 导出"""

import csv

import dashscope
from dashscope.audio.asr import VocabularyService, VocabularyServiceException


def sync_vocabulary(api_key: str, hotwords: list, phrase_id: str = None) -> str | None:
    """
    同步热词表：创建或更新，返回 phrase_id。

    Args:
        api_key: DashScope API Key
        hotwords: 热词列表 ["CUDA", "GitHub", ...]
        phrase_id: 已有的 phrase_id，如果有则更新，否则新建

    Returns:
        新的或更新后的 phrase_id，失败返回 None
    """
    if not api_key or not hotwords:
        return None

    dashscope.api_key = api_key
    service = VocabularyService()

    # 构建热词字典（API需要的格式），weight: 1-5，5为最强
    vocabulary = [{"text": word, "weight": 5} for word in hotwords]

    try:
        if phrase_id:
            # 已有热词表，更新
            service.update_vocabulary(phrase_id, vocabulary)
            return phrase_id
        else:
            # 新建热词表
            new_id = service.create_vocabulary(
                target_model="paraformer-realtime-v2",
                prefix="vt",  # voice_typing 缩写
                vocabulary=vocabulary,
            )
            return new_id
    except VocabularyServiceException as e:
        # 如果旧的 phrase_id 失效，创建新的
        if phrase_id:
            try:
                new_id = service.create_vocabulary(
                    target_model="paraformer-realtime-v2",
                    prefix="vt",
                    vocabulary=vocabulary,
                )
                return new_id
            except VocabularyServiceException:
                pass
        print(f"[热词] 同步失败: {e}")
        return None


# ---- 词典文件：CSV 两列「词汇,易错词」，Excel / WPS 可直接打开编辑 ----

CSV_HEADER = ("词汇", "易错词")


def export_vocab_csv(vocab: list, path: str):
    """vocab: [{"term", "alias"}]。utf-8-sig 带 BOM，Excel 打开中文不乱码"""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for item in vocab:
            writer.writerow((item.get("term", ""), item.get("alias", "")))


def import_vocab_csv(path: str) -> list:
    """读 CSV 或纯文本（一行一个词汇），返回 [{"term", "alias"}]，同名词汇只留第一条。
    先按 UTF-8 读，失败再按 GBK（中文 Windows 上 Excel 另存的 CSV）"""
    for encoding in ("utf-8-sig", "gbk"):
        try:
            with open(path, encoding=encoding, newline="") as f:
                rows = list(csv.reader(f))
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("文件编码无法识别，请另存为 UTF-8 的 CSV")

    result, seen = [], set()
    for row in rows:
        cells = [c.strip() for c in row]
        if not cells or not cells[0] or tuple(cells[:2]) == CSV_HEADER:
            continue
        term = cells[0]
        if term in seen:
            continue
        seen.add(term)
        result.append({"term": term, "alias": cells[1] if len(cells) > 1 else ""})
    return result
