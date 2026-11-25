import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pipeline import config, feeds, main as pmain
from pipeline.context import Context, SkipSource
from pipeline.normalize import is_expired, make_event, parse_date, parse_time
from pipeline.scrapers import community, federations, local_official, recreation_gov, ticketmaster, wikidata
from pipeline.taxonomy import classify

OK = dict(source="t", title="Test Fuarı", interest="camping", sub_type="tent_fair", start_date="2030-05-01",
          country_code="tr", official_url="https://example.org/x")


class Normalize(unittest.TestCase):
    def test_valid_and_schema(self):
        e = make_event(**OK)
        self.assertEqual(e["location"]["country_code"], "TR")
        self.assertEqual(e["schedule"]["end_date"], "2030-05-01")
        self.assertEqual(e["schedule"]["timezone"], "UTC")
        self.assertIsNone(e["poster_url"])
        self.assertEqual(e["details"]["guests"], [])
        self.assertEqual(make_event(**OK)["id"], e["id"])  # deterministik

    def test_missing_required_skipped(self):
        for k in ("title", "start_date", "country_code", "official_url"):
            bad = dict(OK); bad[k] = None
            self.assertIsNone(make_event(**bad), k)
        self.assertIsNone(make_event(**{**OK, "country_code": "ZZ"}))
        self.assertIsNone(make_event(**{**OK, "official_url": "ftp://x"}))
        self.assertIsNone(make_event(**{**OK, "end_date": "2030-04-01"}))
        self.assertIsNone(make_event(**{**OK, "interest": "bogus"}))

    def test_bad_subtype_becomes_none_and_coords(self):
        e = make_event(**{**OK, "sub_type": "nope", "lat": 200, "lng": 10})
        self.assertIsNone(e["classification"]["sub_type"])
        self.assertIsNone(e["location"]["lat"])

    def test_summary_limit_and_time(self):
        e = make_event(**{**OK, "summary": "a" * 500, "start_time": "2030-05-01T10:30:00"})
        self.assertLessEqual(len(e["details"]["summary"]), 300)
        self.assertEqual(e["schedule"]["start_time"], "10:30")
        self.assertIsNone(parse_time("2030-05-01T00:00:00"))
        self.assertIsNone(parse_date("31/02/2030"))

    def test_expiry(self):
        e = make_event(**{**OK, "start_date": "2026-01-01", "end_date": "2026-01-10"})
        self.assertTrue(is_expired(e, date(2026, 1, 11)))
        self.assertFalse(is_expired(e, date(2026, 1, 10)))


