"""Wikidata SPARQL: gelecekteki festival kayıtları; yalnızca doğa/kamp anahtar kelimesiyle sınıflananlar alınır."""
from __future__ import annotations

import re

from ..context import Context
from ..httpclient import fetch_json
from ..normalize import make_event
from ..taxonomy import classify

NAME = "wikidata"
ENDPOINT = "https://query.wikidata.org/sparql"

QUERY = """
SELECT ?item ?itemLabel ?itemDescription ?start ?end ?cc ?website ?coord ?venueLabel WHERE {{
  ?item wdt:P31 ?type .
  ?type wdt:P279* wd:Q132241 .
  ?item wdt:P580 ?start .
  FILTER(?start >= "{today}T00:00:00Z"^^xsd:dateTime)
  ?item wdt:P17 ?country .
  ?country wdt:P297 ?cc .
  OPTIONAL {{ ?item wdt:P582 ?end . }}
  OPTIONAL {{ ?item wdt:P856 ?website . }}
  OPTIONAL {{ ?item wdt:P625 ?coord . }}
  OPTIONAL {{ ?item wdt:P276 ?venue . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,tr,de,fr,es". }}
}}
LIMIT 5000
"""


def _v(b: dict, k: str):
    x = b.get(k)
    return x.get("value") if isinstance(x, dict) else None


def map_binding(b: dict) -> dict | None:
    label = _v(b, "itemLabel")
    if not label or re.fullmatch(r"Q\d+", label):
        return None
    desc = _v(b, "itemDescription")
    cls = classify(f"{label} {desc or ''}")
    if not cls:
        return None
    qid = (_v(b, "item") or "").rsplit("/", 1)[-1]
    if not re.fullmatch(r"Q\d+", qid):
        return None
    lat = lng = None
    m = re.match(r"Point\(([-\d.eE+]+)\s+([-\d.eE+]+)\)", _v(b, "coord") or "")
    if m:
        lng, lat = m[1], m[2]
    official = _v(b, "website") or f"https://www.wikidata.org/wiki/{qid}"
    venue = _v(b, "venueLabel")
    if venue and re.fullmatch(r"Q\d+", venue):
        venue = None
    return make_event(
        source=NAME, title=label, interest=cls[0], sub_type=cls[1],
        start_date=_v(b, "start"), end_date=_v(b, "end"), country_code=_v(b, "cc"),
        venue=venue, lat=lat, lng=lng, summary=desc, official_url=official, verified=False,
    )


def fetch(ctx: Context) -> list[dict]:
    data = fetch_json(ENDPOINT, params={"format": "json", "query": QUERY.format(today=ctx.today.isoformat())},
                      headers={"Accept": "application/sparql-results+json"}, retries=3, timeout=90)
    if not isinstance(data, dict):
        raise RuntimeError("Wikidata yanıt vermedi")
    out: dict[str, dict] = {}
    for b in ((data.get("results") or {}).get("bindings")) or []:
        try:
            e = map_binding(b)
        except Exception:
            continue
        if e:
            out[e["id"]] = e
    return list(out.values())
