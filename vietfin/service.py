import csv
import hashlib
import io
import json
import os
import re
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

from .core import LABELS, metrics, parse_dictionary
from .pipeline import analyze, evaluate_qa, extract_pdf, tokenizer_info
from .store import Store, now

SCHEMAS = {
    "sources_manifest": "ticker fiscal_year publication_year title publisher source_url retrieval_date file_name sha256 document_status selected_version exclusion_reason".split(),
    "report_year": "ticker fiscal_year doc_status total_words_full total_words_narr tech_freq tech_unique dt_raw_freq dt_disc_freq dt_unique dt_implement_freq dt_index dt_implement_index dt_per_10000 tech_per_10000 dt_tech_share dt_broad_freq digital_dummy".split(),
    "keyword_year": "ticker fiscal_year concept_id keyword_name concept_group category raw_freq disc_freq implement_freq dict_version".split(),
    "occurrences": "occurrence_id ticker fiscal_year sha256 pdf_page print_page concept_id matched_term start_char end_char sentence_text paragraph_context context_label label_rationale confidence_score qa_reviewed".split(),
    "qa_log": "ticker fiscal_year ocr_error_pages qa_sample_hits qa_sample_nohits word_count_discrepancy_pct precision_score recall_score qa_decision review_notes".split()
}


