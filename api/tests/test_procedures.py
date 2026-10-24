"""Administrative procedures as structured cards."""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app.features.bots import core
from api.app.main import app
from rag.procedures import parse_procedure, procedure_card

client = TestClient(app)

SERVICE_PUBLIC = (
    "Description: Copie officielle d'un acte d'état civil | "
    "Identification des personnes susceptibles / légitimes à faire la demande: L'intéressé | "
    "Conditions: Conditions Avoir un acte enregistré | "
    "Etapes: 1. Remplir le formulaire en ligne 2. Payer les frais 3. Retirer la copie | "
    "Pièces à fournir: Numéro de l'acte ; Pièce d'identité | "
    "Délai d'exécution: 72 heures | Coût de la procédure: 2 000 FCFA | "
    "Durée de validité: N/A | Contact: Fournisseur de service Mairie de Lomé "
    "[email protected] Partager"
)
EREGULATIONS = (
    "Procédure administrative au Togo : Zone franche – Carnet bleu – Renouvellement. "
    "Étapes : 1. Déposer le carnet bleu ; 2. Payer les frais. Où aller : Division des "
    "opérations douanières de la zone franche. Pièces à fournir : Carnet bleu ; Reçu. "
    "Coût : 10 000 CFA pour les frais de renouvellement du carnet bleu. Durée totale : 2 "
    "jours à 2 jours 55 min (journées de travail de 8 heures). Ce que vous obtenez : Carnet "
    "bleu renouvelé. Base légale : Courrier DG SAZOF sur le carnet bleu."
)


def test_service_public_fields():
    card = parse_procedure(SERVICE_PUBLIC)
    assert card["steps"] == [
        "Remplir le formulaire en ligne",
        "Payer les frais",
        "Retirer la copie",
    ]
    assert card["documents"] == ["Numéro de l'acte", "Pièce d'identité"]
    assert card["conditions"] == "Avoir un acte enregistré"  # repeated label dropped
    assert card["cost"] == "2 000 FCFA"
    assert card["duration"] == "72 heures"
    assert card["office"] == "Mairie de Lomé"
    assert "validity" not in card  # N/A


def test_eregulations_fields_from_one_paragraph():
    card = parse_procedure(EREGULATIONS)
    assert card["steps"] == ["Déposer le carnet bleu", "Payer les frais"]
    assert card["cost"] == "10 000 CFA pour les frais de renouvellement du carnet bleu"
    assert card["duration"].startswith("2 jours à 2 jours 55 min")
    assert card["office"] == "Division des opérations douanières de la zone franche"
    assert card["legal"] == "Courrier DG SAZOF sur le carnet bleu"


def test_news_text_is_not_a_procedure():
    assert (
        procedure_card("1", "t", "u", "s", "Le ministre a visité Kara : il a salué les élus.")
        is None
    )


def test_procedures_api_lists_searches_and_shows_a_card():
    from db import get_conn
    from rag.indexation.ingestor import upsert_document

    url = f"https://service-public.gouv.tg/service/test-{uuid.uuid4()}"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            doc_id = upsert_document(
                cur,
                {
                    "source": "service-public.gouv.tg",
                    "url": url,
                    "category": "administrative",
                    "title": "Demande d'une copie d'acte d'état civil",
                    "raw_content": SERVICE_PUBLIC,
                    "clean_content": SERVICE_PUBLIC,
                },
            )
        conn.commit()

        found = client.get("/v1/procedures", params={"q": "copie acte état civil"}).json()
        assert any(item["id"] == str(doc_id) for item in found["items"])
        card = client.get(f"/v1/procedures/{doc_id}").json()
        assert card["cost"] == "2 000 FCFA"
        assert card["url"] == url
        assert client.get("/v1/procedures/not-a-uuid").status_code == 404
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE url = %s", (url,))
        conn.commit()
        conn.close()


def test_answers_carry_the_card_of_a_procedure_source():
    from api.app.features.query import router as query_router

    card = {"id": "1", "title": "Carnet bleu", "cost": "10 000 CFA"}
    sources = [
        {"title": "Article", "url": "https://icilome.com/x", "score": 0.9},
        {
            "title": "Carnet bleu",
            "url": "https://investirautogo.tg/procedure/120?l=fr",
            "score": 0.8,
        },
    ]
    with patch("api.app.features.procedures.router.card_for_url", return_value=card) as lookup:
        assert query_router._procedure_for(sources) == card
    lookup.assert_called_once_with("https://investirautogo.tg/procedure/120?l=fr")
    assert query_router._procedure_for(sources[:1]) is None


def test_bot_reply_includes_the_exact_checklist():
    card = parse_procedure(SERVICE_PUBLIC) | {"title": "Copie d'acte d'état civil"}
    (message,) = core.render(core.Answer("Voici la démarche.", [], card), "whatsapp")
    assert "*📋 Fiche : Copie d'acte d'état civil*" in message
    assert "☐ Pièce d'identité" in message
    assert "💰 *Coût* : 2 000 FCFA" in message
