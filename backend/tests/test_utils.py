from app.utils import extract_issue_keys, extract_paths, jaccard


def test_extract_issue_keys():
    assert extract_issue_keys("Impacta HU-1234 y BUG-22") == {"HU-1234", "BUG-22"}


def test_extract_paths():
    paths = extract_paths("Usa GET /api/prestadores y /api/prestadores/{cuit}")
    assert "/api/prestadores" in paths
    assert "/api/prestadores/{cuit}" in paths


def test_similarity():
    assert jaccard("buscar prestadores especialidad", "prestadores por especialidad") > 0
