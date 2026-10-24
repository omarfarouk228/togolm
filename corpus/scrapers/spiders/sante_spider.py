"""
Spider for the Ministry of Health (sante-assurances.gouv.tg).

sante.gouv.tg 301-redirects to sante-assurances.gouv.tg, a site of the
government's React platform (see wp_platform): ~640 articles and ~90
documentation PDFs (clinical guides, health accounts, bulletins, calls for
applications), ~100 MB in total.
"""

from scrapers.spiders.wp_platform import WordPressPlatformSpider

API = "https://bk.sante.gouv.tg/wp-json/wp/v2"


class SanteSpider(WordPressPlatformSpider):
    name = "sante"
    source = "sante-assurances.gouv.tg"
    category = "health"

    SITES = [
        {
            "api": "https://bk.sante.gouv.tg",
            "public": "https://sante-assurances.gouv.tg",
            "source": "sante-assurances.gouv.tg",
            "category": "health",
        }
    ]
