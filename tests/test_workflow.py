import csv
import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient
from vietfin.app import create_app
from vietfin.service import Service,SCHEMAS
from vietfin.network import validate_url


def wait(service,job):
    deadline=time.monotonic()+30
    while job['status'] in {'queued','running'} and time.monotonic()<deadline:
        time.sleep(.05)
    assert job['status']=='done',job


def test_full_lifecycle_api(tmp_path,dictionary_bytes,pdf_bytes):
    """Artificial gold labels exercise gates; they do not validate research accuracy."""
    app=create_app(tmp_path)
    s=app.state.service
    try:
        with TestClient(app) as c:
            assert c.get('/').status_code==200
            assert c.get('/api/health').json()['status']=='ok'
            assert c.post('/api/dictionary',files={'file':('fixture.csv',dictionary_bytes)}).status_code==400
            assert c.post('/api/dictionary',files={'file':('fixture.csv',dictionary_bytes)},data={'attested':'true'}).status_code==200
            assert c.post('/api/protocol',files={'file':('fixture.md',b'SYNTHETIC TEST ONLY')},data={'attested':'true'}).status_code==200
            response=c.post('/api/reports',files={'file':('report.pdf',pdf_bytes,'application/pdf')},data={'ticker':'FPT','fiscal_year':'2024'})
            assert response.status_code==200,response.text
            rid=response.json()['id']
            assert c.get(f'/api/reports/{rid}/pdf').content==pdf_bytes
            job=c.post(f'/api/reports/{rid}/process').json()
            deadline=time.monotonic()+30
            while c.get('/api/jobs/'+job['id']).json()['status'] in {'queued','running'} and time.monotonic()<deadline:
                time.sleep(.05)
            assert c.get('/api/jobs/'+job['id']).json()['status']=='done'
            report=c.get('/api/reports/'+rid).json()
            assert len(report['pages'])==2 and report['analysis']['total_words_full']>0
            assert len(report['analysis']['occurrences'])==1
            assert len(report['analysis']['qa_nohits'])==20
            assert c.get(f'/api/reports/{rid}/qa').json()['qa_decision']=='REVIEW'
            for page in report['pages']:
                body={'exclude':False,'narrative':True,'reviewed':True,'print_page':str(page['pdf_page']), 'remove_lines':[],'note':'Synthetic test scope'}
                assert c.put(f'/api/reports/{rid}/pages/{page["pdf_page"]}',json=body).status_code==200
            wait(s,s.process(rid))
            report=c.get('/api/reports/'+rid).json()
            o=report['analysis']['occurrences'][0]
            assert not o['qa_reviewed'] and o['confidence_score'] is None
            assert c.put(f'/api/reports/{rid}/occurrences/{o["occurrence_id"]}',json={'context_label':'C1','label_rationale':'Synthetic internal implementation fixture','digital_meaning':True}).status_code==200
            assert c.put(f'/api/reports/{rid}/metadata',json={'title':'Synthetic BCTN','publisher':'Test','publication_year':2025,'source_url':None,'metadata_reviewed':True}).status_code==200
            a=c.get('/api/reports/'+rid).json()['analysis']
            qa={'hits':[{'occurrence_id':h['occurrence_id'],'correct':True} for h in a['qa_hits']],
                'nohits':[{'id':h['id'],'reviewed':True,'missed_hits':0} for h in a['qa_nohits']],
                'word_reference':a['total_words_full'],'word_reference_method':'Synthetic reference for gate testing only','review_notes':'Not research data'}
            result=c.post(f'/api/reports/{rid}/qa',json=qa)
            assert result.status_code==200,result.text
            assert result.json()['qa_decision']=='OK',result.json()
            report=c.get('/api/reports/'+rid).json()
            assert report['metrics']['digital_dummy']==1
            assert c.post('/api/missing',json={'tickers':['VNM'],'years':[2023]}).status_code==200
            for fmt in ('csv','xlsx','parquet'):
                exported=c.get('/api/export?format='+fmt)
                assert exported.status_code==200
                with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
                    assert set(z.namelist())=={name+'.'+fmt for name in SCHEMAS}
                    if fmt=='csv':
                        rows=list(csv.DictReader(io.StringIO(z.read('report_year.csv').decode('utf-8-sig'))))
                        missing=next(r for r in rows if r['ticker']=='VNM')
                        assert missing['dt_index']=='NA' and missing['digital_dummy']=='NA'
                        keywords=list(csv.DictReader(io.StringIO(z.read('keyword_year.csv').decode('utf-8-sig'))))
                        assert len(keywords)==214
                        assert next(k for k in keywords if k['ticker']=='VNM')['raw_freq']=='NA'
            qa['nohits'][0]['missed_hits']=1
            result=c.post(f'/api/reports/{rid}/qa',json=qa).json()
            assert result['recall_score']==.5 and result['qa_decision']=='REVIEW'
            assert c.get('/api/reports/'+rid).json()['metrics']['digital_dummy'] is None
            assert len(c.get('/api/audit').json())>=10
    finally:
        s.executor.shutdown(wait=True)


def test_empty_repository_can_extract_without_dictionary(tmp_path,pdf_bytes):
    s=Service(tmp_path)
    try:
        r=s.ingest('CMG',2020,pdf_bytes)
        wait(s,s.process(r['id']))
        r=s.store.get(r['id'])
        assert r['pages'] and r['analysis'] is None and r['document_status']=='REVIEW'
        with pytest.raises(ValueError,match='Đã có bản chuẩn'):
            s.ingest('CMG',2020,pdf_bytes)
        s.correct_text(r['id'],1,'Văn bản đã sửa theo PDF.','Synthetic correction')
        page=s.store.get(r['id'])['pages'][0]
        assert page['original_extracted_text']!=page['raw_text'] and not page['reviewed']
    finally:
        s.executor.shutdown(wait=True)


