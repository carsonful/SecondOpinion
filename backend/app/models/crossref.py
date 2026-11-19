from datetime import date
from typing import Literal

from pydantic import BaseModel

NoticeCategory = Literal["retraction", "correction", "expression_of_concern", "other"]


class IntegrityNotice(BaseModel):
    """A notice published against a paper, such as a retraction or correction."""

    category: NoticeCategory
    # Crossref's own type, e.g. "erratum" or "partial_retraction" within a broader category.
    crossref_type: str
    label: str | None
    notice_doi: str | None
    notice_url: str | None
    published_on: date | None
    # Who reported it: "publisher", "retraction-watch", or both.
    sources: list[str]


class IntegrityReport(BaseModel):
    doi: str
    # False when Crossref has no record for this DOI, so it could not be checked.
    found: bool
    # None means unchecked; False means checked and no notice found, not "verified trustworthy".
    retracted: bool | None
    has_expression_of_concern: bool | None
    has_correction: bool | None
    notices: list[IntegrityNotice]
