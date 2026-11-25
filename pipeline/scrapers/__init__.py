"""Kaynak modülleri. Her modül: NAME ve fetch(ctx) -> list[dict] sağlar."""
from . import community, federations, local_official, recreation_gov, ticketmaster, wikidata

SCRAPERS = [ticketmaster, recreation_gov, federations, wikidata, local_official, community]
