# Full-text fixtures

These responses were written by hand to match each API's documented format, because
the sandbox that built this stage could not reach NCBI, Europe PMC, Unpaywall or Azure.
The IDs (PMID 99000001, PMC9900001, DOI 10.5555/so.0002, ...) are fictional.

To replace one with a recorded response, save the real body under the same name and
trim it; the parser tests only rely on structure, not on the article's wording.

| File | Source |
| --- | --- |
| `idconv.json` | `https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids=...&format=json` |
| `europepmc_fulltext.xml` | `https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML` (JATS) |
| `bioc.json` | `https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/{PMCID}/unicode` |
| `unpaywall.json` | `https://api.unpaywall.org/v2/{doi}?email=...` |
| `docintel_layout.json` | Document Intelligence `prebuilt-layout` analyze result (API 2024-11-30) |
