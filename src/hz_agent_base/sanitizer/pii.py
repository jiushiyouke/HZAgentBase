"""PII 检测和遮盖 — 正则模式和遮盖函数。"""

from __future__ import annotations

import re

# PII 正则模式
PII_PATTERNS = {
    "phone": re.compile(r"1[3-9]\d{9}"),
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "id_card": re.compile(r"\d{17}[\dXx]"),
    "bank_card": re.compile(r"\d{16,19}"),
}


def mask_phone(text: str) -> str:
    """遮盖手机号：138****5678。"""
    def replace(m):
        s = m.group()
        return s[:3] + "****" + s[-4:]
    return PII_PATTERNS["phone"].sub(replace, text)


def mask_email(text: str) -> str:
    """遮盖邮箱：t***@example.com。"""
    def replace(m):
        s = m.group()
        local, domain = s.split("@", 1)
        if len(local) <= 1:
            return "*" + "@" + domain
        return local[0] + "***@" + domain
    return PII_PATTERNS["email"].sub(replace, text)


def mask_id_card(text: str) -> str:
    """遮盖身份证号：110***********1234。"""
    def replace(m):
        s = m.group()
        return s[:3] + "***********" + s[-4:]
    return PII_PATTERNS["id_card"].sub(replace, text)


def mask_bank_card(text: str) -> str:
    """遮盖银行卡号：6222 **** **** 1234。"""
    def replace(m):
        s = m.group()
        if len(s) <= 4:
            return s
        return s[:4] + " **** **** " + s[-4:]
    return PII_PATTERNS["bank_card"].sub(replace, text)


# 遮盖函数映射
MASK_FUNCTIONS = {
    "phone": mask_phone,
    "email": mask_email,
    "id_card": mask_id_card,
    "bank_card": mask_bank_card,
}
