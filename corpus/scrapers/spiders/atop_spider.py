"""
Spider for atop.tg — Agence Togolaise de Presse, the official press agency.

~16,000 articles since 2022 (institutional news from every region), read from
the site's public WordPress REST API: its HTML pages and metadata show a
broken publication date (1 January 1970) while the API has the real one.
Crawled daily with the news spiders: with SKIP_KNOWN_URLS only the 500 newest
posts are read (the first run reads the whole archive, SKIP_KNOWN_URLS=0).
"""

from scrapers.spiders.wp_platform import WordPressPlatformSpider

# ATOP category slug -> subcategory. Topics use the corpus categories so the
# category filter (category OR subcategory) finds them; regions are kept as is.
ATOP_SUBCATEGORIES = {
    "sante": "health",
    "education": "education",
    "economie": "economy",
    "agriculture": "agriculture",
    "elevage": "agriculture",
    "environnement": "environnement",
    "politique": "politics",
    "elections-legislatives-regionales-2024": "politics",
    "decentralisation": "politics",
    "securite": "securite",
    "sports": "sport",
    "culture": "culture",
    "technologies": "technologies",
    "statistique": "economy",
    "developpement": "developpement",
    "inter": "international",
    "maritime-regions": "region-maritime",
    "plateaux-regions": "region-plateaux",
    "centrale-regions": "region-centrale",
    "kara-regions": "region-kara",
    "savanes-regions": "region-savanes",
    "societe": "societe",
}


class AtopSpider(WordPressPlatformSpider):
    name = "atop"
    source = "atop.tg"
    category = "press"
    incremental_pages = 5

    SITES = [
        {
            "api": "https://atop.tg",
            "public": None,  # the post's own link
            "source": "atop.tg",
            "category": "press",
            "documentation": False,
            "subcategories": ATOP_SUBCATEGORIES,
        }
    ]
