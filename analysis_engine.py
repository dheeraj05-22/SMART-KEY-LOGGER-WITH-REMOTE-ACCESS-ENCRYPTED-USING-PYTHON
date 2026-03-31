import re
from collections import Counter

SUSPICIOUS_KEYWORDS = [
    "password", "login", "otp", "bank",
    "credit", "cvv", "pin", "account",
    "username"
]

def analyze_text(text):

    lines = text.splitlines()
    words = re.findall(r"\b\w+\b", text.lower())

    # Basic stats
    total_chars = len(text)
    total_words = len(words)
    total_lines = len(lines)

    word_freq = Counter(words)
    top_words = word_freq.most_common(10)

    # Email detection
    emails = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)

    # URL detection
    urls = re.findall(r"https?://[^\s]+", text)

    # IP detection
    ips = re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text)

    # Suspicious keyword hits
    suspicious_hits = []
    for keyword in SUSPICIOUS_KEYWORDS:
        if keyword in text.lower():
            suspicious_hits.append(keyword)

    return {
        "total_chars": total_chars,
        "total_words": total_words,
        "total_lines": total_lines,
        "top_words": top_words,
        "emails": emails,
        "urls": urls,
        "ips": ips,
        "suspicious_hits": suspicious_hits
    }