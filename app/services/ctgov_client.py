"""
Enhanced ClinicalTrials.gov API Client for Sponsor-Side Site Intelligence.
Searches studies by condition/location, aggregates by site, builds inferred profiles.
"""
import httpx
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CTGovStudy:
    """Parsed study from CT.gov API"""
    nct_id: str
    title: str
    phase: str
    status: str
    conditions: List[str]
    sponsors: List[str]
    locations: List[Dict]
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    enrollment: Optional[int] = None


@dataclass
class InferredSiteProfile:
    """Site profile built entirely from CT.gov data."""
    # Basic info
    facility_name: str
    city: str
    state: str
    country: str

    # Aggregated metrics
    investigators: List[Dict] = field(default_factory=list)
    total_trials: int = 0
    completed_trials: int = 0
    active_trials: int = 0
    terminated_trials: int = 0

    # Experience breakdown
    phase_experience: Dict[str, int] = field(default_factory=dict)
    therapeutic_experience: Dict[str, int] = field(default_factory=dict)
    sponsors_worked_with: List[str] = field(default_factory=list)

    # Calculated
    completion_rate: float = 0.0

    # Trial details
    trial_history: List[Dict] = field(default_factory=list)
    competing_trials: List[Dict] = field(default_factory=list)

    # Metadata
    data_source: str = "ClinicalTrials.gov"
    data_confidence: str = "VERIFIED"
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "facility_name": self.facility_name,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "investigators": self.investigators,
            "total_trials": self.total_trials,
            "completed_trials": self.completed_trials,
            "active_trials": self.active_trials,
            "terminated_trials": self.terminated_trials,
            "phase_experience": self.phase_experience,
            "therapeutic_experience": self.therapeutic_experience,
            "sponsors_worked_with": self.sponsors_worked_with,
            "completion_rate": self.completion_rate,
            "trial_history": self.trial_history,
            "competing_trials": self.competing_trials,
            "data_source": self.data_source,
            "data_confidence": self.data_confidence,
            "last_updated": self.last_updated
        }


