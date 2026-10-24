"""
Spider for investirautogo.tg — Togo's investment portal, an eRegulations site
(UNCTAD): each administrative procedure for businesses (free zone, investment
code, company life, imports and exports...) described step by step, with the
office to go to, documents to bring, costs, time and legal basis.

The pages are rendered in the browser from a JSON API
(/api/procedure/{id}/blocksteps, /requeriments, /costs, /timeframe...). Each
procedure is assembled into one plain-text document, stored under its public
URL (/procedure/{id}?l=fr). ~54 procedures, all linked from the home page menu.
"""

import html
import json
import re

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

BASE = "https://investirautogo.tg"
PARTS = (
    "breadcrumb",
    "blocksteps/",
    "institutions/",
    "requeriments/",
    "costs",
    "timeframe",
    "results/",
    "laws/",
    "additionalinfo",
)
WORKDAY_MINUTES = 8 * 60  # eRegulations counts time in minutes of 8-hour days


def _duration(minutes: float) -> str:
    days, rest = divmod(int(minutes), WORKDAY_MINUTES)
    hours, mins = divmod(rest, 60)
    parts = [f"{days} jour{'s' if days > 1 else ''}"] if days else []
    if hours:
        parts.append(f"{hours} h")
    if mins:
        parts.append(f"{mins} min")
    return " ".join(parts) or "0 min"


def _amount(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def procedure_text(data: dict) -> tuple[str, str]:
    """(title, text) of a procedure from its API parts."""
    trail = [b["Name"].strip() for b in data.get("breadcrumb") or [] if b.get("Name")]
    title = " – ".join(dict.fromkeys(t.capitalize() if t.isupper() else t for t in trail))
    lines = [f"Procédure administrative au Togo : {title}."]

    steps = [s for block in data.get("blocksteps/") or [] for s in block.get("Steps", [])]
    if steps:
        numbered = " ; ".join(f"{i}. {s['Name']}" for i, s in enumerate(steps, 1))
        lines.append(f"Étapes : {numbered}.")
    offices = [i["Name"] for i in data.get("institutions/") or []]
    if offices:
        lines.append("Où aller : " + " ; ".join(offices) + ".")
    docs = []
    for r in data.get("requeriments/") or []:
        doc = r.get("RequirementName", "")
        if r.get("CopiesText"):
            doc += f" ({r['CopiesText']})"
        if r.get("Comments"):
            doc += f" : {r['Comments']}"
        docs.append(doc)
    if docs:
        lines.append("Pièces à fournir : " + " ; ".join(docs) + ".")
    costs = [
        f"{_amount(c['Value'])} {c.get('Unit') or 'FCFA'} {c.get('Comments') or ''}".strip()
        for c in data.get("costs") or []
        if not c.get("IsSeparator") and c.get("Value")
    ]
    lines.append("Coût : " + (" ; ".join(costs) if costs else "gratuit") + ".")
    total = (data.get("timeframe") or {}).get("Total") or {}
    if total.get("Max"):
        span = _duration(total.get("Min") or 0)
        if total["Max"] != total.get("Min"):
            span += f" à {_duration(total['Max'])}"
        lines.append(f"Durée totale : {span} (journées de travail de 8 heures).")
    results = [r["Name"] for r in data.get("results/") or []]
    if results:
        lines.append("Ce que vous obtenez : " + " ; ".join(results) + ".")
    laws = [law["Name"] for law in data.get("laws/") or []]
    if laws:
        lines.append("Base légale : " + " ; ".join(laws) + ".")
    info = (data.get("additionalinfo") or {}).get("Text") or ""
    info = html.unescape(re.sub(r"<[^>]+>", " ", info))
    if info.strip():
        lines.append("Informations complémentaires : " + " ".join(info.split()))
    return title, "\n".join(lines)


class ERegulationsSpider(BaseTogoSpider):
    name = "eregulations"
    source = "investirautogo.tg"
    category = "administrative"

    start_urls = [f"{BASE}/"]

    def parse(self, response):
        ids = sorted({int(i) for i in re.findall(r"/procedure/(\d+)", response.text)})
        for pid in ids:
            yield self._part_request(pid, 0, {})

    def _part_request(self, pid: int, index: int, data: dict) -> scrapy.Request:
        part = PARTS[index]
        return scrapy.Request(
            f"{BASE}/api/procedure/{pid}/{part}?l=fr",
            headers={"Accept": "application/json"},
            callback=self.parse_part,
            cb_kwargs={"pid": pid, "index": index, "data": data},
            dont_filter=True,
        )

    def parse_part(self, response, pid: int, index: int, data: dict):
        try:
            data[PARTS[index]] = json.loads(response.text) if response.status == 200 else None
        except ValueError:
            data[PARTS[index]] = None
        if index + 1 < len(PARTS):
            yield self._part_request(pid, index + 1, data)
            return
        title, text = procedure_text(data)
        if not title or len(text.split()) < 20:
            return
        doc = self.make_document(
            response=response,
            title=title,
            raw_content=text,
            subcategory="demarche",
            metadata={"word_count": len(text.split()), "procedure_id": pid},
        )
        doc["url"] = f"{BASE}/procedure/{pid}?l=fr"
        yield doc
