"""Shape one full-text record into the study content sent to Foundry.

Only the sections grading needs are sent. When a study exceeds its token budget,
lower-priority sections are cut first: Limitations, then Methods, then Results,
and the Abstract only as a last resort.
"""

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.models.full_text import FullTextRecord, SectionType

# Reading order in the prompt.
SENT_SECTIONS: tuple[SectionType, ...] = ("abstract", "methods", "results", "limitations")
# Cut first to last.
TRUNCATION_ORDER: tuple[SectionType, ...] = ("limitations", "methods", "results", "abstract")
# A rough, tokenizer-free estimate; English prose averages about 4 characters a token.
CHARACTERS_PER_TOKEN = 4
TRUNCATION_MARK = " [truncated]"
# A section cut below this is more noise than signal, so drop it instead.
MIN_SECTION_CHARACTERS = 200

TIER_LABELS = {"pmc_fulltext": "PMC", "oa_pdf": "open-access PDF"}


@dataclass(frozen=True)
class StudyPayload:
    content: dict[str, Any]
    # Exactly the study text the model sees, for checking its quotations.
    source_text: str
    truncated: list[SectionType]


def build_study_payload(record: FullTextRecord, token_budget: int) -> StudyPayload:
    texts: dict[SectionType, str] = {}
    for section_type in SENT_SECTIONS:
        parts = [
            (f"{s.heading}\n{s.text}" if s.heading and s.type != "abstract" else s.text)
            for s in record.sections if s.type == section_type
        ]
        if parts:
            texts[section_type] = "\n\n".join(parts)

    metadata = {
        "pmid": record.pmid, "title": record.title, "year": record.year, "journal": record.journal,
        "publication_types": record.publication_types, "source_tier": record.source_tier,
    }
    budget = token_budget * CHARACTERS_PER_TOKEN - len(json.dumps(metadata))
    truncated: list[SectionType] = []
    for section_type in TRUNCATION_ORDER:
        excess = sum(len(text) for text in texts.values()) - budget
        if excess <= 0:
            break
        if section_type not in texts:
            continue
        keep = len(texts[section_type]) - excess - len(TRUNCATION_MARK)
        truncated.append(section_type)
        if keep < MIN_SECTION_CHARACTERS:
            del texts[section_type]
        else:
            texts[section_type] = texts[section_type][:keep].rstrip() + TRUNCATION_MARK

    sections = {section_type: texts[section_type] for section_type in SENT_SECTIONS if section_type in texts}
    content = metadata | {"sections": sections}
    if truncated:
        content["truncated_sections"] = truncated
    return StudyPayload(content=content, source_text="\n\n".join(sections.values()), truncated=truncated)


def coverage_summary(records: Sequence[FullTextRecord]) -> str:
    """For example: "3 of 5 studies were read in full text (2 PMC, 1 open-access PDF); 2 were abstract only."""
    if not records:
        return "No studies were retrieved."
    tiers = Counter(record.source_tier for record in records)
    full = tiers["pmc_fulltext"] + tiers["oa_pdf"]
    no_text = sum(1 for r in records if r.source_tier == "abstract_only" and not r.sections)
    abstract_only = tiers["abstract_only"] - no_text

    summary = f"{full} of {len(records)} {'study was' if len(records) == 1 else 'studies were'} read in full text"
    sources = [f"{tiers[tier]} {label}" for tier, label in TIER_LABELS.items() if tiers[tier]]
    if sources:
        summary += f" ({', '.join(sources)})"
    summary += f"; {abstract_only} {'was' if abstract_only == 1 else 'were'} abstract only"
    if no_text:
        summary += f"; {no_text} had no study text"
    return summary + "."
