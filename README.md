# Kamp & Doğa Etkinlikleri Veri Boru Hattı

GitHub Actions ile **her 6 saatte bir** (günde 4 kez) etkinlik verisi toplar, doğrular, süresi geçenleri siler ve
**GitHub Pages**'e yayınlar. Üretilen JSON dosyaları `main` dalına commit edilmez (repo şişmez).

## Kurulum (bir kez)
1. GitHub'da yeni repo aç, bu klasörün içindekileri repo köküne yükle.
2. **Settings → Pages → Build and deployment → Source: `GitHub Actions`** seç.
3. (İsteğe bağlı) **Settings → Secrets and variables → Actions → New repository secret**:
   * `TICKETMASTER_API_KEY` – Ticketmaster Discovery API anahtarı
   * `RIDB_API_KEY` – Recreation.gov (RIDB) API anahtarı
   Anahtar yoksa ilgili modül hata vermeden atlanır.
4. **Actions → "Etkinlik Veri Boru Hattı" → Run workflow** ile ilk yayını başlat. Sonrası otomatiktir.

## Yayın adresleri
`https://<kullanici>.github.io/<repo>/` altında:
`events.json` (hepsi) · `events/<ÜLKE>.json` (ülke bazlı) · `countries.json` · `taxonomy.json` · `status.json` (kaynak durumu/sağlık)

## Kurallar nasıl sağlanıyor
| Kural | Uygulama |
|---|---|
| Sıfır yalan veri | Zorunlu alan (başlık, başlangıç tarihi, ülke kodu, resmî URL, geçerli kategori) eksikse kayıt sessizce atlanır. Serbest metinden tarih/konum tahmini yapılmaz; sınıflandırılamayan kayıt alınmaz. |
| Hata vermeme | Her kaynak kendi `try/except` bloğunda; ağ katmanı 404/429/5xx/timeout/SSL/bozuk JSON'da istisna fırlatmaz. Bir kaynak çökerse önceki yayındaki **gerçek** kayıtları korunur (yeni veri uydurulmaz). |
| Süresi geçen veri | `end_date` (yoksa `start_date`) bugünün UTC tarihinden küçükse her taramada silinir. |
| Tekrarsız | `id` = ülke + başlangıç + başlık üzerinden deterministik SHA-256; kaynaklar arası yinelenenlerde daha dolu kayıt seçilir. |

## Kaynaklar (`pipeline/scrapers/`)
`ticketmaster` · `recreation_gov` · `federations` (F.I.C.C., UIAA) · `wikidata` · `local_official` (TOBB Fuar Takvimi + yapılandırılabilir) · `community`

* `config/sources.json`: federasyon/yerel sayfa adresleri. Bu sayfalardan yalnızca **schema.org/Event (JSON-LD)** veya **.ics** varsa kayıt üretilir. Adres değiştirmek/eklemek için bu dosyayı düzenle.
* `community_events/*.json`: elle eklediğin doğrulanmış etkinlikler (bkz. `community_events/README.md`).
* Sağlık kontrolü: yayındaki `status.json` her kaynağın `ok / empty / skipped / error` durumunu gösterir.

## Kategori ağacı
`taxonomy.json` — camping, caravan, outdoor_sports, music_nature ve alt türleri (kod: `pipeline/taxonomy.py`).
Metin sınıflandırma kuralları (EN/TR/DE) aynı dosyadadır; yeni dil/anahtar kelime eklenebilir.

## Yerel çalıştırma / test
```
python -m unittest discover -s tests -v
TICKETMASTER_API_KEY=xxx python -m pipeline.main   # çıktı: site/
```
Harici bağımlılık yoktur (yalnızca Python 3.10+ standart kütüphane).
