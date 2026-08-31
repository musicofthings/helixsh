# Demo data

Synthetic inputs for exercising the desktop app and CLI without real
sequencing data. The FASTQ paths are placeholders: they are enough to plan
and validate a run, not to execute one.

| File | Use |
|---|---|
| `rnaseq-samplesheet.csv` | four-sample bulk RNA-seq, control vs treated |
| `sarek-samplesheet.csv` | two tumour/normal pairs, exercises pairing detection |
| `viralrecon-samplesheet.csv` | two viral amplicon samples |
| `trace.txt` | a Nextflow trace with fully qualified nf-core process names |

`scripts/demo.sh` creates the scratch directories these need (`demo/work/`,
which is git-ignored) and launches the desktop app.
