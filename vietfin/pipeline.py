import hashlib
import importlib.metadata
import json
import random
import re
from pathlib import Path

import pymupdf
from underthesea import word_tokenize

from .core import Matcher, context, normalize, suggest_label
from .store import now


def tokenizer_info():
    return {"name": "underthesea", "version": importlib.metadata.version("underthesea"),
            "mode": "word_tokenize-default", "filter": "contains-unicode-letter-v1"}


def count_words(text):
    return sum(any(c.isalpha() for c in token) for token in word_tokenize(text))


def extract_pdf(path, tessdata=None):
    import pytesseract
    from PIL import Image
    pages = []
    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("PDF mã hóa: cần bản PDF có thể đọc, không bỏ qua mật khẩu")
        for index, page in enumerate(doc):
            raw = page.get_text(sort=True)
            ocr, error = False, None
            if sum(c.isalpha() for c in raw) < 30:
                try:
                    pix = page.get_pixmap(dpi=180)
                    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    config = f'--tessdata-dir "{tessdata}"' if tessdata else ""
                    raw = pytesseract.image_to_string(image, lang="vie", config=config, timeout=120)
                    ocr = True
                except (RuntimeError, pytesseract.TesseractError, pytesseract.TesseractNotFoundError) as exc:
                    error = str(exc)[:500]
            pages.append({"pdf_page": index+1, "print_page": None, "raw_text": raw,
                          "ocr": ocr, "ocr_error": error, "exclude": False, "narrative": True,
                          "reviewed": False, "note": "", "remove_lines": []})
    if not pages:
        raise ValueError("PDF không có trang")
    # Suggestions only: no silent exclusion of covers, financial statements or short pages.
    edges = {}
    for p in pages:
        lines = [x.strip() for x in p["raw_text"].splitlines() if x.strip()]
        for line in set(lines[:2] + lines[-2:]):
            edges[line] = edges.get(line, 0) + 1
    repeated = {line for line, n in edges.items() if n >= max(3, len(pages)*0.5)}
    for p in pages:
        lines = p["raw_text"].splitlines()
        p["suggested_remove_lines"] = sorted({i for i in list(range(min(2,len(lines)))) + list(range(max(0,len(lines)-2),len(lines))) if lines[i].strip() in repeated})
        p["suggested_exclude"] = bool(re.search(r"mục lục", p["raw_text"][:150], re.I)) or len(p["raw_text"].strip()) < 30
        p["suggested_financial"] = bool(re.search(r"báo cáo tài chính|ý kiến kiểm toán|bảng cân đối kế toán", p["raw_text"][:600], re.I))
    return pages


