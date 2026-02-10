from helixsh.provenance import compute_execution_hash


def test_execution_hash_stable():
    h1 = compute_execution_hash("nextflow run x", {"a": 1, "b": 2})
    h2 = compute_execution_hash("nextflow run x", {"b": 2, "a": 1})
    assert h1 == h2
