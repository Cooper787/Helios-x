"""Catalyst calendar from ClinicalTrials.gov API v2.

Free, no API key, no rate-limit registration. This is the forward-looking
catalyst spine.

Known limitation, stated here because it constrains the whole strategy:
primaryCompletionDate is when the trial expects to finish collecting primary
outcome data, NOT when results are announced. The gap between the two is
typically weeks to months and is not published. So this yields an approximate
catalyst window, not a dated event.

PDUFA target action dates -- the genuinely precise biotech catalyst -- have no
free API at all. Drugs@FDA lists approvals only after the fact. Every free
PDUFA calendar is a scraped commercial site. That gap is unsolved and is
recorded in the project design doc.
"""

from __future__ import annotations

import calendar
import logging
import urllib.parse
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

from ..models import Catalyst, EventType, Provenance, SponsorClass, TrialDesign
from .base import HttpJsonClient, SourceError, dig

logger = logging.getLogger(__name__)

API_ROOT = "https://clinicaltrials.gov/api/v2/studies"

_FIELDS = ",".join(
    [
        "protocolSection.identificationModule.nctId",
        "protocolSection.identificationModule.briefTitle",
        "protocolSection.statusModule.overallStatus",
        "protocolSection.statusModule.primaryCompletionDateStruct",
        "protocolSection.sponsorCollaboratorsModule.leadSponsor",
        "protocolSection.armsInterventionsModule.interventions",
        "protocolSection.conditionsModule.conditions",
        "protocolSection.designModule.phases",
        "protocolSection.designModule.enrollmentInfo",
        "protocolSection.designModule.designInfo",
    ]
)

_PHASE_TO_EVENT = {
    "PHASE3": EventType.PHASE_3_COMPLETION,
    "PHASE2": EventType.PHASE_2_COMPLETION,
}


def parse_ct_date(value: Optional[str]) -> Optional[date]:
    """Parse a ClinicalTrials.gov date.

    The API emits either YYYY-MM-DD or YYYY-MM. A month-only value is treated
    as the end of that month: for a catalyst we care about, assuming the later
    date is the conservative choice, because it keeps us out of the position
    for longer rather than entering early on a date that may already have
    passed.
    """
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            parsed = datetime.strptime(value, fmt).date()
        except ValueError:
            continue
        if fmt == "%Y-%m":
            last_day = calendar.monthrange(parsed.year, parsed.month)[1]
            return date(parsed.year, parsed.month, last_day)
        return parsed
    return None


class ClinicalTrialsSource:
    """Fetches trials whose primary completion falls in a forward window."""

    name = "clinicaltrials.gov"

    def __init__(self, client: HttpJsonClient, page_size: int = 100, max_pages: int = 20) -> None:
        self.client = client
        self.page_size = page_size
        self.max_pages = max_pages

    def _build_url(self, phase: str, page_token: Optional[str]) -> str:
        params = {
            "query.term": f"AREA[Phase]{phase}",
            "filter.overallStatus": "RECRUITING|ACTIVE_NOT_RECRUITING|ENROLLING_BY_INVITATION",
            "pageSize": str(self.page_size),
            "fields": _FIELDS,
            "countTotal": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        return f"{API_ROOT}?{urllib.parse.urlencode(params, safe='[]|')}"

    def fetch(self, phases: Iterable[str]) -> List[Catalyst]:
        catalysts: List[Catalyst] = []
        for phase in phases:
            catalysts.extend(self._fetch_phase(phase))
        return catalysts

    def _fetch_phase(self, phase: str) -> List[Catalyst]:
        out: List[Catalyst] = []
        token: Optional[str] = None

        for page in range(self.max_pages):
            url = self._build_url(phase, token)
            payload = self.client.get_json(url)

            studies = payload.get("studies") if isinstance(payload, dict) else None
            if not isinstance(studies, list):
                raise SourceError(
                    f"Unexpected response shape from {self.name}: "
                    f"expected 'studies' list, got {type(studies).__name__}"
                )

            for study in studies:
                catalyst = self._parse_study(study, phase)
                if catalyst is not None:
                    out.append(catalyst)

            token = payload.get("nextPageToken")
            if not token:
                break
        else:
            # Loop exhausted without exhausting the result set. Say so rather
            # than silently truncating -- a quiet cap reads as full coverage.
            logger.warning(
                "%s: hit max_pages=%d for %s; results truncated",
                self.name,
                self.max_pages,
                phase,
            )

        return out

    def _parse_study(self, study: Dict[str, Any], phase: str) -> Optional[Catalyst]:
        proto = study.get("protocolSection", {}) if isinstance(study, dict) else {}

        nct_id = dig(proto, "identificationModule", "nctId")
        if not nct_id:
            return None

        pcd = dig(proto, "statusModule", "primaryCompletionDateStruct", default={})
        event_date = parse_ct_date(pcd.get("date") if isinstance(pcd, dict) else None)
        if event_date is None:
            return None

        # "ACTUAL" means the date has already happened; only "ESTIMATED"
        # dates are forward-looking catalysts.
        date_type = (pcd.get("type") or "").upper() if isinstance(pcd, dict) else ""
        if date_type == "ACTUAL":
            return None

        lead = dig(proto, "sponsorCollaboratorsModule", "leadSponsor", default={}) or {}
        sponsor = lead.get("name") or ""
        if not sponsor:
            return None

        try:
            sponsor_class = SponsorClass((lead.get("class") or "UNKNOWN").upper())
        except ValueError:
            sponsor_class = SponsorClass.UNKNOWN

        interventions = dig(proto, "armsInterventionsModule", "interventions", default=[]) or []
        names, types = [], []
        for iv in interventions:
            if isinstance(iv, dict):
                if iv.get("name"):
                    names.append(str(iv["name"]))
                if iv.get("type"):
                    types.append(str(iv["type"]).upper())

        phases = dig(proto, "designModule", "phases", default=[]) or []
        phase_key = phase
        for p in phases:
            if isinstance(p, str) and p.upper() in _PHASE_TO_EVENT:
                phase_key = p.upper()
                break

        enrol = dig(proto, "designModule", "enrollmentInfo", default={}) or {}
        design_info = dig(proto, "designModule", "designInfo", default={}) or {}
        enrollment = enrol.get("count")
        design = TrialDesign(
            enrollment=int(enrollment) if isinstance(enrollment, (int, float)) else None,
            enrollment_is_estimated=(enrol.get("type") or "").upper() != "ACTUAL",
            allocation=design_info.get("allocation"),
            masking=dig(design_info, "maskingInfo", "masking"),
            primary_purpose=design_info.get("primaryPurpose"),
        )

        return Catalyst(
            event_type=_PHASE_TO_EVENT.get(phase_key, EventType.PHASE_3_COMPLETION),
            event_date=event_date,
            sponsor=sponsor,
            title=dig(proto, "identificationModule", "briefTitle", default="") or "",
            external_id=str(nct_id),
            intervention_names=names,
            intervention_types=types,
            conditions=list(dig(proto, "conditionsModule", "conditions", default=[]) or []),
            date_is_estimated=True,
            sponsor_class=sponsor_class,
            design=design,
            phase_label=phase_key,
            provenance=Provenance(
                source=self.name,
                url=f"https://clinicaltrials.gov/study/{nct_id}",
            ),
        )
