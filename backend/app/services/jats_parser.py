"""Turn PMC full text (Europe PMC JATS XML or NCBI BioC JSON) into labeled sections."""

import json
import re
import xml.etree.ElementTree as ET
from typing import Any

from app.models.full_text import Section, SectionType


class FullTextParseError(ValueError):
    """The source answered, but not with article text we can use."""


# Checked in order, so "Results and discussion" is results and
# "Strengths and limitations" is limitations.
_HEADING_RULES: list[tuple[SectionType, re.Pattern[str]]] = [
    ("limitations", re.compile(r"\blimitations?\b|\bstrengths? and weakness")),
    ("abstract", re.compile(r"^(?:abstract|summary)$")),
    ("methods", re.compile(
        r"\bmethods?\b|\bmethodology\b|\bmaterials?\b|\bpatients and\b|\bparticipants\b|\bsubjects\b"
        r"|\bstudy design\b|\bstudy population\b|\bexperimental\b|\bstatistical analys[ie]s\b"
        r"|\bdata (?:collection|analysis|sources)\b|\binterventions?\b|\boutcome measures\b"
        r"|\beligibility\b|\bsearch strategy\b|\brandomi[sz]ation\b"
    )),
    ("results", re.compile(r"\bresults?\b|\bfindings\b")),
    ("discussion", re.compile(r"\bdiscussion\b|\bconclusions?\b|\binterpretation\b|\bimplications\b")),
    ("introduction", re.compile(r"\bintroduction\b|\bbackground\b|\brationale\b|\bobjectives?\b|\baims?\b")),
]

# JATS sec-type values (https://jats.nlm.nih.gov/archiving/tag-library/1.3/attribute/sec-type.html).
_SEC_TYPES: dict[str, SectionType] = {
    "intro": "introduction", "introduction": "introduction", "background": "introduction",
    "materials": "methods", "methods": "methods", "materials|methods": "methods",
    "subjects": "methods", "cases": "methods",
    "results": "results", "discussion": "discussion", "conclusions": "discussion",
    "results|discussion": "results", "limitations": "limitations",
}

# BioC section_type values used by the NCBI PMC BioC service.
_BIOC_TYPES: dict[str, SectionType] = {
    "ABSTRACT": "abstract", "INTRO": "introduction", "METHODS": "methods", "CASE": "methods",
    "RESULTS": "results", "DISCUSS": "discussion", "CONCL": "discussion",
}
_BIOC_SKIPPED = {
    "TITLE", "REF", "SUPPL", "ACK_FUND", "AUTH_CONT", "COMP_INT", "ABBR", "KEYWORD", "REVIEW_INFO",
}

# JATS elements that are never study content.
_SKIPPED_TAGS = {"ref-list", "supplementary-material", "sub-article", "fn-group", "ack", "graphic", "media"}
_BLOCK_TAGS = {"p", "title", "caption", "tr", "label", "list-item", "disp-quote", "table-wrap", "fig", "def-item"}
_NUMBERING = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?|[IVX]+\.|[A-Z]\.)\s+")


def classify_heading(heading: str | None) -> SectionType:
    """Map a section heading such as "Materials and Methods" to a section type."""
    if not heading:
        return "other"
    text = _NUMBERING.sub("", heading).strip().casefold().rstrip(":. ")
    for section_type, pattern in _HEADING_RULES:
        if pattern.search(text):
            return section_type
    return "other"


def _child_type(heading: str | None, parent: SectionType) -> SectionType:
    # A subsection only leaves its parent when its own heading says so, so
    # "Participants" stays in methods and "Zinc lozenges" stays in results.
    own = classify_heading(heading)
    return parent if own in ("other", "abstract") else own


def _local(tag: Any) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _render(node: ET.Element) -> str:
    """Element text with inline markup kept and block elements on their own lines."""
    if _local(node.tag) in _SKIPPED_TAGS:
        return ""
    text = node.text or ""
    for child in node:
        text += _render(child) + (child.tail or "")
    if _local(node.tag) in ("td", "th"):
        return text.strip() + " | "
    if _local(node.tag) in _BLOCK_TAGS:
        return "\n" + text + "\n"
    return text


