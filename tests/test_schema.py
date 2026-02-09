from helixsh.schema import validate_params


def test_validate_params_success():
    schema = {
        "required": ["input", "aligner"],
        "properties": {"input": {"type": "string"}, "aligner": {"type": "string"}},
    }
    params = {"input": "samplesheet.csv", "aligner": "star"}
    result = validate_params(schema, params)
    assert result.ok is True


def test_validate_params_mutually_exclusive():
    schema = {
        "properties": {"star": {"type": "boolean"}, "hisat2": {"type": "boolean"}},
        "mutually_exclusive": [["star", "hisat2"]],
    }
    params = {"star": True, "hisat2": True}
    result = validate_params(schema, params)
    assert result.ok is False
    assert any("Mutually exclusive" in x.message for x in result.issues)
