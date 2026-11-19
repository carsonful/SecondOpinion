# Study type key

| Mark | Study type |
| --- | --- |
| A · purple | Systematic review or meta-analysis |
| B · blue | Randomized or other intervention study |
| C · teal | Observational study: cohort, case-control, or cross-sectional |
| D · amber | Case report or case series |
| — · gray | Review, commentary, or unclear design |

Letters and colors are labels only, not grades. A study's design does not
establish that it was well conducted. Labels are based on PubMed publication
types, with an abstract description used to identify a subtype when indexed as
observational. A label may be unknown when the available information is unclear.
See the [NCBI epidemiology guide](https://www.ncbi.nlm.nih.gov/books/NBK621603/)
and this overview of [clinical study designs](https://pmc.ncbi.nlm.nih.gov/articles/PMC11009715/).

## Population labels

Population is separate from study design. An animal experiment can be a randomized
trial; the trial label does not mean its findings were observed in people.

| Label | Indexed MeSH descriptors |
| --- | --- |
| Laboratory / cell study (`in_vitro`) | `In Vitro Techniques`, `Cells, Cultured`, or `Cell Culture Techniques` |
| Human-indexed (`human`) | `Humans`, with no explicit lab descriptor above |
| Animal study (`animal`) | `Animals`, without `Humans` or an explicit lab descriptor |
| Population not indexed (`unknown`) | None of these descriptors |

Descriptors are compared without case or surrounding/repeated whitespace.
Lab descriptors take precedence even for human-derived cells. Otherwise, mixed
`Humans`/`Animals` records are human-indexed; that label does not establish that
all findings concern people. Read the abstract to identify the actual population.
Species names alone are not used to guess a label. New/unindexed records can be
unknown even when their abstract describes participants.

These labels describe the indexed record, not evidence quality, eligibility for
treatment, or certainty that a finding applies to humans. Overview prompts receive
the label alongside the abstract and must preserve animal/lab qualifications.
Prompt instructions do not independently validate an AI interpretation.
