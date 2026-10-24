"""
Spider for the ministries on the government's React platform (see
wp_platform), read from their public WordPress REST APIs.

Found on 2026-10-24 by probing bk.<ministry>.gouv.tg/wp-json. environnement
moved there from its old WordPress site (its sitemaps in gouv_ministry
stopped bringing anything in June 2026); the others were not in the corpus.
Health (sante-assurances.gouv.tg) has its own spider on the same base.
"""

from scrapers.spiders.wp_platform import WordPressPlatformSpider


def _site(name: str, category: str) -> dict:
    return {
        "api": f"https://bk.{name}.gouv.tg",
        "public": f"https://{name}.gouv.tg",
        "source": f"{name}.gouv.tg",
        "category": category,
    }


class GouvPlatformSpider(WordPressPlatformSpider):
    name = "gouv_platform"
    source = "gouv.tg"  # per site, see SITES
    category = "administrative"

    SITES = [
        _site("fonctionpublique", "administrative"),  # civil service, pensions (~95 posts)
        _site("diplomatie", "politics"),  # foreign affairs, cooperation (~470)
        _site("numerique", "economy"),  # digital economy (~340)
        _site("transports", "economy"),  # transport, opening up regions (~40)
        _site("communication", "politics"),  # communication, media (~210)
        _site("defense", "politics"),  # national defence (~430)
        _site("planification", "economy"),  # planning, development (~380)
        _site("environnement", "agriculture"),  # environment (~580)
        _site("eau", "administrative"),  # water, local development (~120)
        _site("economie", "economy"),  # economy (~12)
    ]
