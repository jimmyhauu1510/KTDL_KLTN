import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .core import metrics
from .network import discover, fetch
from .service import Service


class StrictModel(BaseModel):
    model_config=ConfigDict(extra="forbid")


class PageReview(StrictModel):
    exclude: bool=False
    narrative: bool=True
    reviewed: bool=True
    print_page: str|None=None
    remove_lines: list[int]=[]
    note: str=Field(default="",max_length=5000)


class OccurrenceReview(StrictModel):
    context_label: Literal["C1","C2","C3","C4","C5","C6"]
    label_rationale: str=Field(min_length=1,max_length=5000)
    digital_meaning: bool


class HitQA(StrictModel):
    occurrence_id: str
    correct: bool|None=None


class NoHitQA(StrictModel):
    id: str
    reviewed: bool=False
    missed_hits: int|None=Field(default=None,ge=0)


class QAReview(StrictModel):
    hits: list[HitQA]
    nohits: list[NoHitQA]
    word_reference: int|None=Field(default=None,gt=0)
    word_reference_method: str=Field(default="",max_length=5000)
    review_notes: str=Field(default="",max_length=10000)


class Metadata(StrictModel):
    publication_year: int|None=Field(default=None,ge=2016,le=2100)
    title: str=Field(min_length=1,max_length=500)
    publisher: str=Field(min_length=1,max_length=500)
    source_url: str|None=Field(default=None,max_length=2000)
    metadata_reviewed: bool=False


class Missing(StrictModel):
    tickers: list[str]=Field(min_length=1,max_length=2000)
    years: list[int]=Field(default_factory=lambda:list(range(2016,2026)),min_length=1,max_length=10)


class URLImport(StrictModel):
    ticker: str
    fiscal_year: int
    url: str=Field(max_length=2000)


class Discovery(StrictModel):
    url: str=Field(max_length=2000)


class TextCorrection(StrictModel):
    text: str=Field(max_length=200000)
    reason: str=Field(min_length=1,max_length=5000)


