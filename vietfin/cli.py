import argparse
import csv
import json
import os
import time
from pathlib import Path

from .service import Service
from .network import fetch


def main():
    parser=argparse.ArgumentParser(description="VietFin-DTMiner — BCTN evidence and audit")
    parser.add_argument("--data",default=os.environ.get("VIETFIN_DATA","data"),help="Workspace dữ liệu riêng")
    sub=parser.add_subparsers(dest="command",required=True)
    serve=sub.add_parser("serve");serve.add_argument("--port",type=int,default=8000)
    sub.add_parser("status")
    d=sub.add_parser("dictionary");d.add_argument("file");d.add_argument("--attest-original",action="store_true")
    p=sub.add_parser("protocol");p.add_argument("file");p.add_argument("--attest-original",action="store_true")
    i=sub.add_parser("ingest");i.add_argument("ticker");i.add_argument("year",type=int);i.add_argument("file");i.add_argument("--source-url",default="")
    b=sub.add_parser("batch");b.add_argument("manifest",help="CSV ticker,fiscal_year,path,source_url; đường dẫn tương đối theo manifest")
    m=sub.add_parser("missing");m.add_argument("tickers",nargs="+")
    a=sub.add_parser("process");a.add_argument("report_ids",nargs="*",help="Bỏ trống để xử lý mọi PDF chưa phân tích")
    e=sub.add_parser("export");e.add_argument("output");e.add_argument("--format",choices=["csv","xlsx","parquet"],default="csv")
    args=parser.parse_args()
    if args.command=="serve":
        import uvicorn
        from .app import create_app
        uvicorn.run(create_app(args.data),host="127.0.0.1",port=args.port)
        return
    s=Service(args.data)
    try:
        if args.command=="status":
            print(json.dumps(s.config()|{"reports":[{"id":r["id"],"status":r["document_status"],"error":r["error"]} for r in s.store.reports()]},ensure_ascii=False,indent=2))
        elif args.command=="dictionary":
            print(json.dumps(s.dictionary(Path(args.file).read_bytes(),args.file,args.attest_original),ensure_ascii=False))
        elif args.command=="protocol":
            print(json.dumps(s.protocol(Path(args.file).read_bytes(),args.file,args.attest_original),ensure_ascii=False))
        elif args.command=="ingest":
            print(s.ingest(args.ticker,args.year,Path(args.file).read_bytes(),source_url=args.source_url)["id"])
        elif args.command=="missing":
            existing={r["id"] for r in s.store.reports()}
            for t in args.tickers:
                for y in range(2016,2026):
                    if f"{t.upper()}-{y}" not in existing:
                        print(s.ingest(t,y)["id"])
        elif args.command=="batch":
            manifest=Path(args.manifest).resolve()
            rows=list(csv.DictReader(manifest.open(encoding="utf-8-sig")))
            failures=0
            for row in rows:
                try:
                    url=row.get("source_url","")
                    if row.get("path"):
                        content=(manifest.parent/row["path"]).read_bytes()
                    elif url:
                        content,url=fetch(url)
                    else:
                        content=None
                    print(s.ingest(row["ticker"],int(row["fiscal_year"]),content,source_url=url,
                                   publication_year=int(row["publication_year"]) if row.get("publication_year") else None)["id"])
                except Exception as exc:
                    failures+=1
                    print(json.dumps({"ticker":row.get("ticker"),"year":row.get("fiscal_year"),"error":str(exc)},ensure_ascii=False))
            if failures:
                raise SystemExit(1)
        elif args.command=="process":
            ids=args.report_ids or [r["id"] for r in s.store.reports() if r["sha256"] and not r["analysis"]]
            jobs=[s.process(rid) for rid in ids]
            while any(j["status"] in {"queued","running"} for j in jobs):
                time.sleep(.2)
            print(json.dumps(jobs,ensure_ascii=False,indent=2))
            if any(j["status"]=="failed" for j in jobs):
                raise SystemExit(1)
        elif args.command=="export":
            Path(args.output).write_bytes(s.export(args.format))
            print(args.output)
    except (ValueError,KeyError,OSError) as exc:
        parser.exit(1,f"Lỗi: {exc}\n")
    finally:
        s.executor.shutdown(wait=True)


if __name__=="__main__":
    main()
