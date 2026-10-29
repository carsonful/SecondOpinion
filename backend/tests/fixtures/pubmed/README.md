# Recorded PubMed population fixture

`efetch_animal_trial.xml` records the NCBI EFetch response for PMID **42907999**:
an exploratory randomized study of wound healing in female dogs. Retrieved
2026-10-29 from:

https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=42907999&retmode=xml

The XML was indented for review; descriptors, publication types, and source text
were retained. Tests run from this recording without querying NCBI. It has an
`Animals` descriptor, no `Humans` descriptor, and a `Randomized Controlled Trial`
publication type. This catches the regression where a trial label is mistaken
for evidence of human participants.

Mixed and unindexed cases are derived in parameterized tests from the existing
recorded zinc fixture. Their expected labels test explicit descriptor rules;
they do not claim to be separately recorded PubMed articles.