def create_app(root=None):
    from contextlib import asynccontextmanager
    service=Service(root)
    @asynccontextmanager
    async def lifespan(app):
        yield
        service.executor.shutdown(wait=True)
    app=FastAPI(title="VietFin-DTMiner",version="0.1.0",lifespan=lifespan)
    app.state.service=service
    static=Path(__file__).parent/"static"

    @app.middleware("http")
    async def local_boundary(request,call_next):
        # Local, single-user research UI; block cross-origin mutations and hostile Host headers.
        if request.url.hostname not in {"127.0.0.1","localhost","::1","testserver"}:
            return Response("Local host required",status_code=403)
        origin=request.headers.get("origin")
        if request.method not in {"GET","HEAD","OPTIONS"} and origin and origin!=str(request.base_url).rstrip("/"):
            return Response("Cross-origin request rejected",status_code=403)
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(ValueError)
    async def bad_request(request,exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":str(exc)},status_code=400)

    @app.exception_handler(KeyError)
    async def not_found(request,exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":"Không tìm thấy hồ sơ hoặc tài nguyên"},status_code=404)

    import httpx
    @app.exception_handler(httpx.HTTPError)
    async def upstream_failure(request,exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":"Nguồn tải hoặc dịch vụ AI không khả dụng: "+str(exc)},status_code=502)

    @app.get("/")
    def index():
        return FileResponse(static/"index.html")

    @app.get("/api/health")
    def health():
        return {"status":"ok","version":"0.1.0"}

    @app.get("/api/config")
    def config():
        return service.config()

    @app.post("/api/dictionary")
    async def dictionary(file:UploadFile=File(...),attested:bool=Form(False)):
        content=await file.read(10*1024*1024+1)
        if len(content)>10*1024*1024:
            raise ValueError("Dictionary tối đa 10 MB")
        return service.dictionary(content,file.filename or "dictionary.csv",attested)

    @app.get("/api/dictionary/template")
    def dictionary_template():
        return Response("concept_id,keyword_name,concept_group,category,terms,case_sensitive_terms\n",media_type="text/csv",
                        headers={"Content-Disposition":"attachment; filename=dictionary_import_template.csv"})

    @app.post("/api/protocol")
    async def protocol(file:UploadFile=File(...),attested:bool=Form(False)):
        return service.protocol(await file.read(20*1024*1024+1),file.filename or "protocol.docx",attested)

    @app.get("/api/reports")
    def reports():
        return service.store.summaries()

    @app.post("/api/reports")
    async def upload(ticker:str=Form(...),fiscal_year:int=Form(...),source_url:str=Form(""),publication_year:int|None=Form(None),replace:bool=Form(False),replacement_reason:str=Form(""),file:UploadFile=File(...)):
        if replace and not replacement_reason.strip():
            raise ValueError("Chọn bản đính chính cần ghi lý do và nguồn xác minh")
        return service.ingest(ticker,fiscal_year,await file.read(100*1024*1024+1),source_url=source_url,publication_year=publication_year,replace=replace,replacement_reason=replacement_reason)

    @app.post("/api/missing")
    def missing(body:Missing):
        # Validate all inputs before any mutation.
        import re
        if any(not re.fullmatch(r"[A-Z0-9]{2,12}",t.strip().upper()) for t in body.tickers) or any(not 2016<=y<=2025 for y in body.years):
            raise ValueError("Ticker/năm không hợp lệ")
        existing={r["id"] for r in service.store.reports()}
        added=[]
        for ticker in dict.fromkeys(t.strip().upper() for t in body.tickers):
            for year in dict.fromkeys(body.years):
                if f"{ticker}-{year}" not in existing:
                    added.append(service.ingest(ticker,year)["id"])
        return {"added":added}

    @app.post("/api/ingest-url")
    def ingest_url(body:URLImport):
        content,final=fetch(body.url)
        return service.ingest(body.ticker,body.fiscal_year,content,source_url=final)

    @app.post("/api/discover")
    def discover_urls(body:Discovery):
        return {"urls":discover(body.url),"note":"Danh sách ứng viên từ trang HTML; cần xác minh BCTN và năm tài chính trước khi nhập"}

    @app.get("/api/reports/{rid}")
    def report(rid:str):
        r=service.store.get(rid)
        return r|{"metrics":metrics(r,service.store.setting("dictionary"))}

    @app.put("/api/reports/{rid}/metadata")
    def metadata(rid:str,body:Metadata):
        with service.lock:
            r=service.editable(rid)
            r.update(body.model_dump())
            if r["sha256"]:
                r["document_status"]="REVIEW"
                r["qa_result"] = None
            service.store.save(r)
            service.store.audit("metadata_review",body.model_dump(),rid)
        return r

    @app.get("/api/reports/{rid}/pdf")
    def pdf(rid:str):
        r=service.store.get(rid)
        if not r["sha256"]:
            raise HTTPException(404,"Chưa có PDF")
        return FileResponse(service.store.root/"pdf"/(r["sha256"]+".pdf"),media_type="application/pdf")

    @app.post("/api/reports/{rid}/process")
    def process(rid:str):
        return service.process(rid)

    @app.get("/api/jobs/{jid}")
    def job(jid:str):
        return service.jobs[jid]

    @app.put("/api/reports/{rid}/pages/{number}")
    def page(rid:str,number:int,body:PageReview):
        return service.update_page(rid,number,body.model_dump())

    @app.put("/api/reports/{rid}/occurrences/{oid}")
    def occurrence(rid:str,oid:str,body:OccurrenceReview):
        return service.review_occurrence(rid,oid,body.model_dump())

    @app.post("/api/reports/{rid}/occurrences/{oid}/suggest-ai")
    def suggest_ai(rid:str,oid:str):
        import httpx
        try:
            return service.suggest_ai(rid,oid)
        except httpx.HTTPError as exc:
            raise HTTPException(502,"Không gọi được Ollama local: "+str(exc)) from exc

    @app.put("/api/reports/{rid}/pages/{number}/text")
    def correct_text(rid:str,number:int,body:TextCorrection):
        return service.correct_text(rid,number,body.text,body.reason)

    @app.post("/api/reports/{rid}/qa")
    def qa(rid:str,body:QAReview):
        values=body.model_dump()
        if any(h["reviewed"] and h["missed_hits"] is None for h in values["nohits"]):
            raise ValueError("No-hit đã duyệt cần số lượt bỏ sót, bao gồm 0")
        return service.qa(rid,values)

    @app.get("/api/reports/{rid}/qa")
    def qa_status(rid:str):
        return service.qa(rid)

    @app.get("/api/audit")
    def audit(report_id:str|None=None):
        return service.store.history(report_id)

    @app.get("/api/export")
    def export(format:Literal["csv","xlsx","parquet"]="csv"):
        return Response(service.export(format),media_type="application/zip",
                        headers={"Content-Disposition":f"attachment; filename=vietfin_{format}.zip"})

    app.mount("/static",StaticFiles(directory=static),name="static")
    return app
