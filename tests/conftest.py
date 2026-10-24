"""Synthetic fixtures only. These concepts and documents are NOT research inputs."""
import csv
import io
import pytest
import pymupdf


@pytest.fixture
def dictionary_bytes():
    stream=io.StringIO()
    writer=csv.DictWriter(stream,fieldnames=['concept_id','keyword_name','concept_group','category','terms','case_sensitive_terms'])
    writer.writeheader()
    for i in range(1,108):
        term='AI' if i==6 else ('CNTT' if i==86 else f'SYNTHETICCONCEPT{i:03d}')
        writer.writerow(dict(concept_id=f'KW{i:03d}',keyword_name=f'SYNTHETIC TEST {i}',concept_group='TEST_ONLY',
            category='CORE' if i<=39 else 'CONTEXT' if i<=85 else 'TECH_ONLY',terms=term,case_sensitive_terms=term if i in (6,86) else ''))
    return stream.getvalue().encode()


@pytest.fixture
def pdf_bytes():
    doc=pymupdf.open()
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    for n in range(2):
        page=doc.new_page()
        lines=['Doanh nghiệp triển khai AI trong quản trị nội bộ.'] if n==0 else []
        lines += [f'Đây là đoạn văn bản không chứa từ khóa dùng kiểm tra độc lập số {n*15+i}.' for i in range(15)]
        for i,line in enumerate(lines):
            page.insert_text((30,50+i*35),line,fontname='vn',fontfile=font,fontsize=10)
    content=doc.tobytes()
    doc.close()
    return content