def analyze(report, dictionary):
    matcher = Matcher(dictionary)
    occurrences, nohits = [], []
    full, narr = 0, 0
    for page in report["pages"]:
        if page["exclude"]:
            page["text"] = ""
            continue
        # Keep original offsets, even for removed header/footer lines.
        lines = page["raw_text"].splitlines(keepends=True)
        raw = "".join(" "*len(line) if i in page["remove_lines"] else line for i,line in enumerate(lines))
        text, offsets = normalize(raw)
        page["text"] = text
        words = count_words(text)
        page["word_count"] = words
        full += words
        if page["narrative"]:
            narr += words
        hits = matcher.match(text)
        for start, end, concept, term in hits:
            sentence, window = context(text, start, end)
            label, reason = suggest_label(sentence)
            oid = hashlib.sha256(f'{report["sha256"]}:{page["pdf_page"]}:{start}:{end}:{concept["concept_id"]}'.encode()).hexdigest()[:24]
            original_end = offsets[end] if end < len(text) else len(raw)
            occurrences.append({"occurrence_id": oid, "ticker": report["ticker"], "fiscal_year": report["fiscal_year"],
                "sha256": report["sha256"], "pdf_page": page["pdf_page"], "print_page": page["print_page"],
                "concept_id": concept["concept_id"], "matched_term": term, "start_char": start, "end_char": end,
                "original_start_char": offsets[start], "original_end_char": original_end,
                "sentence_text": sentence, "paragraph_context": window, "context_label": label,
                "label_rationale": reason, "confidence_score": None, "qa_reviewed": False,
                "digital_meaning": None})
        for m in re.finditer(r"[^.!?]+(?:[.!?]+|$)", text):
            if len(m.group().strip()) >= 30 and not any(m.start() < end and m.end() > start for start,end,_,_ in hits):
                nohits.append({"id": f'{page["pdf_page"]}:{m.start()}', "pdf_page": page["pdf_page"],
                               "text": m.group().strip(), "reviewed": False, "missed_hits": None})
    rng = random.Random(report["sha256"])
    dt = [o for o in occurrences if o["concept_id"] != "KW086" and next(c for c in dictionary["concepts"] if c["concept_id"] == o["concept_id"])["category"] != "TECH_ONLY"]
    sampled = rng.sample(dt, min(30, len(dt)))
    content_pages = [p["pdf_page"] for p in report["pages"] if not p["exclude"] and p.get("word_count",0)]
    mandatory = {content_pages[i] for i in (0,len(content_pages)//2,len(content_pages)-1)} if content_pages else set()
    pool = [n for n in content_pages if n not in mandatory]
    mandatory.update(rng.sample(pool, min(max(0,5-len(mandatory)),len(pool))))
    report["analysis"] = {"created_at": now(), "dictionary_sha256": dictionary["sha256"],
        "tokenizer": tokenizer_info(), "total_words_full": full, "total_words_narr": narr,
        "occurrences": occurrences, "qa_hits": [{"occurrence_id": o["occurrence_id"], "correct": None} for o in sampled],
        "qa_nohits": rng.sample(nohits,min(20,len(nohits))), "qa_pages": sorted(mandatory),
        "available_nohits": len(nohits), "word_reference": None, "word_reference_method": "",
        "review_notes": ""}
    report["document_status"] = "REVIEW"
    report["qa_result"] = None
    return report


def evaluate_qa(report, protocol):
    a = report.get("analysis")
    reasons = []
    result = {"precision_score": None, "recall_score": None, "word_count_discrepancy_pct": None}
    if not a:
        return {**result, "qa_decision": "REVIEW", "reasons": ["Chưa phân tích"]}
    hits, nohits = a["qa_hits"], a["qa_nohits"]
    tp = sum(h["correct"] is True for h in hits)
    fp = sum(h["correct"] is False for h in hits)
    fn = sum(h["missed_hits"] or 0 for h in nohits if h["reviewed"])
    precision = tp/(tp+fp) if tp+fp else None
    recall = tp/(tp+fn) if tp+fn else None
    ref = a.get("word_reference")
    deviation = abs(a["total_words_full"]-ref)/ref*100 if ref and ref>0 else None
    result.update(precision_score=precision, recall_score=recall, word_count_discrepancy_pct=deviation)
    if not protocol or not protocol.get("attested"):
        reasons.append("Chưa xác nhận đối chiếu Protocol gốc")
    if not all(p["reviewed"] for p in report["pages"]):
        reasons.append("Chưa duyệt phạm vi FULL/NARRATIVE và header/footer tất cả trang")
    if any(p["ocr_error"] for p in report["pages"] if not p["exclude"]):
        reasons.append("Trang nội dung còn lỗi OCR")
    if not a["total_words_full"]:
        reasons.append("Tổng từ bằng 0")
    if any(not o["qa_reviewed"] for o in a["occurrences"]):
        reasons.append("Còn occurrence chưa duyệt ngữ cảnh/nghĩa số")
    if any(h["correct"] is None for h in hits) or not hits:
        reasons.append("Mẫu hit chưa kiểm chứng hoặc không có hit để ước lượng precision")
    if len(nohits)<20 or any(not h["reviewed"] for h in nohits):
        reasons.append("Cần đủ 20 đoạn no-hit độc lập đã kiểm tra")
    if precision is None or precision<0.95:
        reasons.append("Precision chưa đạt 95%")
    if recall is None or recall<0.90:
        reasons.append("Recall chưa đạt 90%")
    if deviation is None or deviation>2 or not a.get("word_reference_method", "").strip():
        reasons.append("Chưa có kiểm đếm từ độc lập với độ lệch ≤2% và mô tả phương pháp")
    if not report.get("metadata_reviewed"):
        reasons.append("Chưa đối chiếu năm tài chính và nguồn phát hành")
    return {**result, "qa_sample_hits": len(hits), "qa_sample_nohits": len(nohits),
            "ocr_error_pages": [p["pdf_page"] for p in report["pages"] if p["ocr_error"]],
            "qa_decision": "REVIEW" if reasons else "OK", "reasons": reasons}
