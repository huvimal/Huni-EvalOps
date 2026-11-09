"""Offline candidate used to demonstrate a reproducible release check."""


def classify(text):
    text = text.casefold()
    if "người lạ" in text or "mật khẩu" in text or "đăng nhập" in text:
        return {"category": "account", "urgent": "người lạ" in text}
    if "giao hàng" in text or "kiện hàng" in text:
        return {"category": "delivery", "urgent": False}
    if "tiền hoàn" in text or "hoàn tiền" in text:
        return {"category": "refund", "urgent": False}
    return {"category": "other", "urgent": False}
