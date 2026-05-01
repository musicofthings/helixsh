from helixsh.context import parse_nextflow_config_defaults, summarize_samplesheet


def test_summarize_samplesheet(tmp_path):
    f = tmp_path / "samplesheet.csv"
    f.write_text("sample,condition\nS1,tumor\nS2,normal\n", encoding="utf-8")
    s = summarize_samplesheet(str(f))
    assert s.row_count == 2
    assert s.has_tumor_normal is True
    assert s.sample_ids == ("S1", "S2")


def test_parse_nextflow_config_defaults(tmp_path):
    f = tmp_path / "nextflow.config"
    f.write_text('cpus = 8\nmemory = "32 GB"\ntime = "12h"\n', encoding="utf-8")
    d = parse_nextflow_config_defaults(str(f))
    assert d.cpus == "8"
    assert d.memory == "32 GB"
    assert d.time == "12h"