def test_hash_tampering_detected(tmp_path,pdf_bytes):
    s=Service(tmp_path)
    try:
        r=s.ingest('FPT',2024,pdf_bytes)
        (tmp_path/'pdf'/(r['sha256']+'.pdf')).write_bytes(b'tampered')
        job=s.process(r['id'])
        s.executor.shutdown(wait=True)
        assert job['status']=='failed' and 'SHA-256' in job['error']
    finally:
        s.executor.shutdown(wait=True)


def test_security_boundaries(tmp_path):
    app=create_app(tmp_path)
    try:
        with TestClient(app) as c:
            assert c.post('/api/missing',json={'tickers':['FPT']},headers={'Origin':'https://evil.example'}).status_code==403
            assert c.get('/api/health',headers={'Host':'evil.example'}).status_code==403
            assert c.post('/api/missing',json={'tickers':['FPT'],'years':[2030]}).status_code==400
            assert c.get('/api/reports/nonexistent').status_code==404
        for url in ('http://example.com','https://127.0.0.1/a','https://169.254.169.254/a','https://user:pass@example.com/a'):
            with pytest.raises(ValueError):
                validate_url(url)
    finally:
        app.state.service.executor.shutdown(wait=True)


def test_version_replacement_preserves_evidence(tmp_path,pdf_bytes):
    import pymupdf
    s=Service(tmp_path)
    try:
        first=s.ingest('FPT',2024,pdf_bytes)
        with pymupdf.open(stream=pdf_bytes,filetype='pdf') as doc:
            doc.set_metadata({'title':'Synthetic corrected version'})
            replacement=doc.tobytes()
        second=s.ingest('FPT',2024,replacement,replace=True,replacement_reason='Synthetic version test')
        assert second['selected_version']=='2' and second['document_status']=='REVIEW'
        assert second['analysis'] is None and second['sha256']!=first['sha256']
        assert (tmp_path/'pdf'/(first['sha256']+'.pdf')).read_bytes()==pdf_bytes
        assert len(list((tmp_path/'artifacts'/'versions'/'FPT-2024').glob('*.json')))==1
        assert len(s.store.reports())==1
        with pytest.raises(ValueError,match='trùng SHA-256'):
            s.ingest('FPT',2024,replacement,replace=True)
    finally:
        s.executor.shutdown(wait=True)


def test_ocr_raster_page(tmp_path,monkeypatch):
    import os
    import pymupdf
    from PIL import Image,ImageDraw,ImageFont
    from vietfin.pipeline import extract_pdf
    tessdata=os.environ.get('VIETFIN_TESSDATA','/workspace/.local/share/vietfin-dtminer/tessdata')
    if not __import__('pathlib').Path(tessdata,'vie.traineddata').exists():
        pytest.skip('Vietnamese Tesseract model is not installed')
    image=Image.new('RGB',(1600,200),'white')
    ImageDraw.Draw(image).text((20,60),'Doanh nghiệp chuyển đổi số',fill='black',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',48))
    buffer=io.BytesIO();image.save(buffer,format='PNG')
    path=tmp_path/'scan.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page(width=800,height=100)
        page.insert_image(page.rect,stream=buffer.getvalue());doc.save(path)
    pages=extract_pdf(path,tessdata)
    assert pages[0]['ocr'] and pages[0]['ocr_error'] is None
    assert 'chuyển đổi số' in pages[0]['raw_text']


def test_llm_predictions_remain_unreviewed(tmp_path,pdf_bytes,dictionary_bytes,monkeypatch):
    import vietfin.llm
    s=Service(tmp_path)
    try:
        s.dictionary(dictionary_bytes,'fixture.csv',True)
        r=s.ingest('FPT',2024,pdf_bytes)
        wait(s,s.process(r['id']))
        o=s.store.get(r['id'])['analysis']['occurrences'][0]
        monkeypatch.setattr(vietfin.llm,'predict',lambda occurrence:{'context_label':'C2','rationale':'SYNTHETIC prediction','digital_meaning':True,'model':'test-only'})
        s.suggest_ai(r['id'],o['occurrence_id'])
        report=s.store.get(r['id'])
        result=report['analysis']['occurrences'][0]
        assert not result['qa_reviewed'] and result['confidence_score'] is None
        assert report['summary']['metrics']['dt_disc_freq']==0
    finally:
        s.executor.shutdown(wait=True)


def test_persistence_and_dictionary_lock(tmp_path,pdf_bytes,dictionary_bytes):
    s=Service(tmp_path)
    s.dictionary(dictionary_bytes,'fixture.csv',True)
    r=s.ingest('FPT',2024,pdf_bytes)
    wait(s,s.process(r['id']))
    s.executor.shutdown(wait=True)
    restored=Service(tmp_path)
    try:
        assert restored.store.get(r['id'])['analysis']['occurrences']
        with pytest.raises(ValueError,match='từ điển bị khóa'):
            restored.dictionary(dictionary_bytes.replace(b'SYNTHETIC TEST 1,',b'SYNTHETIC TEST ONE,'),'fixture.csv',True)
        summaries=restored.store.summaries()
        assert 'pages' not in summaries[0] and summaries[0]['page_count']==2
    finally:
        restored.executor.shutdown(wait=True)
