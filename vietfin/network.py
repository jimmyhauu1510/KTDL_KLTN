"""Conservative HTTPS ingestion. No credentials, private-network targets or HTML execution."""
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit
from html.parser import HTMLParser
import httpx


def validate_url(url):
    parsed=urlsplit(url)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError("Chỉ nhận HTTPS công khai cổng 443, không có thông tin đăng nhập")
    try:
        addresses=socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("Không phân giải được hostname nguồn: "+parsed.hostname) from exc
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Không cho phép địa chỉ nội bộ/loopback/metadata")
    return url


def fetch(url, limit=100*1024*1024):
    # Proxy/trust configuration supplied by cloud runtime remains intact.
    with httpx.Client(timeout=60,follow_redirects=False) as client:
        for _ in range(6):
            validate_url(url)
            with client.stream("GET",url,headers={"User-Agent":"VietFin-DTMiner/0.1 research; single-request ingestion"}) as response:
                if response.status_code in {301,302,303,307,308}:
                    if not response.headers.get('location'):
                        raise ValueError("Nguồn trả chuyển hướng không có Location")
                    url=urljoin(url,response.headers["location"])
                    continue
                response.raise_for_status()
                parts,total=[],0
                for chunk in response.iter_bytes():
                    total+=len(chunk)
                    if total>limit:
                        raise ValueError("Tệp vượt giới hạn kích thước")
                    parts.append(chunk)
                return b"".join(parts),url
    raise ValueError("Quá nhiều chuyển hướng")


def discover(url):
    content,final=fetch(url,2*1024*1024)
    links=[]
    class Parser(HTMLParser):
        def handle_starttag(self,tag,attrs):
            if tag=="a":
                href=dict(attrs).get("href","")
                target=urljoin(final,href)
                if urlsplit(target).scheme=="https" and urlsplit(target).path.lower().endswith(".pdf"):
                    links.append(target)
    Parser().feed(content.decode("utf-8",errors="replace"))
    return sorted(set(links))[:500]
