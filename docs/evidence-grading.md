# Simple evidence grading

For the first version, use API metadata to assign an **evidence category** and
**status flags** automatically. Use the abstract to summarize the finding and
its relevance to the claim. Assign the provisional base weights below when the
design is known; otherwise leave the weight unknown. No human review is required
for this preliminary categorization.

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

## Provisional base weights (v0.1)

These editable project defaults describe the starting contribution of a design
to assessment of a **human intervention-effect claim**. They are heuristics, not
validated quality scores, formal GRADE ratings, or probabilities that a claim is
true. A weight of 8 does not mean 80% confidence or twice the reliability of 4.
Different questions, such as harms or diagnosis, may need different defaults.

| Evidence category / resolved design | Base weight (0–10) | Starting rationale |
| --- | ---: | --- |
| Randomized evidence | 8 | Strong starting design for comparing intervention effects; bias still needs assessment. |
| Intervention evidence; randomization unknown | 5 | Direct intervention research, with randomization unconfirmed. |
| Observational evidence: cohort | 4 | Can establish timing, but confounding remains possible. |
| Observational evidence: case-control | 3 | Useful comparison design, with selection and recall limitations to assess. |
| Observational evidence: cross-sectional | 2 | Captures associations without reliably establishing timing. |
| Observational evidence: subtype unknown | 3 | Provisional middle value until the design is resolved. |
| Descriptive evidence: case report or case series | 1 | Useful signals, with little basis for comparative effects. |
| General review | 0 | Background context; no independent contribution to the weighted comparison. |
| Commentary / inspect abstract | 0 | Context by default; use the actual design weight if original research is identified. |
| Unclassified | Unknown (`null`) | Missing or conflicting design information is not a zero-quality score. |
| Research synthesis | Conditional | Use the rule below; the review label alone earns no bonus. |

For a systematic review or meta-analysis, use the base weight of its included
design only when that design is established (for example, 8 for a synthesis of
randomized trials). If included designs are mixed, weight separately reported
design groups; otherwise leave the weight `null`. This is a design-based starting
value, not an appraisal of the review's methods. Represent an overlapping body of
research with either its synthesis or its underlying studies in a comparison,
never both. Unresolved overlap prevents an aggregate weighted comparison.

Use one resolved design weight per paper or separately reported design group;
do not add weights for overlapping publication tags. A specific design takes
precedence over a generic format tag such as Journal Article or Letter. Conflicting
design tags remain `null` until resolved from the abstract. Retain the original
tags and the passage used to resolve the design.

### Eligibility and status rules

Keep the base weight separate from eligibility. Exclusion or withholding does
not change the recorded design weight.

| Condition | Treatment in the main weighted comparison |
| --- | --- |
| Relevant human evidence with a usable finding and no withholding condition | Eligible at its base weight. |
| Retracted findings | Exclude; effective contribution is 0. |
| Unresolved expression of concern | Withhold; effective contribution is 0 while unresolved. |
| Correction / erratum | Use the corrected finding; withhold affected findings if unresolved. No fixed deduction. |
| Preprint | Keep in a separate provisional group using the same design defaults. |
| Animal-only / preclinical evidence | Keep in a separate group; contribution to direct human evidence is 0. |
| Does not address the claim | Exclude from this claim's comparison; contribution is 0. |
| Relevance uncertain, result unavailable, or design weight unknown | Withhold from numeric comparison and display the information gap. |
| Publication date, keyword match, or no notice found | No numerical bonus or penalty. |

For eligible evidence, `effective_weight = base_weight`. For excluded or withheld
evidence, `effective_weight = 0`, with the reason retained. Unknown base weights
remain `null` in the record. Zero contribution means the paper does not contribute
to this comparison; it does not establish that its research is poor.

Keep supporting, contrary, mixed, and inconclusive findings separate. Apply the
same design weight regardless of agreement with the claim. Do not convert these
weights into a signed vote, confidence percentage, or automatic verdict. Any
future aggregation needs explicit rules for comparability, overlap, bias, and
precision; this version defines starting weights only.

### Adjusting the defaults later

Treat this table as the source of truth for `base_weights_v0.1` until implemented
in configuration. Store weights centrally when implemented, rather than embedding
them in prompts. Record the weight version, resolved design, base weight,
eligibility reason, and effective weight with each assessment. Changes should
increment the version and document the rationale so older results stay
interpretable. These values are documentation only; they do not change runtime
grading yet.

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

Each paper gets **evidence category + base weight + weight version + eligibility
reason + effective weight + status flags + relevance + finding + short summary +
citation**. Metadata grading uses code; AI interprets abstracts and
writes summaries, retaining supporting passages.

The overall summary groups comparable outcomes, explains agreement and
contradictions, and distinguishes designs. Do not count duplicate reports or
reviews and their included studies as independent confirmation. Avoid majority
votes, ad hoc weights outside the versioned defaults, and confidence percentages.
The base weights supplement the explanation; they do not determine the verdict.
If findings cannot support
a conclusion, return **Insufficient evidence** automatically.

This document describes the intended assessment method.
