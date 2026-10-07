# Simple evidence grading

For the first version, use API metadata to assign an **evidence category** and
**status flags** automatically. Use the abstract to summarize the finding and
its relevance to the claim. No human review or numeric score is required.

## Metadata: what helps or hurts?

These are project rules for preliminary assessment, not formal GRADE ratings.
“Helps” means a useful evidence signal, not proof that the study was conducted well.
Tags may overlap or be missing; retain all tags and use “unknown” when ambiguous.

| Field / possible value | Effect on assessment | Simple rule |
| --- | --- | --- |
| Publication type: **Randomized Controlled Trial** | Helps assess causal intervention effects. | Label **Randomized evidence**. Does not guarantee low bias. |
| Publication type: **Clinical Trial** or **Controlled Clinical Trial** | Indicates intervention research, but does not establish randomization. | Label **Intervention evidence; randomization unknown** unless explicitly tagged. |
| Publication type: **Observational Study** | Useful for associations and harms; confounding limits causal conclusions. | Label **Observational evidence**. |
| Publication type: **Systematic Review** or **Meta-Analysis** | Brings together research, but credibility depends on methods and included studies. | Label **Research synthesis**; no automatic highest grade. |
| Publication type: **Review** | Provides background; does not establish a systematic search or appraisal. | Label **General review**. |
| Publication type: **Case Reports** | Can identify signals or unusual events; limited for estimating comparative effects. | Label **Descriptive evidence**. |
| Publication type: **Editorial**, **Comment**, or **Letter** | Often discussion rather than original research, but letters can report data. | Label **Commentary / inspect abstract**; do not infer study design from format alone. |
| Publication type: **Journal Article**, missing, or conflicting tags | Neither helps nor hurts: design is unresolved. | Label **Unclassified** rather than low quality. |
| Species/population tags: **Humans**, relevant age group | Helps establish applicability to a human claim. | Record a relevance clue; confirm the actual population in the abstract. |
| Species tags: **Animals** without human evidence | Limited direct applicability to a human-health claim. | Show separately as **Preclinical evidence**; do not treat as direct human confirmation. |
| Topic tags / keywords match the claim | Helps retrieval, but does not establish that the study answers the question. | Check population, comparison, and outcome in the abstract. |
| **Retracted Publication** or linked retraction of the article | Serious integrity problem. | Exclude affected findings from synthesis and display the notice. Distinguish the retracted paper from the notice itself. |
| Linked **Expression of Concern** | Unresolved integrity concern. | Flag and withhold from the main synthesis while unresolved. |
| Linked **Correction / Erratum** | May be minor or may change the result. | Use corrected information when resolvable; otherwise withhold affected findings. No fixed penalty. |
| **Preprint** status | Has not necessarily completed journal peer review. | Flag and summarize separately from journal-published evidence. |
| Publication date: recent or old | Describes currency, not study quality. | Display the date; no age bonus or penalty. |
| No integrity notice found | No issue identified in the retrieved record; not a guarantee. | Record **No notice found**, not “verified trustworthy.” |
| Missing abstract or full-text access | Limits what the app can assess; does not make the study worse. | Mark **Limited information**; do not invent findings. |

Publication types, topic tags, and notice links are available when supplied or
indexed; they are not complete for every record. Cohort, case-control, and
cross-sectional designs may require abstract interpretation rather than a
specific publication-type tag. See [PubMed field documentation](https://pubmed.ncbi.nlm.nih.gov/help/)
and [Europe PMC API documentation](https://europepmc.org/RestfulWebService).

## Findings: separate from the study grade

These require reading the abstract; they are not standard metadata grades.

| Extracted finding | Effect on the claim | Effect on study grade |
| --- | --- | --- |
| Supports the claim | Include as supporting evidence for the matching outcome. | None: agreement does not improve study quality. |
| Contradicts the claim | Include as contrary evidence for the matching outcome. | None: disagreement does not reduce study quality. |
| Mixed across outcomes | Explain each outcome separately. | None automatically. |
| Inconclusive or too imprecise | May not resolve the claim. Nonsignificance does not prove no effect. | Record uncertainty separately from design. |
| Does not address the claim | Exclude from this claim’s synthesis. | A relevance issue, not a quality penalty. |
| Result missing or ambiguous | Return **Cannot determine**. | Keep the design category; flag insufficient information. |

## Output and overall summary

Each paper gets **evidence category + status flags + relevance + finding + short
summary + citation**. Metadata grading uses code; AI interprets abstracts and
writes summaries, retaining supporting passages.

The overall summary groups comparable outcomes, explains agreement and
contradictions, and distinguishes designs. Do not count duplicate reports or
reviews and their included studies as independent confirmation. Avoid majority
votes, invented weights, and confidence percentages. If findings cannot support
a conclusion, return **Insufficient evidence** automatically.

This document describes the intended assessment method.
