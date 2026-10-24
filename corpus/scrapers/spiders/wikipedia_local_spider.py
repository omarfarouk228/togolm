"""
Spider for the Éwé (ee) and Kabiyè (kbp) Wikipedias.

About 1,400 Éwé and 1,700 Kabiyè articles (2026): the largest freely licensed
texts in Togo's two national languages. Stored with language "ee" / "kbp" so
retrieval for French answers never uses them (see
rag.retrieval.search.RETRIEVAL_LANGUAGE); answers in Éwé or Kabiyè get the
closest passages as wording references (rag.generation.language_reference).

Every article of the main namespace is read (list=allpages), then its plain
text (one extract per request: full extracts can't be batched).
"""

import json
from urllib.parse import urlencode

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider
from scrapers.spiders.wikipedia_spider import WikipediaSpider

WIKIS = {"ee": "ee.wikipedia.org", "kbp": "kbp.wikipedia.org"}
# Local-language articles are often short stubs; 15 words still carry wording.
MIN_WORDS = 15


def _api(host: str, **params) -> str:
    params.update(format="json", utf8="1")
    return f"https://{host}/w/api.php?" + urlencode(params)


class WikipediaLocalSpider(BaseTogoSpider):
    name = "wikipedia_local"
    source = "wikipedia.org"  # per wiki, see make_document
    category = "culture"
    language = "ee"  # per wiki

    custom_settings = WikipediaSpider.custom_settings

    def __init__(self, *args, langs="ee,kbp", **kwargs):
        super().__init__(*args, **kwargs)
        self.langs = [lang for lang in langs.split(",") if lang in WIKIS]

    async def start(self):
        for lang in self.langs:
            yield self._list_request(lang)

    def _list_request(self, lang: str, cont: str | None = None) -> scrapy.Request:
        params = dict(
            action="query", list="allpages", apnamespace=0, apfilterredir="nonredirects",
            aplimit=500,
        )  # fmt: skip
        if cont:
            params["apcontinue"] = cont
        return scrapy.Request(
            _api(WIKIS[lang], **params), callback=self.parse_list, cb_kwargs={"lang": lang}
        )

    def parse_list(self, response, lang: str):
        data = json.loads(response.text)
        for page in data.get("query", {}).get("allpages", []):
            yield scrapy.Request(
                _api(
                    WIKIS[lang],
                    action="query",
                    pageids=page["pageid"],
                    prop="extracts|info",
                    explaintext=1,
                    exlimit=1,
                    inprop="url",
                ),  # fmt: skip
                callback=self.parse_article,
                cb_kwargs={"lang": lang},
            )
        cont = data.get("continue", {}).get("apcontinue")
        if cont:
            yield self._list_request(lang, cont)

    def parse_article(self, response, lang: str):
        data = json.loads(response.text)
        for page in data.get("query", {}).get("pages", {}).values():
            text = (page.get("extract") or "").strip()
            if len(text.split()) < MIN_WORDS:
                continue
            doc = self.make_document(
                response=response,
                title=page.get("title", ""),
                raw_content=text,
                subcategory="encyclopedie",
                metadata={"word_count": len(text.split()), "page_id": page.get("pageid")},
            )
            doc["url"] = page.get("canonicalurl") or page.get("fullurl") or response.url
            doc["source"] = WIKIS[lang]
            doc["language"] = lang
            yield doc