class CTGovClient:
    """
    Client for ClinicalTrials.gov API v2.
    Searches studies and aggregates into site profiles.
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

    COMPLETED_STATUSES = ["COMPLETED"]
    ACTIVE_STATUSES = ["RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING"]
    TERMINATED_STATUSES = ["TERMINATED", "WITHDRAWN", "SUSPENDED"]

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def search_studies(
        self,
        condition: Optional[str] = None,
        location: Optional[str] = None,
        sponsor: Optional[str] = None,
        phase: Optional[List[str]] = None,
        status: Optional[List[str]] = None,
        page_size: int = 100,
        max_pages: int = 5
    ) -> List[CTGovStudy]:
        """
        Search CT.gov for studies matching criteria.

        Args:
            condition: Disease/condition (e.g., "NASH", "NAFLD")
            location: Location filter (state, city, or institution)
            sponsor: Sponsor name
            phase: List of phases ["PHASE1", "PHASE2", "PHASE3", "PHASE4"]
            status: List of statuses ["COMPLETED", "RECRUITING", etc.]
            page_size: Results per page (max 100)
            max_pages: Maximum pages to fetch
        """
        params = {
            "pageSize": min(page_size, 100),
            "format": "json"
        }

        if condition:
            params["query.cond"] = condition
        if location:
            params["query.locn"] = location
        if sponsor:
            params["query.spons"] = sponsor
        if phase:
            params["filter.phase"] = ",".join(phase)
        if status:
            params["filter.overallStatus"] = ",".join(status)

        all_studies = []
        next_page_token = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for page in range(max_pages):
                try:
                    if next_page_token:
                        params["pageToken"] = next_page_token

                    logger.info(f"CT.gov query page {page + 1}: condition={condition}, location={location}")
                    response = await client.get(self.BASE_URL, params=params)
                    response.raise_for_status()
                    data = response.json()

                    studies = data.get("studies", [])
                    logger.info(f"Found {len(studies)} studies on page {page + 1}")

                    for study in studies:
                        parsed = self._parse_study(study)
                        if parsed:
                            all_studies.append(parsed)

                    next_page_token = data.get("nextPageToken")
                    if not next_page_token:
                        break

                except httpx.HTTPError as e:
                    logger.error(f"CT.gov API error: {e}")
                    break
                except Exception as e:
                    logger.error(f"Error fetching studies: {e}")
                    break

        logger.info(f"Total studies retrieved: {len(all_studies)}")
        return all_studies

    def _parse_study(self, raw_study: Dict) -> Optional[CTGovStudy]:
        """Parse raw CT.gov API response into CTGovStudy object"""
        try:
            protocol = raw_study.get("protocolSection", {})

            # Identification
            id_module = protocol.get("identificationModule", {})
            nct_id = id_module.get("nctId", "")
            title = id_module.get("briefTitle", id_module.get("officialTitle", ""))

            # Status & Phase
            status_module = protocol.get("statusModule", {})
            status = status_module.get("overallStatus", "UNKNOWN")

            design_module = protocol.get("designModule", {})
            phases = design_module.get("phases", [])
            phase = phases[0] if phases else "N/A"
            phase = phase.replace("PHASE", "Phase ").replace("_", "/")

            # Dates
            start_date = status_module.get("startDateStruct", {}).get("date")
            completion_date = status_module.get("completionDateStruct", {}).get("date")

            # Conditions
            conditions_module = protocol.get("conditionsModule", {})
            conditions = conditions_module.get("conditions", [])

            # Sponsors
            sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
            lead_sponsor = sponsor_module.get("leadSponsor", {}).get("name", "")
            collaborators = [c.get("name", "") for c in sponsor_module.get("collaborators", [])]
            sponsors = [s for s in [lead_sponsor] + collaborators if s]

            # Enrollment
            enrollment_info = design_module.get("enrollmentInfo", {})
            enrollment = enrollment_info.get("count")

            # Locations with investigators
            contacts_module = protocol.get("contactsLocationsModule", {})
            locations = []

            for loc in contacts_module.get("locations", []):
                location_data = {
                    "facility": loc.get("facility", "Unknown Facility"),
                    "city": loc.get("city", ""),
                    "state": loc.get("state", ""),
                    "country": loc.get("country", ""),
                    "status": loc.get("status", ""),
                    "investigators": []
                }

                for contact in loc.get("contacts", []):
                    role = contact.get("role", "")
                    if role in ["PRINCIPAL_INVESTIGATOR", "SUB_INVESTIGATOR", "STUDY_DIRECTOR", "STUDY_CHAIR"]:
                        location_data["investigators"].append({
                            "name": contact.get("name", "Unknown"),
                            "role": role
                        })

                locations.append(location_data)

            return CTGovStudy(
                nct_id=nct_id,
                title=title,
                phase=phase,
                status=status,
                conditions=conditions,
                sponsors=sponsors,
                locations=locations,
                start_date=start_date,
                completion_date=completion_date,
                enrollment=enrollment
            )

        except Exception as e:
            logger.error(f"Error parsing study: {e}")
            return None

    async def aggregate_sites_from_studies(
        self,
        studies: List[CTGovStudy],
        target_condition: Optional[str] = None
    ) -> List[InferredSiteProfile]:
        """
        Aggregate studies into unique site profiles.
        Groups by facility + city + state.
        """
        sites_map: Dict[str, Dict] = {}

        for study in studies:
            for location in study.locations:
                facility = location.get("facility", "Unknown")
                city = location.get("city", "")
                state = location.get("state", "")
                country = location.get("country", "")

                site_key = f"{facility}|{city}|{state}|{country}".lower()

                if site_key not in sites_map:
                    sites_map[site_key] = {
                        "facility_name": facility,
                        "city": city,
                        "state": state,
                        "country": country,
                        "investigators": {},
                        "trials": [],
                        "phases": Counter(),
                        "conditions": Counter(),
                        "sponsors": set(),
                        "statuses": Counter(),
                        "competing_trials": []
                    }

                site = sites_map[site_key]

                trial_info = {
                    "nct_id": study.nct_id,
                    "title": study.title,
                    "phase": study.phase,
                    "status": study.status,
                    "conditions": study.conditions,
                    "enrollment": study.enrollment
                }
                site["trials"].append(trial_info)

                # Check for competing trials
                if target_condition and study.status in self.ACTIVE_STATUSES:
                    condition_match = any(
                        target_condition.lower() in c.lower()
                        for c in study.conditions
                    )
                    if condition_match:
                        site["competing_trials"].append(trial_info)

                site["phases"][study.phase] += 1
                site["statuses"][study.status] += 1

                for condition in study.conditions:
                    site["conditions"][condition] += 1

                for sponsor in study.sponsors:
                    site["sponsors"].add(sponsor)

                for inv in location.get("investigators", []):
                    inv_name = inv.get("name", "Unknown")
                    inv_role = inv.get("role", "UNKNOWN")

                    if inv_name not in site["investigators"]:
                        site["investigators"][inv_name] = {
                            "name": inv_name,
                            "roles": Counter(),
                            "trial_count": 0
                        }

                    site["investigators"][inv_name]["roles"][inv_role] += 1
                    site["investigators"][inv_name]["trial_count"] += 1

        # Convert to InferredSiteProfile objects
        profiles = []

        for site_key, site_data in sites_map.items():
            completed = sum(site_data["statuses"].get(s, 0) for s in self.COMPLETED_STATUSES)
            active = sum(site_data["statuses"].get(s, 0) for s in self.ACTIVE_STATUSES)
            terminated = sum(site_data["statuses"].get(s, 0) for s in self.TERMINATED_STATUSES)

            total = completed + terminated
            completion_rate = round(completed / total, 2) if total > 0 else 0.0

            investigators = sorted(
                [
                    {
                        "name": inv["name"],
                        "roles": dict(inv["roles"]),
                        "trial_count": inv["trial_count"],
                        "primary_role": max(inv["roles"], key=inv["roles"].get) if inv["roles"] else "UNKNOWN"
                    }
                    for inv in site_data["investigators"].values()
                ],
                key=lambda x: x["trial_count"],
                reverse=True
            )[:10]

            sponsors_list = list(site_data["sponsors"])[:20]

            profile = InferredSiteProfile(
                facility_name=site_data["facility_name"],
                city=site_data["city"],
                state=site_data["state"],
                country=site_data["country"],
                investigators=investigators,
                total_trials=len(site_data["trials"]),
                completed_trials=completed,
                active_trials=active,
                terminated_trials=terminated,
                phase_experience=dict(site_data["phases"]),
                therapeutic_experience=dict(site_data["conditions"].most_common(20)),
                sponsors_worked_with=sponsors_list,
                completion_rate=completion_rate,
                trial_history=site_data["trials"][:50],
                competing_trials=site_data["competing_trials"]
            )

            profiles.append(profile)

        profiles.sort(key=lambda x: x.total_trials, reverse=True)
        return profiles

    async def search_sites(
        self,
        condition: str,
        location: Optional[str] = None,
        min_trials: int = 1,
        include_phases: Optional[List[str]] = None
    ) -> List[InferredSiteProfile]:
        """
        High-level method: Search for sites experienced in a condition.
        """
        logger.info(f"Searching sites: condition={condition}, location={location}")

        studies = await self.search_studies(
            condition=condition,
            location=location,
            max_pages=10
        )

        if not studies:
            logger.warning(f"No studies found for condition={condition}")
            return []

        sites = await self.aggregate_sites_from_studies(studies, target_condition=condition)
        sites = [s for s in sites if s.total_trials >= min_trials]

        if include_phases:
            sites = [s for s in sites if any(phase in s.phase_experience for phase in include_phases)]

        logger.info(f"Found {len(sites)} sites matching criteria")
        return sites

    async def get_site_profile(
        self,
        facility_name: str,
        city: Optional[str] = None,
        state: Optional[str] = None,
        condition: Optional[str] = None
    ) -> Optional[InferredSiteProfile]:
        """Get profile for a specific site."""
        location_parts = [p for p in [facility_name, city, state] if p]
        location = ", ".join(location_parts) if location_parts else facility_name

        studies = await self.search_studies(
            condition=condition,
            location=location,
            max_pages=10
        )

        if not studies:
            return None

        sites = await self.aggregate_sites_from_studies(studies, target_condition=condition)

        facility_lower = facility_name.lower()
        for site in sites:
            if facility_lower in site.facility_name.lower():
                if city and city.lower() != site.city.lower():
                    continue
                if state and state.lower() != site.state.lower():
                    continue
                return site

        return sites[0] if sites else None