class Classify(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(classify("KARAVANİST Karavan Fuarı"), ("caravan", "caravan_expo"))
        self.assertEqual(classify("Ultra Trail Run 50K"), ("outdoor_sports", "trail_run"))
        self.assertEqual(classify("Tiny House Fair"), ("caravan", "tiny_house_fair"))
        self.assertIsNone(classify("Jazz Night"))
        self.assertIsNone(classify(None))


class Feeds(unittest.TestCase):
    def test_jsonld_and_ics(self):
        html = '<script type="application/ld+json">{"@type":"Event","name":"X Camp Festival","startDate":"2030-06-01","endDate":"2030-06-03","url":"/e/1","location":{"name":"Park","address":{"addressLocality":"Wien","addressCountry":"AT"}}}</script>'
        r = feeds.jsonld_events(html, "https://a.org/list")
        self.assertEqual(r[0]["country"], "AT")
        self.assertEqual(r[0]["url"], "https://a.org/e/1")
        ics = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Camp Festival\nDTSTART;VALUE=DATE:20300601\nDTEND;VALUE=DATE:20300604\nEND:VEVENT\nEND:VCALENDAR"
        ev = feeds.ics_events(ics)[0]
        self.assertEqual((ev["start"], ev["end"]), ("2030-06-01", "2030-06-03"))

    def test_garbage_does_not_raise(self):
        self.assertEqual(feeds.jsonld_events("<script type='application/ld+json'>{bozuk", "https://a"), [])
        self.assertEqual(feeds.ics_events("saçma"), [])


class Sources(unittest.TestCase):
    def test_ticketmaster_map(self):
        raw = {"name": "Summer Camping Festival", "url": "https://tm.example/e", "dates": {"start": {"localDate": "2030-07-01", "localTime": "18:00:00"}, "timezone": "Europe/Berlin"},
               "_embedded": {"venues": [{"name": "V", "city": {"name": "Köln"}, "country": {"countryCode": "DE"}, "location": {"latitude": "50.9", "longitude": "6.9"}}]}}
        e = ticketmaster.map_event(raw)
        self.assertEqual(e["location"]["country_code"], "DE")
        self.assertIsNone(ticketmaster.map_event({**raw, "name": "Rock Konseri"}))
        self.assertIsNone(ticketmaster.map_event({"name": "Camping Festival"}))  # tarih yok

    def test_skip_without_keys(self):
        ctx = Context(env={})
        for m in (ticketmaster, recreation_gov):
            with self.assertRaises(SkipSource):
                m.fetch(ctx)

    def test_wikidata_binding(self):
        b = {"item": {"value": "http://www.wikidata.org/entity/Q1"}, "itemLabel": {"value": "Trekking Festival"},
             "start": {"value": "2030-05-01T00:00:00Z"}, "cc": {"value": "NP"}}
        e = wikidata.map_binding(b)
        self.assertEqual(e["links"]["official_url"], "https://www.wikidata.org/wiki/Q1")
        self.assertIsNone(wikidata.map_binding({**b, "itemLabel": {"value": "Q1"}}))

    def test_tobb_table(self):
        html = "<table><tr><th>Fuar Adı</th><th>Başlangıç</th><th>Bitiş</th><th>Şehir</th></tr><tr><td><a href='/f/1'>Karavan Fuarı</a></td><td>03.02.2030</td><td>07.02.2030</td><td>İstanbul</td></tr><tr><td>Mobilya Fuarı</td><td>01.01.2030</td><td>02.01.2030</td><td>Ankara</td></tr></table>"
        rows = local_official.parse_tobb(html, "https://x")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["start"], "2030-02-03")

    def test_community_isolated_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            good = [{"title": "Gerçek Kamp Festivali", "classification": {"interest": "camping", "sub_type": "camp_festival"},
                     "schedule": {"start_date": "2030-08-01", "end_date": "2030-08-03"}, "location": {"country_code": "TR"},
                     "links": {"official_url": "https://example.org"}}, {"title": "Eksik"}]
            (p / "a.json").write_text(json.dumps(good), encoding="utf-8")
            (p / "b.json").write_text("{bozuk", encoding="utf-8")
            (p / "_c.json").write_text(json.dumps(good), encoding="utf-8")
            old = config.COMMUNITY_DIR
            config.COMMUNITY_DIR = p
            try:
                res = community.fetch(Context())
            finally:
                config.COMMUNITY_DIR = old
            self.assertEqual(len(res), 1)

    def test_federations_skip_without_config(self):
        ctx = Context(env={})
        ctx.sources_config = lambda: {}
        with self.assertRaises(SkipSource):
            federations.fetch(ctx)


class EndToEnd(unittest.TestCase):
    def test_pipeline_isolation_purge_dedupe_output(self):
        class Boom:
            NAME = "boom"
            def fetch(self, ctx): raise RuntimeError("apikey=SECRET patladı")
        class Fixed:
            NAME = "fixed"
            def fetch(self, ctx):
                a = make_event(**{**OK, "start_date": "2030-05-01"})
                old = make_event(**{**OK, "title": "Eski", "start_date": "2020-01-01"})
                dup = make_event(**{**OK, "summary": "daha dolu", "source": "t2"})
                return [a, old, dup]
        with tempfile.TemporaryDirectory() as d:
            old_scr, old_site = pmain.SCRAPERS, config.SITE_DIR
            pmain.SCRAPERS = [Boom(), Fixed()]
            try:
                ctx = Context(env={})
                raw, status = pmain.run_sources(ctx)
                self.assertEqual([s["status"] for s in status], ["error", "ok"])
                self.assertNotIn("SECRET", status[0]["error"])
                events, extra = pmain.finalize(raw, ctx)
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["details"]["summary"], "daha dolu")
                self.assertEqual(extra, {"expired_removed": 1, "duplicates_removed": 1})
                pmain.write_site(events, status, extra, ctx, Path(d))
                for f in ("events.json", "countries.json", "status.json", "taxonomy.json", "index.html", ".nojekyll", "events/TR.json"):
                    self.assertTrue((Path(d) / f).exists(), f)
            finally:
                pmain.SCRAPERS = old_scr


if __name__ == "__main__":
    unittest.main()
