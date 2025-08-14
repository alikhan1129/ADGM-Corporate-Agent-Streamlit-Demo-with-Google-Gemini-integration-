import re


def classify_doc_type(text: str) -> str:
    text_l = text.lower()
    # handle common abbreviations and variants
    if re.search(r"\b(aoa|articles of association|article of association)\b", text_l):
        return "Articles of Association"
    if re.search(r"\b(moa|memorandum of association|memorandum)\b", text_l):
        return "Memorandum of Association"
    if re.search(r"\b(ubo|ultimate beneficial owner|ultimate beneficial owner declaration)\b", text_l):
        return "UBO Declaration Form"
    if re.search(r"\b(register of members and directors|register of members|register of directors)\b", text_l):
        return "Register of Members and Directors"
    if re.search(r"\b(incorporation application|application for incorporation|application to incorporate|incorporation form)\b", text_l):
        return "Incorporation Application Form"
    # short docs — use words rather than characters
    word_count = len([w for w in re.split(r"\s+", text_l) if w.strip()])
    if word_count < 40:
        return "Short Document"
    # fallback - try to detect common contract headings
    if re.search(r"\b(agreement|contract|terms|conditions)\b", text_l):
        return "Commercial Agreement / Other"
    return "Commercial Agreement / Other"


def detect_process(predicted_types) -> str:
    incorporation_keywords = set([
        "Articles of Association", "Memorandum of Association", "Incorporation Application Form", "UBO Declaration Form", "Register of Members and Directors"
    ])
    if not predicted_types:
        return "Unknown / Other"
    count = sum(1 for pt in predicted_types if pt in incorporation_keywords)
    # require at least 2 core docs to infer incorporation process
    if count >= 2:
        return "Company Incorporation"
    return "Unknown / Other"