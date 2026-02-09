from helixsh.intent import intent_to_nf_args, parse_intent


def test_parse_intent_rnaseq_low_mem_resume():
    result = parse_intent("run nf-core rnaseq on tumor-normal samples use docker optimize for low-memory node resume")
    assert result.pipeline == "nf-core/rnaseq"
    assert result.runtime == "docker"
    assert result.resume is True
    assert result.low_memory_mode is True
    assert result.sample_model == "tumor-normal"
    assert "--max_cpus" in intent_to_nf_args(result)


def test_parse_intent_wgs_podman():
    result = parse_intent("run wgs with podman")
    assert result.pipeline == "nf-core/sarek"
    assert result.runtime == "podman"
