from unittest.mock import MagicMock, patch

from rag.generation import language_reference


def test_french_answers_get_no_reference():
    assert language_reference.reference_block("fr", "Comment obtenir un passeport ?") == ""


def test_reference_passages_for_ewe():
    embedder = MagicMock(model_id="gemini-embedding-001@384")
    embedder.encode_query.return_value = [0.1] * 384
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = [("Lomé", "Lomé nye Togo fe fiadudu. " * 40)]
    with (
        patch("rag.retrieval.search._get_embedder", return_value=embedder),
        patch.object(language_reference, "get_conn", return_value=conn),
    ):
        block = language_reference.reference_block("ee", "Où se trouve Lomé ?")

    assert block.startswith("TEXTES DE RÉFÉRENCE EN ÉWÉ")
    assert "jamais comme source" in block
    assert "- Lomé : Lomé nye Togo" in block
    assert len(block) < 800
    params = cur.execute.call_args.args[1]
    assert params[0] == "ee"


def test_reference_failure_never_breaks_answering():
    with patch("rag.retrieval.search._get_embedder", side_effect=RuntimeError("quota")):
        assert language_reference.reference_block("kbp", "Kara") == ""
