"""
Taxonomy and category classification for event pipeline.
Categorizes events by interest: concert, festival, fair, camping, outdoor, sport, culture, other.
Provides ISO_COUNTRIES, VALID_INTERESTS, and is_valid_class validator.
"""

import re
from typing import Tuple, Dict, Any, Union, Set

ISO_COUNTRIES: Set[str] = {
    "TR", "US", "DE", "FR", "GB", "NL", "IT", "ES", "AT", "CH", "BE", "SE", "NO", "FI",
    "DK", "PL", "CZ", "GR", "PT", "IE", "CA", "AU", "NZ", "JP", "KR", "BR", "MX", "AR",
    "EG", "AE", "SA", "QA", "AZ", "GE", "RU", "UA", "RO", "BG", "HU", "SK", "HR", "RS"
}

VALID_INTERESTS: Set[str] = {
    "concert", "festival", "fair", "camping", "outdoor", "sport", "culture", "other",
    "music", "sports", "arts", "family", "community", "conference"
}

TAXONOMY_MAP = {
    "concert": [
        "concert", "konser", "müzik", "music", "live band", "canlı müzik", "orkestra",
        "akustik", "sahne", "senfoni", "filarmoni", "recital", "resital", "dj set",
        "rock", "pop", "jazz", "caz", "rap", "hiphop", "metal", "blues", "klasik müzik"
    ],
    "festival": [
        "festival", "fest", "şenlik", "panayır", "karnaval", "carnival", "fiesta",
        "bazaars", "gala", "kutlama", "yıl dönümü", "şenliği"
    ],
    "fair": [
        "fair", "fuar", "expo", "exhibition", "sergi", "panayır", "bazaar", "ticaret fuarı",
        "tanıtım günleri", "ziyaret", "otobüs fuarı", "karavan fuarı", "kitap fuarı"
    ],
    "camping": [
        "camp", "camping", "kamp", "karavan", "caravan", "tiny house", "çadır",
        "kamp ateşi", "glamping", "kampçılık", "doğa kampı", "gençlik kampı"
    ],
    "outdoor": [
        "outdoor", "doğa", "nature", "trekking", "hiking", "yürüyüş", "doğa yürüyüşü",
        "tırmanış", "climbing", "dağcılık", "mountaineering", "rafting", "kanyon",
        "yamaç paraşütü", "paragliding", "safari", "bisiklet turu", "cycling",
        "orienteering", "oryantiring", "mağaracılık", "caving", "su sporları"
    ],
    "sport": [
        "sport", "sports", "spor", "maraton", "marathon", "koşu", "run", "running",
        "race", "yarış", "turnuva", "tournament", "lig", "league", "match", "maç",
        "futbol", "basketbol", "voleybol", "tenis", "yüzme", "triatlon"
    ],
    "culture": [
        "theater", "theatre", "tiyatro", "gösteri", "show", "sinema", "cinema", "movie",
        "film", "atölye", "workshop", "konferans", "seminer", "panel", "söyleşi",
        "bale", "dans", "dance", "opera", "müze", "museum"
    ]
}

def is_valid_class(classification: Union[Dict[str, Any], str]) -> bool:
    """Validates whether a classification object or string interest is valid."""
    if not classification:
        return False
    if isinstance(classification, str):
        return classification.lower() in VALID_INTERESTS
    if isinstance(classification, dict):
        interest = classification.get("interest", "")
        return str(interest).lower() in VALID_INTERESTS
    return False

def classify_event(title: str, description: str = "") -> Tuple[str, str]:
    """
    Classifies an event based on title and description into (interest, sub_type).
    Returns ("other", "") if no category matches.
    """
    text = f"{title} {description}".lower()

    for category, keywords in TAXONOMY_MAP.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                sub_type = kw.capitalize()
                return category, sub_type

    return "other", ""
