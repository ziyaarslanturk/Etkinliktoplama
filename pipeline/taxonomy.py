"""4 kademeli filtre ağacı (Ülke > İl > Ana ilgi alanı > Alt tür) ve sınıflandırma kuralları."""
from __future__ import annotations

import re

TAXONOMY: dict[str, list[str]] = {
    "camping": ["tent_fair", "camp_festival", "bushcraft_workshop", "family_camp", "community_meetup"],
    "caravan": ["caravan_expo", "caravan_rally", "offroad_meetup", "tiny_house_fair"],
    "outdoor_sports": ["trekking", "climbing_fest", "trail_run", "water_sports"],
    "music_nature": ["outdoor_concert", "music_camp"],
}

ISO_COUNTRIES = frozenset(
    """AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ
CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR
GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP
KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT
MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW
SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG
UM US UY UZ VA VC VE VG VI VN VU WF WS XK YE YT ZA ZM ZW""".split()
)


def is_valid_class(interest: str | None, sub_type: str | None) -> bool:
    if interest not in TAXONOMY:
        return False
    return sub_type is None or sub_type in TAXONOMY[interest]


# Öncelik sırasına göre kurallar. Metinde kural eşleşmezse etkinlik SINIFLANDIRILAMAZ ve atlanır
# (tahmin yürütülmez). Diller: EN, TR, DE (ek diller kolayca eklenebilir).
_RULES: list[tuple[str, str, str | None]] = [
    (r"tiny[\s-]?house", "caravan", "tiny_house_fair"),
    (r"(caravan|motorhome|camper|wohnmobil|karavan|\brv\b|campervan).{0,40}(rall(y|ye|i)|treffen|bulu[sş]ma)", "caravan", "caravan_rally"),
    (r"(rall(y|ye|i)|treffen).{0,40}(caravan|motorhome|camper|wohnmobil|karavan)", "caravan", "caravan_rally"),
    (r"(caravan|motorhome|camper|wohnmobil|karavan|\brv\b|campervan|caravaning).{0,40}(expo|show|salon|messe|fair|fuar)", "caravan", "caravan_expo"),
    (r"(expo|show|salon|messe|fair|fuar).{0,40}(caravan|motorhome|camper|wohnmobil|karavan|\brv\b|campervan)", "caravan", "caravan_expo"),
    (r"off[\s-]?road|4x4|arazi arac", "caravan", "offroad_meetup"),
    (r"bushcraft", "camping", "bushcraft_workshop"),
    (r"family camp|aile kamp", "camping", "family_camp"),
    (r"(camping|camp|zelt|kamp).{0,20}(festival|fest\b)", "camping", "camp_festival"),
    (r"(tent|zelt|[cç]adir).{0,30}(fair|expo|show|messe|fuar)", "camping", "tent_fair"),
    (r"(camping|camp|kamp|outdoor).{0,40}(fair|expo|messe|fuar)", "camping", "tent_fair"),
    (r"camp(ers|ing)?.{0,20}(meet-?up|meeting|gathering|treffen|bulu[sş]ma)", "camping", "community_meetup"),
    (r"music camp|m[uü]zik kamp", "music_nature", "music_camp"),
    (r"outdoor concert|open[\s-]air|a[cç][iı]k hava konser|freiluft", "music_nature", "outdoor_concert"),
    (r"trail[\s-]?run|ultra[\s-]?trail|sky[\s-]?run|patika ko[sş]u", "outdoor_sports", "trail_run"),
    (r"trekking|hiking|hike\b|wandern|yürüyü[sş]|doğa y[uü]r[uü]y[uü][sş]", "outdoor_sports", "trekking"),
    (r"climbing|mountaineering|bouldering|alpinism|t[iı]rman[iı][sş]|dağc[iı]l[iı]k", "outdoor_sports", "climbing_fest"),
    (r"kayak|canoe|rafting|paddle|dragon boat|su sporlar", "outdoor_sports", "water_sports"),
    (r"\bcamping\b|\bcamp\b|kamp(ç|c)?[iı]?l[iı]k|\bkamp\b|zelten", "camping", None),
    (r"karavan|caravan", "caravan", None),
    (r"outdoor|do[gğ]a sporlar", "outdoor_sports", None),
]
_COMPILED = [(re.compile(p, re.IGNORECASE), i, s) for p, i, s in _RULES]


def classify(text: str | None) -> tuple[str, str | None] | None:
    """Metinden (interest, sub_type) döndürür; eşleşme yoksa None."""
    if not text:
        return None
    for rx, interest, sub in _COMPILED:
        if rx.search(text):
            return interest, sub
    return None
