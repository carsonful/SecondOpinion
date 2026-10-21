"""Retrieve available PMC JATS article text without substituting an abstract."""

import re
import xml.etree.ElementTree as ET

from app.models.pubmed import PubMedArticle
from app.services.pubmed import PubMedClient, PubMedResponseError

# One bounded model request; never truncate a paper and call it a full review.
MAX_STUDY_CHARACTERS = 60_000


class FullTextUnavailable(Exception):
    pass


def parse_full_text(content: bytes, article: PubMedArticle) -> str:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        raise PubMedResponseError("PMC returned invalid article XML") from None
    for node in root.iter():
        node.tag = node.tag.rsplit("}", 1)[-1]
    paper = root if root.tag == "article" else root.find("article")
    if paper is None:
        raise FullTextUnavailable("Full article text is not available through PMC for this study.")
    ids = {n.get("pub-id-type"): "".join(n.itertext()).strip()
           for n in paper.findall("front/article-meta/article-id")}
    pmc = ids.get("pmc", ids.get("pmcid", ""))
    if pmc.removeprefix("PMC") != article.pmc_id.removeprefix("PMC") or (
        ids.get("pmid") and ids["pmid"] != article.pmid
    ):
        raise PubMedResponseError("PMC article identity does not match the selected study")
    body = paper.find("body")
    if body is None or not "".join(body.itertext()).strip():
        raise FullTextUnavailable("PMC returned no article body; no full-study assessment was made.")

    def render(node):
        if node.tag in {"ref-list", "supplementary-material", "sub-article"}:
            return ""
        text = node.text or ""
        for child in node:
            text += render(child) + (child.tail or "")
        if node.tag in {"p", "title", "sec", "table-wrap", "caption", "tr", "td", "th", "label", "list-item"}:
            return "\n" + text + "\n"
        return text

    sections = [render(n) for n in paper.findall("front/article-meta/abstract")]
    sections.append(render(body))
    text = "\n".join(line.strip() for line in "\n".join(sections).splitlines() if line.strip())
    if len(text) > MAX_STUDY_CHARACTERS:
        raise FullTextUnavailable("This study exceeds the prototype's 60,000-character assessment budget. No model call was made.")
    return text


async def retrieve_full_text(client: PubMedClient, article: PubMedArticle) -> str:
    if not article.pmc_id or not re.fullmatch(r"PMC\d+", article.pmc_id):
        raise FullTextUnavailable("This study has no linked PMC record.")
    response = await client._get("efetch.fcgi", {
        "db": "pmc", "id": article.pmc_id.removeprefix("PMC"), "retmode": "xml",
    })
    return parse_full_text(response.content, article)
