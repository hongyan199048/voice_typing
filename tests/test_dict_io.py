"""词典导入 / 导出自检：往返一致、带逗号的易错词、表头、纯文本、GBK、去重。

运行: python3 tests/test_dict_io.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_typing.core.vocabulary import export_vocab_csv, import_vocab_csv


def _tmp(name, data: bytes):
    path = os.path.join(tempfile.mkdtemp(), name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def test_round_trip():
    vocab = [{"term": "Claude Code", "alias": "cloud code, 克劳德"}, {"term": "CUDA", "alias": ""}]
    path = os.path.join(tempfile.mkdtemp(), "dict.csv")
    export_vocab_csv(vocab, path)
    assert import_vocab_csv(path) == vocab


def test_plain_text_one_term_per_line():
    path = _tmp("words.txt", "Mid360\nROS2\n\n  costmap  \n".encode("utf-8"))
    assert import_vocab_csv(path) == [
        {"term": "Mid360", "alias": ""}, {"term": "ROS2", "alias": ""}, {"term": "costmap", "alias": ""}]


def test_gbk_from_excel_and_dedup():
    path = _tmp("excel.csv", "词汇,易错词\r\n激光雷达,激光雷打\r\n激光雷达,重复\r\n".encode("gbk"))
    assert import_vocab_csv(path) == [{"term": "激光雷达", "alias": "激光雷打"}]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
