import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("VIETFIN_DATA", "data")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("pdf", "artifacts", "exports"):
            (self.root / name).mkdir(exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS reports (
                  id TEXT PRIMARY KEY, ticker TEXT NOT NULL, fiscal_year INTEGER NOT NULL,
                  payload TEXT NOT NULL, UNIQUE(ticker, fiscal_year));
                CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                  seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                  report_id TEXT, action TEXT NOT NULL, detail TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / "vietfin.sqlite3", timeout=30)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, report_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM reports WHERE id=?", (report_id,)).fetchone()
        if not row:
            raise KeyError(report_id)
        return json.loads(row[0])

    def reports(self):
        return list(self.iter_reports())

    def iter_reports(self):
        """Read one document at a time instead of loading the corpus into memory."""
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM reports ORDER BY ticker,fiscal_year")
            for row in rows:
                yield json.loads(row[0])

    def summaries(self):
        with self.connect() as db:
            rows=db.execute("SELECT json_extract(payload,'$.summary') FROM reports ORDER BY ticker,fiscal_year").fetchall()
        if all(row[0] is not None for row in rows):
            return [json.loads(row[0]) for row in rows]
        # Compatibility with workspaces created before cached dashboard summaries.
        result=[]
        for report in self.iter_reports():
            self.save(report)
            result.append(self.get(report['id'])['summary'])
        return result

    def save(self, report):
        from .core import metrics
        report['summary']={k:v for k,v in report.items() if k not in {'pages','analysis','summary'}} | {
            'metrics': metrics(report,self.setting('dictionary')),
            'page_count':len(report['pages']),
            'occurrence_count':len((report.get('analysis') or {}).get('occurrences',[]))}
        with self.connect() as db:
            db.execute("INSERT INTO reports VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                       (report["id"], report["ticker"], report["fiscal_year"], json.dumps(report, ensure_ascii=False)))

    def setting(self, name, value=None):
        with self.connect() as db:
            if value is not None:
                db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (name, json.dumps(value, ensure_ascii=False)))
            row = db.execute("SELECT payload FROM settings WHERE name=?", (name,)).fetchone()
        return json.loads(row[0]) if row else None

    def audit(self, action, detail, report_id=None):
        with self.connect() as db:
            db.execute("INSERT INTO audit(timestamp, report_id, action, detail) VALUES (?,?,?,?)",
                       (now(), report_id, action, json.dumps(detail, ensure_ascii=False)))

    def history(self, report_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM audit WHERE (? IS NULL OR report_id=?) ORDER BY seq DESC LIMIT 500",
                              (report_id, report_id)).fetchall()
        return [dict(row) for row in rows]