def _clean(text: str) -> str:
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def parse_jats(content: bytes) -> tuple[list[Section], str | None]:
    """Parse a JATS article (Europe PMC fullTextXML). Returns (sections, license)."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        raise FullTextParseError("Full text was not valid XML") from None
    for node in root.iter():
        node.tag = _local(node.tag)
    article = root if root.tag == "article" else root.find(".//article")
    if article is None:
        raise FullTextParseError("Full text has no article element")

    sections: list[Section] = []
    abstract = next(
        (a for a in article.iterfind("front/article-meta/abstract") if a.get("abstract-type") is None),
        article.find("front/article-meta/abstract"),
    )
    if abstract is not None:
        heading = abstract.find("title")
        if heading is not None:
            abstract.remove(heading)
        text = _clean(_render(abstract))
        if text:
            sections.append(Section(type="abstract", heading="Abstract", text=text))

    body = article.find("body")
    if body is not None:
        loose: list[str] = []
        for child in body:
            if child.tag == "sec":
                _collect_sec(child, None, sections)
            else:
                loose.append(_render(child))
        text = _clean("".join(loose))
        if text:
            # Body text outside any <sec>, as in short reports and letters.
            sections.append(Section(type="other", heading=None, text=text))

    # Drop the empty pieces that splitting subsections out can leave behind.
    return [s for s in sections if s.text], _jats_license(article)


def _collect_sec(sec: ET.Element, parent: SectionType | None, out: list[Section]) -> None:
    title_node = sec.find("title")
    heading = _clean(_render(title_node)) if title_node is not None else None
    sec_type = _SEC_TYPES.get((sec.get("sec-type") or "").casefold())
    if parent is None:
        section_type = sec_type or classify_heading(heading)
    else:
        section_type = sec_type or _child_type(heading, parent)

    own = Section(type=section_type, heading=heading or None, text="")
    out.append(own)
    parts: list[str] = []
    for child in sec:
        if child is title_node:
            continue
        if child.tag == "sec":
            child_heading = child.find("title")
            child_type = _SEC_TYPES.get((child.get("sec-type") or "").casefold()) or _child_type(
                _clean(_render(child_heading)) if child_heading is not None else None, section_type
            )
            if child_type != section_type:
                # Split out, e.g. "Strengths and limitations" inside the Discussion.
                own.text = _clean("".join(parts))
                _collect_sec(child, section_type, out)
                parts = []
                own = Section(type=section_type, heading=heading or None, text="")
                out.append(own)
                continue
        parts.append(_render(child))
    own.text = _clean("".join(parts))


def _jats_license(article: ET.Element) -> str | None:
    license_node = article.find("front/article-meta/permissions/license")
    if license_node is None:
        return None
    candidates = [value for key, value in license_node.attrib.items() if _local(key) == "href"]
    candidates += ["".join(n.itertext()) for n in license_node.iter() if n.tag == "license_ref"]
    candidates.append("".join(license_node.itertext()))
    for candidate in candidates:
        found = normalize_license(candidate)
        if found:
            return found
    return None


_CC_URL = re.compile(r"creativecommons\.org/licenses/([a-z-]+)/", re.IGNORECASE)
_CC_TEXT = re.compile(r"\bCC[\s-]?(BY(?:[\s-](?:NC|ND|SA))*|0)\b", re.IGNORECASE)


def normalize_license(value: str | None) -> str | None:
    """Return an Unpaywall-style license id ("cc-by", "cc-by-nc-nd", "cc0") or None."""
    if not value:
        return None
    if "creativecommons.org/publicdomain/zero" in value.casefold():
        return "cc0"
    match = _CC_URL.search(value)
    if match:
        return "cc-" + match.group(1).casefold()
    match = _CC_TEXT.search(value)
    if match:
        return "cc-" + re.sub(r"[\s-]+", "-", match.group(1)).casefold()
    if "creative commons attribution" in value.casefold():
        return "cc-by"
    return None


def parse_bioc(content: bytes) -> tuple[list[Section], str | None]:
    """Parse NCBI BioC JSON for one PMC article. Returns (sections, license)."""
    try:
        payload = json.loads(content)
        collection = payload[0] if isinstance(payload, list) else payload
        passages = collection["documents"][0]["passages"]
        if not isinstance(passages, list):
            raise TypeError
    except (ValueError, KeyError, IndexError, TypeError):
        raise FullTextParseError("BioC response had no article passages") from None

    license_id = None
    abstract: list[str] = []
    sections: list[Section] = []
    current: Section | None = None
    current_bioc: str | None = None
    for passage in passages:
        if not isinstance(passage, dict):
            continue
        infons = passage.get("infons") or {}
        bioc_type = str(infons.get("section_type", "")).upper()
        kind = str(infons.get("type", ""))
        text = _clean(str(passage.get("text") or ""))
        license_id = license_id or normalize_license(infons.get("license"))
        if not text or bioc_type in _BIOC_SKIPPED:
            continue
        if bioc_type == "ABSTRACT":
            abstract.append(text)
            continue

        base = _BIOC_TYPES.get(bioc_type)
        if kind.startswith("title"):
            if kind == "title_1" or current is None:
                section_type = base or classify_heading(text)
                if classify_heading(text) == "limitations":
                    section_type = "limitations"
            else:
                section_type = _child_type(text, base or current.type)
            if current is None or kind == "title_1" or section_type != current.type:
                current = Section(type=section_type, heading=text, text="")
                current_bioc = bioc_type
                sections.append(current)
            else:
                current.text += f"\n{text}"
            continue

        # Table and figure passages belong to wherever they appear.
        if current is None or (bioc_type != current_bioc and bioc_type not in ("TABLE", "FIG")):
            current = Section(type=base or "other", heading=None, text="")
            current_bioc = bioc_type
            sections.append(current)
        current.text += f"\n{text}"

    for section in sections:
        section.text = section.text.strip()
    result = [s for s in sections if s.text]
    if abstract:
        result.insert(0, Section(type="abstract", heading="Abstract", text="\n".join(abstract)))
    return result, license_id
