"""Crawl Google Scholar stats for the homepage.

Exit codes:
  0 = success, results/gs_data.json + results/gs_data_shieldsio.json written
  3 = Scholar unreachable from this network (Google blocks/captchas cloud IPs)

GitHub-hosted runners are blocked by Google Scholar, so CI treats exit 3 as
"keep the previous snapshot" rather than a hard failure. For a guaranteed
refresh run google_scholar_crawler/local_update.py on a network that can
reach scholar.google.com.
"""
import json
import os
import sys
import time
from datetime import datetime

import httpx


def _sanitize_no_proxy():
    # httpx parses NO_PROXY entries as URL patterns; a bare bracketed IPv6 like
    # "[::1]" (present in some proxy setups) raises InvalidURL at import time.
    # Drop bracketed entries; losing an IPv6 loopback bypass is harmless here.
    for key in ('NO_PROXY', 'no_proxy'):
        val = os.environ.get(key)
        if not val:
            continue
        safe = [p.strip() for p in val.split(',') if p.strip() and '[' not in p and ']' not in p]
        if safe:
            os.environ[key] = ','.join(safe)
        else:
            os.environ.pop(key, None)


_sanitize_no_proxy()

# scholarly's httpx client sets no timeout by default. Google drops packets
# from cloud IPs, so an unbounded request would hang until the step timeout.
# Bound every request scholarly makes instead.
_orig_client_init = httpx.Client.__init__


def _client_init_with_timeout(self, *args, **kwargs):
    kwargs.setdefault('timeout', httpx.Timeout(25.0, connect=10.0))
    return _orig_client_init(self, *args, **kwargs)


httpx.Client.__init__ = _client_init_with_timeout

from scholarly import scholarly  # noqa: E402  (import after the timeout patch)

SCHOLAR_ID = os.environ.get('GOOGLE_SCHOLAR_ID', 'KpVFMqYAAAAJ')
ATTEMPTS = 3


def log(msg):
    print(msg, flush=True)


def crawl():
    author = scholarly.search_author_id(SCHOLAR_ID)
    scholarly.fill(author, sections=['basics', 'indices', 'counts', 'publications'])
    return author


def main():
    author = None
    for attempt in range(1, ATTEMPTS + 1):
        log(f'[crawl] attempt {attempt}/{ATTEMPTS}')
        try:
            author = crawl()
            break
        except Exception as exc:  # noqa: BLE001 - any fetch error is retryable
            log(f'[crawl] attempt {attempt} failed: {type(exc).__name__}: {exc}')
            if attempt < ATTEMPTS:
                time.sleep(5 * attempt)
    if author is None:
        log('[crawl] Google Scholar unreachable from this network (blocked/captcha).')
        return 3

    name = author['name']
    author['updated'] = str(datetime.now())
    pubs = {}
    for v in author['publications']:
        if not v.get('title'):
            v['title'] = (v.get('bib') or {}).get('title')
        pubs[v['author_pub_id']] = v
    author['publications'] = pubs
    log(f"[crawl] ok: {name}, citedby={author['citedby']}, hindex={author['hindex']}, pubs={len(pubs)}")

    os.makedirs('results', exist_ok=True)
    with open('results/gs_data.json', 'w', encoding='utf-8') as outfile:
        json.dump(author, outfile, ensure_ascii=False)

    shieldio_data = {
        'schemaVersion': 1,
        'label': 'citations',
        'message': f"{author['citedby']}",
    }
    with open('results/gs_data_shieldsio.json', 'w', encoding='utf-8') as outfile:
        json.dump(shieldio_data, outfile, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())