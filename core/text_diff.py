"""テキスト類似度チェック"""

from constants import TEXT_SIMILARITY_THRESHOLD


def texts_similar(s1: str, s2: str,
                  threshold: float = TEXT_SIMILARITY_THRESHOLD) -> bool:
    """2つの文字列が threshold 以上一致しているか判定"""
    if not s1 or not s2:
        return False
    shorter = min(len(s1), len(s2))
    if shorter == 0:
        return False
    common = sum(c1 == c2 for c1, c2 in zip(s1, s2))
    return common / shorter > threshold
