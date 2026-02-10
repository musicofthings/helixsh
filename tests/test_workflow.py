from helixsh.workflow import container_violations, parse_process_nodes


def test_parse_process_nodes_and_container_violations():
    text = """
process ALIGN_READS {
  cpus 8
  memory '32 GB'
  time '12h'
  container 'biocontainers/star:latest'
}
process QUANTIFY {
  cpus 2
}
"""
    nodes = parse_process_nodes(text)
    assert len(nodes) == 2
    assert nodes[0].name == "ALIGN_READS"
    issues = container_violations(nodes)
    assert issues == ["Process QUANTIFY missing container"]