class Service:
    def __init__(self, root=None):
        self.store = Store(root)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vietfin")
        self.jobs = {}
        for r in self.store.iter_reports():
            if r.get("processing"):
                r["processing"] = False
                r["error"] = "Tiến trình trước bị gián đoạn; chạy lại xử lý"
                self.store.save(r)

    def config(self):
        d = self.store.setting("dictionary")
        return {"dictionary": {k:v for k,v in d.items() if k!="concepts"} | {"count": len(d["concepts"])} if d else None,
                "protocol": self.store.setting("protocol"), "tokenizer": tokenizer_info(),
                "data_root": str(self.store.root), "workflow": "single-user-local"}

    def dictionary(self, content, filename, attested):
        if not attested:
            raise ValueError("Cần xác nhận tệp được chuyển từ Dictionary V1.0 gốc, không phải danh sách tự tạo")
        d = parse_dictionary(content, filename)
        with self.lock:
            old = self.store.setting("dictionary")
            if old and old["sha256"] != d["sha256"] and any(r.get("analysis") for r in self.store.iter_reports()):
                raise ValueError("Đã có phân tích: từ điển bị khóa. Phương pháp mới cần workspace/version mới và chạy lại toàn mẫu")
            artifact = self.store.root/"artifacts"/(d["sha256"] + (".xlsx" if filename.endswith(".xlsx") else ".csv"))
            artifact.write_bytes(content)
            self.store.setting("dictionary", d)
            self.store.audit("dictionary_import", {"sha256": d["sha256"], "attested": True})
        return self.config()

    def protocol(self, content, filename, attested):
        if not content or len(content)>20*1024*1024:
            raise ValueError("Protocol phải có nội dung, tối đa 20 MB")
        digest = hashlib.sha256(content).hexdigest()
        suffix = Path(filename).suffix.lower()
        if suffix not in {".docx", ".pdf", ".txt", ".md"}:
            raise ValueError("Protocol hỗ trợ DOCX/PDF/TXT/MD")
        (self.store.root/"artifacts"/(digest+suffix)).write_bytes(content)
        info = {"version": "PROTOCOL_V1.0", "sha256": digest, "filename": Path(filename).name,
                "attested": bool(attested), "note": "Người dùng xác nhận bản gốc; hệ thống không tự chứng nhận tính tương đương phương pháp"}
        with self.lock:
            self.store.setting("protocol", info)
            self.store.audit("protocol_import", info)
            for r in self.store.iter_reports():
                if r.get("analysis"):
                    r["document_status"]="REVIEW"
                    r["qa_result"] = None
                    self.store.save(r)
        return info

    def ingest(self, ticker, year, content=None, **metadata):
        ticker = ticker.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{2,12}", ticker) or not 2016<=int(year)<=2025:
            raise ValueError("Ticker 2–12 chữ/số, năm tài chính trong 2016–2025")
        rid = f"{ticker}-{int(year)}"
        with self.lock:
            try:
                existing=self.store.get(rid)
            except KeyError:
                existing=None
            if existing and existing.get("processing"):
                raise ValueError("Đợi hồ sơ xử lý xong trước khi nhập bản đính chính")
            if existing and existing.get("sha256") and not metadata.get("replace",False):
                raise ValueError("Đã có bản chuẩn cho doanh nghiệp–năm; không cộng hoặc ghi đè PDF. Dùng workspace riêng để đối chiếu phiên bản mới")
            if existing and existing.get("sha256") and content is None:
                raise ValueError("Không được thay PDF hiện có bằng MISSING")
            digest = None
            if content is not None:
                if len(content)>100*1024*1024 or not content.startswith(b"%PDF-"):
                    raise ValueError("Cần PDF hợp lệ, tối đa 100 MB")
                try:
                    with pymupdf.open(stream=content,filetype="pdf") as doc:
                        if doc.needs_pass or not len(doc):
                            raise ValueError("PDF trống hoặc cần mật khẩu")
                except (pymupdf.FileDataError,RuntimeError) as exc:
                    raise ValueError("Không đọc được PDF: "+str(exc)) from exc
                digest = hashlib.sha256(content).hexdigest()
                target = self.store.root/"pdf"/(digest+".pdf")
                if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                    raise ValueError("Kho PDF không toàn vẹn")
                if not target.exists():
                    target.write_bytes(content)
            version=1
            if existing and existing.get("sha256"):
                if existing['sha256']==digest:
                    raise ValueError("PDF trùng SHA-256 với bản đang chọn; không tạo phiên bản đếm lặp")
                version=int(existing["selected_version"])+1
                archive_dir=self.store.root/'artifacts'/'versions'/rid
                archive_dir.mkdir(parents=True,exist_ok=True)
                archive_file=archive_dir/f'{existing["selected_version"]}-{existing["sha256"]}.json'
                archive_file.write_text(json.dumps(existing,ensure_ascii=False),encoding='utf-8')
                self.store.audit("supersede_version",{"previous_sha256":existing['sha256'],"selected_sha256":digest,
                    "archive":str(archive_file.relative_to(self.store.root)),"reason":metadata.get('replacement_reason','Bản đính chính do người dùng chọn')},rid)
            report = {"id": rid, "ticker": ticker, "fiscal_year": int(year),
                "publication_year": metadata.get("publication_year"), "title": metadata.get("title") or f"{ticker} BCTN {year}",
                "publisher": metadata.get("publisher") or ticker, "source_url": metadata.get("source_url") or None,
                "retrieval_date": now(), "file_name": f"{ticker}_BCTN_{year}.pdf" if digest else None,
                "sha256": digest, "document_status": "REVIEW" if digest else "MISSING",
                "selected_version": str(version) if digest else None, "exclusion_reason": None if digest else "Chưa có BCTN chuẩn",
                "metadata_reviewed": False, "pages": [], "analysis": None, "processing": False, "error": None}
            self.store.save(report)
            self.store.audit("ingest" if digest else "register_missing", {"sha256": digest, "source_url":report["source_url"]},rid)
        return report

    def process(self, rid):
        with self.lock:
            r = self.store.get(rid)
            if r["processing"]:
                raise ValueError("Hồ sơ đang xử lý")
            if not r["sha256"]:
                raise ValueError("Hồ sơ MISSING: cần PDF")
            r["processing"] = True
            r["error"] = None
            r["document_status"] = "REVIEW"
            self.store.save(r)
        job_id = uuid.uuid4().hex
        self.jobs[job_id] = {"id": job_id, "report_id":rid,"status":"queued","error":None}

        def run():
            self.jobs[job_id]["status"]="running"
            try:
                path = self.store.root/"pdf"/(r["sha256"]+".pdf")
                if hashlib.sha256(path.read_bytes()).hexdigest()!=r["sha256"]:
                    raise ValueError("SHA-256 PDF không khớp")
                if not r["pages"]:
                    r["pages"] = extract_pdf(path, os.environ.get("VIETFIN_TESSDATA"))
                with self.lock:
                    d = self.store.setting("dictionary")
                    if d:
                        pinned = self.store.setting("tokenizer")
                        if pinned and pinned != tokenizer_info():
                            raise ValueError("Phiên bản tokenizer thay đổi: cần môi trường đã khóa hoặc version nghiên cứu mới")
                        self.store.setting("tokenizer",tokenizer_info())
                        analyze(r,d)
                    else:
                        r["error"] = "Đã trích PDF; chưa tính chỉ số vì thiếu Dictionary V1.0"
                    r["processing"] = False
                    self.store.save(r)
                    self.store.audit("process", {"dictionary":d["sha256"] if d else None,"pages":len(r["pages"])},rid)
                self.jobs[job_id]["status"]="done"
            except Exception as exc:
                with self.lock:
                    current = self.store.get(rid)
                    current.update(processing=False,error=str(exc),document_status="REVIEW")
                    self.store.save(current)
                    self.store.audit("process_failed",{"error":str(exc)},rid)
                self.jobs[job_id].update(status="failed",error=str(exc))
        self.executor.submit(run)
        return self.jobs[job_id]

    def editable(self, rid):
        r = self.store.get(rid)
        if r["processing"]:
            raise ValueError("Đợi xử lý hoàn tất trước khi sửa")
        return r

    def update_page(self, rid, number, values):
        with self.lock:
            r = self.editable(rid)
            page = next((p for p in r["pages"] if p["pdf_page"]==number),None)
            if not page:
                raise ValueError("Không có trang")
            if any(i<0 or i>=len(page["raw_text"].splitlines()) for i in values["remove_lines"]):
                raise ValueError("Chỉ số dòng không hợp lệ (bắt đầu từ 0)")
            if values.get("print_page") is not None and len(str(values["print_page"]))>30:
                raise ValueError("Số trang in quá dài")
            page.update(values)
            # Any text-scope change invalidates all dependent spans and QA.
            r["analysis"] = None
            r["qa_result"] = None
            r["document_status"] = "REVIEW"
            self.store.save(r)
            self.store.audit("page_review",values|{"pdf_page":number},rid)
        return r

    def review_occurrence(self, rid, oid, values):
        with self.lock:
            r = self.editable(rid)
            if not r.get("analysis"):
                raise ValueError("Chạy phân tích trước")
            o = next((o for o in r["analysis"]["occurrences"] if o["occurrence_id"]==oid),None)
            if not o:
                raise ValueError("Occurrence không tồn tại")
            if values["context_label"] not in LABELS or not values["label_rationale"].strip():
                raise ValueError("Cần nhãn C1–C6 và lý do có bằng chứng")
            o.update(values,qa_reviewed=True,confidence_score=None)
            for h in r["analysis"]["qa_hits"]:
                if h["occurrence_id"]==oid:
                    h["correct"]=None
            r["document_status"]="REVIEW"
            r["qa_result"] = None
            self.store.save(r)
            self.store.audit("occurrence_review",values|{"occurrence_id":oid},rid)
        return o

    def suggest_ai(self, rid, oid):
        from .llm import predict
        with self.lock:
            r=self.editable(rid)
            if not r.get("analysis"):
                raise ValueError("Chưa có phân tích")
            o=next((o for o in r["analysis"]["occurrences"] if o["occurrence_id"]==oid),None)
            if not o:
                raise ValueError("Không có occurrence")
            fingerprint=r["analysis"]["created_at"]
        suggestion=predict(o)
        with self.lock:
            r=self.editable(rid)
            if not r.get("analysis") or r["analysis"]["created_at"]!=fingerprint:
                raise ValueError("Phân tích đã thay đổi trong khi model chạy; không lưu gợi ý cũ")
            target=next(o for o in r["analysis"]["occurrences"] if o["occurrence_id"]==oid)
            target["ai_suggestion"]=suggestion
            if not target["qa_reviewed"]:
                target["context_label"]=suggestion["context_label"]
                target["label_rationale"]="Gợi ý LLM chưa kiểm chứng: "+suggestion["rationale"]
                target["confidence_score"]=None
            self.store.save(r)
            self.store.audit("local_llm_suggestion",suggestion|{"occurrence_id":oid},rid)
        return suggestion

    def correct_text(self,rid,number,text,reason):
        if not reason.strip() or len(text)>200000:
            raise ValueError("Cần lý do sửa và văn bản tối đa 200.000 ký tự/trang")
        with self.lock:
            r=self.editable(rid)
            page=next((p for p in r["pages"] if p["pdf_page"]==number),None)
            if not page:
                raise ValueError("Không có trang")
            page.setdefault("original_extracted_text",page["raw_text"])
            page.update(raw_text=text,ocr_error=None,reviewed=False,remove_lines=[],note=reason)
            r.update(analysis=None,qa_result=None,document_status="REVIEW")
            self.store.save(r)
            self.store.audit("text_correction",{"pdf_page":number,"reason":reason,"text":text},rid)
        return page

    def qa(self, rid, values=None):
        with self.lock:
            r = self.editable(rid)
            if not r.get("analysis"):
                raise ValueError("Chưa có phân tích")
            a = r["analysis"]
            if values is not None:
                if {h["occurrence_id"] for h in values["hits"]} != {h["occurrence_id"] for h in a["qa_hits"]} or len(values["hits"])!=len(a["qa_hits"]):
                    raise ValueError("Mẫu hit không khớp lần phân tích hiện tại")
                if {h["id"] for h in values["nohits"]} != {h["id"] for h in a["qa_nohits"]} or len(values["nohits"])!=len(a["qa_nohits"]):
                    raise ValueError("Mẫu no-hit không khớp")
                a["qa_hits"]=values["hits"]
                for old,new in zip(sorted(a["qa_nohits"],key=lambda h:h["id"]),sorted(values["nohits"],key=lambda h:h["id"])):
                    old.update(new)
                a.update({k:values[k] for k in ("word_reference","word_reference_method","review_notes")})
            result = evaluate_qa(r,self.store.setting("protocol"))
            pdf=self.store.root/'pdf'/(r['sha256']+'.pdf')
            if not pdf.exists() or hashlib.sha256(pdf.read_bytes()).hexdigest()!=r['sha256']:
                result['reasons'].append('PDF gốc không còn khớp SHA-256')
            dictionary=self.store.setting('dictionary')
            if not dictionary or a['dictionary_sha256']!=dictionary['sha256'] or a['tokenizer']!=tokenizer_info():
                result['reasons'].append('Phiên bản từ điển/tokenizer không khớp phân tích')
            if result['reasons']:
                result['qa_decision']='REVIEW'
            r["document_status"] = result["qa_decision"]
            r["qa_result"] = result
            self.store.save(r)
            self.store.audit("qa_evaluate",result,rid)
        return result

    def export(self, fmt="csv"):
        if fmt not in {"csv","xlsx","parquet"}:
            raise ValueError("Định dạng: csv/xlsx/parquet")
        with self.lock:
            reports = self.store.iter_reports()
            report_count = 0
            d = self.store.setting("dictionary")
            tables = {name:[] for name in SCHEMAS}
            for r in reports:
                report_count += 1
                tables["sources_manifest"].append(r)
                tables["report_year"].append({"ticker":r["ticker"],"fiscal_year":r["fiscal_year"],"doc_status":r["document_status"],**metrics(r,d)})
                a = r.get("analysis")
                if not a:
                    tables["qa_log"].append({"ticker":r["ticker"],"fiscal_year":r["fiscal_year"],"qa_decision":"REVIEW",
                        "review_notes":"MISSING: chưa có BCTN chuẩn" if r["document_status"]=="MISSING" else "Chưa phân tích / chưa QA"})
                    if d:
                        for c in d["concepts"]:
                            tables["keyword_year"].append({"ticker":r["ticker"],"fiscal_year":r["fiscal_year"],**c,
                                "raw_freq":None,"disc_freq":None,"implement_freq":None,"dict_version":d["version"]})
                    continue
                tables["occurrences"].extend(a["occurrences"])
                result=r.get('qa_result') or evaluate_qa(r,self.store.setting("protocol"))
                if r['document_status']!='OK':
                    result['qa_decision']='REVIEW'
                tables["qa_log"].append({"ticker":r["ticker"],"fiscal_year":r["fiscal_year"],**result,
                    "review_notes":a["review_notes"]+"; "+"; ".join(result["reasons"])})
                for c in d["concepts"]:
                    occurrences=[o for o in a["occurrences"] if o["concept_id"]==c["concept_id"]]
                    eligible=c["category"] in {"CORE","CONTEXT"} and c["concept_id"]!="KW086"
                    disc=[o for o in occurrences if eligible and o["qa_reviewed"] and o["digital_meaning"] and o["context_label"] in {"C1","C2","C3"}]
                    tables["keyword_year"].append({"ticker":r["ticker"],"fiscal_year":r["fiscal_year"],**c,
                        "raw_freq":len(occurrences),"disc_freq":len(disc),"implement_freq":sum(o["context_label"]=="C1" for o in disc),"dict_version":d["version"]})
        output=io.BytesIO()
        with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
            for name, columns in SCHEMAS.items():
                rows=[{k:json.dumps(row.get(k),ensure_ascii=False) if isinstance(row.get(k),(list,dict)) else row.get(k) for k in columns} for row in tables[name]]
                if fmt=="csv":
                    stream=io.StringIO(newline="")
                    writer=csv.DictWriter(stream,fieldnames=columns)
                    writer.writeheader()
                    # Explicit NA preserves missing vs observed zero.
                    writer.writerows({k: "NA" if v is None else v for k,v in row.items()} for row in rows)
                    content=stream.getvalue().encode("utf-8-sig")
                else:
                    import pandas as pd
                    frame=pd.DataFrame(rows,columns=columns)
                    stream=io.BytesIO()
                    if fmt=="xlsx":
                        frame.to_excel(stream,index=False,na_rep="NA")
                    else:
                        frame.to_parquet(stream,index=False)
                    content=stream.getvalue()
                archive.writestr(name+"."+fmt,content)
        self.store.audit("export",{"format":fmt,"reports":report_count})
        return output.getvalue()
