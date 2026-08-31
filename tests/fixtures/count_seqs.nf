#!/usr/bin/env nextflow

// Minimal but representative workflow: one process per input FASTA, a
// published output, and a value derived from the file contents. Used by the
// integration suite to prove Helixsh actually executes Nextflow.

params.reads  = null
params.outdir = 'results'
params.fail   = false

process COUNT_SEQS {
    publishDir params.outdir, mode: 'copy'

    input:
    path fasta

    output:
    path "${fasta.simpleName}.count"

    script:
    if (params.fail)
        """
        echo "deliberate failure for exit-code propagation" >&2
        exit 3
        """
    else
        """
        grep -c '^>' ${fasta} > ${fasta.simpleName}.count
        """
}

workflow {
    Channel.fromPath("${params.reads}/*.fasta") | COUNT_SEQS | view
}
