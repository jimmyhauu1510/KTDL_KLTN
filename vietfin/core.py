import csv
import hashlib
import io
import json
import math
import re
import unicodedata
from collections import Counter

ACRONYMS = {"AI", "ML", "NLP", "IoT", "BI", "ERP", "CRM", "RPA", "CNTT", "ICT", "API", "IoT", "IT"}
LABELS = {f"C{i}" for i in range(1, 7)}


def normalize(text):
    """NFC/whitespace normalization, with normalized-char -> original offset map."""
    chars, mapping = [], []
    for match in re.finditer(r"[^\r\n\t\f\v\u00a0\u200b]|[\r\n\t\f\v\u00a0\u200b]", text):
        c, pos = match.group(), match.start()
        if unicodedata.combining(c) and chars:
            composed = unicodedata.normalize("NFC", chars[-1] + c)
            if len(composed) == 1:
                chars[-1] = composed
                continue
        if c.isspace() or c == "\u200b":
            c = " "
            if chars and chars[-1] == " ":
                continue
        if c in "‐‑‒–—−":
            c = "-"
        chars.append(c)
        mapping.append(pos)
    mapping.append(len(text))
    return "".join(chars), mapping


def parse_dictionary(content, filename):
    if filename.lower().endswith(".xlsx"):
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(content), read_only=True, data_only=True).active
        values = iter(ws.values)
        headers = [str(x).strip() for x in next(values)]
        rows = [dict(zip(headers, row)) for row in values if any(x is not None for x in row)]
    else:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    required = {"concept_id", "keyword_name", "concept_group", "category", "terms", "case_sensitive_terms"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("Cần các cột: " + ", ".join(sorted(required)))
    concepts, seen, aliases = [], set(), {}
    for row in rows:
        cid = str(row["concept_id"]).strip()
        if cid in seen:
            raise ValueError(f"Concept ID trùng: {cid}")
        seen.add(cid)
        category = str(row["category"]).strip().upper()
        terms = [normalize(t.strip())[0] for t in str(row["terms"] or "").split(";") if t.strip()]
        sensitive = [t.strip() for t in str(row["case_sensitive_terms"] or "").split(";") if t.strip()]
        if not terms or not str(row["keyword_name"] or "").strip() or not str(row["concept_group"] or "").strip():
            raise ValueError(f"Thiếu tên, nhóm hoặc biến thể: {cid}")
        canonical={term.casefold():term for term in ACRONYMS}
        for term in terms:
            if term.casefold() in canonical and term!=canonical[term.casefold()]:
                raise ValueError(f"Viết tắt phải đúng hoa/thường: {canonical[term.casefold()]} (không dùng {term})")
        if not set(sensitive).issubset(terms):
            raise ValueError(f"case_sensitive_terms phải nằm trong terms: {cid}")
        for term in terms:
            key = term.casefold()
            if key in aliases and aliases[key] != cid:
                raise ValueError(f"Biến thể dùng bởi nhiều ID: {term}")
            aliases[key] = cid
        concepts.append({"concept_id": cid, "keyword_name": str(row["keyword_name"]),
                         "concept_group": str(row["concept_group"]), "category": category,
                         "terms": terms, "case_sensitive_terms": sorted(set(sensitive) | (set(terms) & ACRONYMS))})
    if seen != {f"KW{i:03d}" for i in range(1, 108)}:
        raise ValueError("Dictionary V1.0 phải có đúng KW001–KW107, không thiếu hoặc thêm ID")
    if Counter(c["category"] for c in concepts) != {"CORE": 39, "CONTEXT": 46, "TECH_ONLY": 22}:
        raise ValueError("Phân nhóm phải đúng 39 CORE, 46 CONTEXT, 22 TECH_ONLY")
    return {"version": "DICTIONARY_V1.0", "sha256": hashlib.sha256(content).hexdigest(), "concepts": concepts}


class Matcher:
    def __init__(self, dictionary):
        self.patterns = []
        for concept in dictionary["concepts"]:
            for term in concept["terms"]:
                pattern = r"(?<!\w)" + re.escape(term).replace(r"\ ", r"\s+") + r"(?!\w)"
                flags = 0 if term in concept["case_sensitive_terms"] else re.IGNORECASE
                self.patterns.append((re.compile(pattern, flags), concept))

    def match(self, text):
        candidates = []
        for pattern, concept in self.patterns:
            for m in pattern.finditer(text):
                candidates.append((m.start(), m.end(), concept, m.group()))
        selected = []
        for start, end, concept, term in sorted(candidates, key=lambda x: (-(x[1]-x[0]), x[0], x[2]["concept_id"])):
            if not any(start < e and end > s for s, e, _, _ in selected):
                selected.append((start, end, concept, term))
        return sorted(selected, key=lambda x: x[0])


def context(text, start, end):
    spans = [(m.start(), m.end()) for m in re.finditer(r"[^.!?]+(?:[.!?]+|$)", text)]
    for i, (s, e) in enumerate(spans):
        if s <= start < e:
            return text[s:e].strip(), text[spans[max(0, i-1)][0]:spans[min(len(spans)-1, i+1)][1]].strip()
    return text[start:end], text


def suggest_label(sentence):
    rules = [
        ("C5", r"chưa triển khai|không thực hiện|đình chỉ|chưa ứng dụng"),
        ("C6", r"theo (?:gartner|idc|báo cáo của ngân hàng thế giới)|khái niệm.{0,40}là gì"),
        ("C4", r"khách hàng tự triển khai|đối tác tự triển khai"),
        ("C3", r"đặt mục tiêu|dự kiến|kế hoạch|sẽ triển khai"),
        ("C2", r"cung cấp.{0,80}(?:dịch vụ|giải pháp)|bán.{0,50}(?:nền tảng|phần mềm)"),
        ("C1", r"triển khai.{0,80}nội bộ|ứng dụng.{0,80}nội bộ"),
    ]
    for label, pattern in rules:
        m = re.search(pattern, sentence, re.IGNORECASE)
        if m:
            return label, "Gợi ý quy tắc, cần người duyệt: " + m.group()
    return None, "Chưa đủ bằng chứng xác định chủ thể; cần duyệt"


def metrics(report, dictionary):
    fields = "total_words_full total_words_narr tech_freq tech_unique dt_raw_freq dt_disc_freq dt_unique dt_implement_freq dt_index dt_implement_index dt_per_10000 tech_per_10000 dt_tech_share dt_broad_freq digital_dummy".split()
    out = dict.fromkeys(fields)
    if report.get("document_status") == "MISSING" or not report.get("analysis"):
        return out
    occurrences = report["analysis"]["occurrences"]
    concepts = {c["concept_id"]: c for c in dictionary["concepts"]}
    dt = [o for o in occurrences if concepts[o["concept_id"]]["category"] in {"CORE", "CONTEXT"} and o["concept_id"] != "KW086"]
    disc = [o for o in dt if o.get("qa_reviewed") and o.get("context_label") in {"C1", "C2", "C3"} and o.get("digital_meaning")]
    impl = [o for o in disc if o["context_label"] == "C1"]
    broad = [o for o in occurrences if o["concept_id"] == "KW086" and o.get("qa_reviewed") and o.get("context_label") in {"C1", "C2", "C3"} and o.get("digital_meaning")]
    full = report["analysis"]["total_words_full"]
    if not full:
        out.update(total_words_full=0,total_words_narr=report["analysis"]["total_words_narr"])
        return out
    tech = [o for o in occurrences if not (o.get("qa_reviewed") and o.get("digital_meaning") is False)]
    out.update(total_words_full=full, total_words_narr=report["analysis"]["total_words_narr"], tech_freq=len(occurrences),
               tech_unique=len({o["concept_id"] for o in tech}), dt_raw_freq=len(dt), dt_disc_freq=len(disc),
               dt_unique=len({o["concept_id"] for o in disc}), dt_implement_freq=len(impl), dt_index=math.log1p(len(disc)),
               dt_implement_index=math.log1p(len(impl)), dt_per_10000=10000*len(disc)/full if full else None,
               tech_per_10000=10000*len(tech)/full if full else None,
               dt_tech_share=len(disc)/len(tech) if tech else None,
               dt_broad_freq=len(disc)+len(broad), digital_dummy=int(bool(impl)) if report["document_status"] == "OK" else None)
    out["tech_freq"] = len(tech)
    return out
