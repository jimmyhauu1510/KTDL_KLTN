import math
import pytest
from vietfin.core import Matcher, normalize, parse_dictionary, metrics, suggest_label


def test_dictionary_contract(dictionary_bytes):
    d=parse_dictionary(dictionary_bytes,'test.csv')
    assert len(d['concepts'])==107
    with pytest.raises(ValueError,match='KW001'):
        parse_dictionary(dictionary_bytes.replace(b'KW107',b'KW999'),'test.csv')
    with pytest.raises(ValueError,match='Phân nhóm'):
        parse_dictionary(dictionary_bytes.replace(b'TECH_ONLY',b'CORE'),'test.csv')
    with pytest.raises(ValueError,match='hoa/thường'):
        parse_dictionary(dictionary_bytes.replace(b',AI,AI',b',ai,ai'),'test.csv')


def test_longest_non_overlap_boundaries_and_ai():
    d={'concepts':[
        {'concept_id':'KW001','terms':['chuyển đổi số'],'case_sensitive_terms':[]},
        {'concept_id':'KW002','terms':['hệ sinh thái chuyển đổi số'],'case_sensitive_terms':[]},
        {'concept_id':'KW006','terms':['AI'],'case_sensitive_terms':['AI']}]}
    text='ai cũng dùng hệ sinh thái chuyển đổi số, AI; XAI và AIx không tính.'
    hits=Matcher(d).match(text)
    assert [h[2]['concept_id'] for h in hits]==['KW002','KW006']
    assert all(text[s:e]==term for s,e,_,term in hits)


def test_nfc_offsets():
    original='A\tchuyển  đổi\nsố'
    text,mapping=normalize(original)
    assert text=='A chuyển đổi số'
    assert len(mapping)==len(text)+1
    assert original[mapping[text.index('c')]]=='c'


def test_context_suggestions_never_confidence():
    assert suggest_label('FPT cung cấp dịch vụ AI cho khách hàng.')[0]=='C2'
    assert suggest_label('Khách hàng tự triển khai AI.')[0]=='C4'
    assert suggest_label('Chưa triển khai AI nội bộ.')[0]=='C5'


def test_metrics_kw086_missing_and_review(dictionary_bytes):
    d=parse_dictionary(dictionary_bytes,'test.csv')
    occurrences=[{'concept_id':cid,'context_label':label,'qa_reviewed':True,'digital_meaning':True} for cid,label in [('KW006','C1'),('KW001','C2'),('KW002','C4'),('KW086','C1')]]
    r={'document_status':'REVIEW','analysis':{'occurrences':occurrences,'total_words_full':100,'total_words_narr':80}}
    m=metrics(r,d)
    assert m['tech_freq']==4 and m['dt_raw_freq']==3 and m['dt_disc_freq']==2
    assert m['dt_implement_freq']==1 and m['dt_broad_freq']==3
    assert m['dt_index']==math.log1p(2) and m['digital_dummy'] is None
    r['document_status']='OK'
    assert metrics(r,d)['digital_dummy']==1
    assert all(v is None for v in metrics({'document_status':'MISSING'},d).values())
    r['analysis']['total_words_full']=0
    assert metrics(r,d)['dt_index'] is None
