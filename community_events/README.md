# Topluluk / Manuel Etkinlik Havuzu

Bu klasöre eklediğin **`*.json`** dosyaları her taramada otomatik okunur (`_` ile başlayan dosyalar yok sayılır).

* Dosya içeriği: etkinlik listesi `[ {...}, {...} ]` veya `{ "events": [ ... ] }`.
* Her etkinlik **standart şemada** olmalı (bkz. `SABLON.json.example`).
* Zorunlu alanlar: `title`, `classification.interest`, `schedule.start_date`, `location.country_code`, `links.official_url`.
  Eksik/geçersiz kayıtlar sessizce atlanır. Tarihi geçen kayıtlar otomatik silinir.
* Sadece **gerçek ve doğruladığın** etkinlikleri ekle; örnek/uydurma veri ekleme.
* Geçerli değerler için `site/taxonomy.json` veya proje README'sine bak.
