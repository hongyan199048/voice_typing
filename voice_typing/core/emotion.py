"""转写文本 → 头像表情：关键词匹配，取文中最后出现的情绪词（说到哪、表情跟到哪）。

表情名对应头像的 9 种：neutral / happy / surprised / sad / sleepy /
squinted / calm / inspecting / confused。
"""

# ponytail: 纯关键词 + 近距离否定，不懂反讽、长距离否定；要更准再换 LLM 打标签
# 单字词容易误伤（困难→困、麻烦→烦、累计→累），这里一律用双字以上的说法
_KEYWORDS = {
    "happy": ("哈哈", "嘿嘿", "开心", "高兴", "快乐", "幸福", "太好了", "太棒了", "好棒", "喜欢",
              "谢谢", "感谢", "不错", "满意", "舒服", "兴奋", "激动", "期待", "顺利", "成功",
              "好耶", "爽", "厉害", "完美", "牛逼", "太牛", "nice", "cool"),
    "surprised": ("哇", "天哪", "天啊", "居然", "竟然", "卧槽", "真的假的", "没想到", "震惊",
                  "不会吧", "吓死", "吓一跳", "意外", "wow"),
    "sad": ("难过", "伤心", "遗憾", "可惜", "唉", "想哭", "哭了", "失望", "抱歉", "对不起",
            "糟糕", "完蛋", "郁闷", "不好", "不太好", "不怎么好", "心情差", "难受", "痛苦",
            "崩溃", "委屈", "失落", "沮丧", "焦虑", "压力大", "担心", "倒霉", "心累", "emo"),
    "sleepy": ("好困", "困了", "犯困", "困死", "好累", "太累", "累了", "累死", "睡觉", "晚安",
               "疲惫", "没精神", "打哈欠"),
    "squinted": ("生气", "烦死", "好烦", "烦人", "心烦", "讨厌", "气死", "无语", "怀疑", "不爽",
                 "离谱", "恼火", "火大", "受不了", "恶心", "什么玩意"),
    "confused": ("为什么", "为啥", "怎么回事", "不懂", "不明白", "搞不懂", "搞不清", "奇怪",
                 "什么鬼", "啥意思", "怎么办", "是不是"),
    "inspecting": ("看看", "检查", "分析", "研究", "确认一下", "查一下"),
    "calm": ("好的", "没问题", "放心", "慢慢来", "不着急", "可以的"),
}

# 情绪词前 _NEG_WINDOW 个字内出现否定词时意思反转：不开心 → sad，不难过 → calm
# 不收「别」：特别 / 区别 / 别人太常见，「心情特别不好」会被误判成反转
_NEGATIONS = ("不", "没")
_NEG_WINDOW = 4
_NEGATED = {"happy": "sad", "calm": "sad", "sad": "calm", "squinted": "calm", "sleepy": "neutral"}


def detect_emotion(text: str) -> str:
    """返回最后出现的情绪词所属表情（同一位置结束取更长的词）；没有命中返回 neutral"""
    text = text.lower()
    best, best_key = "neutral", (-1, 0)
    for emotion, words in _KEYWORDS.items():
        for word in words:
            pos = text.rfind(word)
            if pos < 0:
                continue
            key = (pos + len(word), len(word))
            if key > best_key:
                before = text[max(0, pos - _NEG_WINDOW):pos]
                negated = any(n in before for n in _NEGATIONS) and emotion in _NEGATED
                best, best_key = (_NEGATED[emotion] if negated else emotion), key
    return best
