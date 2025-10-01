"""
Feasibility Scorer

Scores site feasibility by matching protocol requirements against site capabilities.
This is separate from survey question answering - it's pure requirement vs capability matching.
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

@dataclass
class FeasibilityMatch:
    requirement: str
    category: str
    matched: bool
    site_capability: str
    confidence: float
    points: int
    reasoning: str

@dataclass
class FeasibilityScore:
    total_score: int
    max_possible: int
    percentage: float
    category_scores: Dict[str, int]
    matches: List[FeasibilityMatch]
    flags: List[str]
    critical_gaps: List[str]

class FeasibilityScorer:
    """Score site feasibility based on protocol requirements vs site capabilities"""

    def __init__(self):
        # Scoring weights for different categories
        self.category_weights = {
            "equipment": 30,      # 30% of total score
            "staff": 25,          # 25% of total score
            "population": 25,     # 25% of total score
            "experience": 15,     # 15% of total score
            "procedures": 5       # 5% of total score
        }

    def score_feasibility(
        self,
        protocol_requirements: Dict[str, Any],
        site_profile: Dict[str, Any]
    ) -> FeasibilityScore:
        """Score site feasibility against protocol requirements"""

        all_matches = []
        category_scores = {}
        flags = []
        critical_gaps = []

        # Score each category
        for category, weight in self.category_weights.items():
            matches, score, category_flags = self._score_category(
                category, protocol_requirements, site_profile, weight
            )

            all_matches.extend(matches)
            category_scores[category] = score
            flags.extend(category_flags)

            # Check for critical gaps
            critical_misses = [m for m in matches if not m.matched and "critical" in m.requirement.lower()]
            for miss in critical_misses:
                critical_gaps.append(f"{category.title()}: {miss.requirement}")

        # Calculate total score
        total_score = sum(category_scores.values())
        max_possible = sum(self.category_weights.values())
        percentage = (total_score / max_possible) * 100

        # Add overall flags
        if percentage < 50:
            flags.append("Low feasibility score - significant gaps identified")
        if len(critical_gaps) > 0:
            flags.append(f"{len(critical_gaps)} critical requirements not met")

        return FeasibilityScore(
            total_score=total_score,
            max_possible=max_possible,
            percentage=percentage,
            category_scores=category_scores,
            matches=all_matches,
            flags=flags,
            critical_gaps=critical_gaps
        )

    def _score_category(
        self,
        category: str,
        protocol_reqs: Dict[str, Any],
        site_profile: Dict[str, Any],
        max_points: int
    ) -> Tuple[List[FeasibilityMatch], int, List[str]]:
        """Score a specific category of requirements"""

        if category == "equipment":
            return self._score_equipment(protocol_reqs, site_profile, max_points)
        elif category == "staff":
            return self._score_staff(protocol_reqs, site_profile, max_points)
        elif category == "population":
            return self._score_population(protocol_reqs, site_profile, max_points)
        elif category == "experience":
            return self._score_experience(protocol_reqs, site_profile, max_points)
        elif category == "procedures":
            return self._score_procedures(protocol_reqs, site_profile, max_points)
        else:
            return [], 0, []

    def _score_equipment(self, protocol_reqs: Dict, site_profile: Dict, max_points: int) -> Tuple[List[FeasibilityMatch], int, List[str]]:
        """Score equipment requirements"""
        matches = []
        flags = []

        # Get equipment requirements from protocol
        equipment_reqs = protocol_reqs.get("requirements", {}).get("equipment", [])
        site_equipment = site_profile.get("procedures_equipment", {}).get("special_equipment", [])

        if not equipment_reqs:
            # No specific equipment requirements
            return [], max_points, []

        points_per_item = max_points // len(equipment_reqs)
        total_points = 0

        for req in equipment_reqs:
            equipment_name = req.get("equipment", "")
            criticality = req.get("criticality", "optional")

            # Check if site has this equipment (fuzzy matching)
            matched, site_item, confidence = self._match_equipment(equipment_name, site_equipment)

            points = points_per_item if matched else 0
            if criticality == "critical" and not matched:
                points = -points_per_item  # Penalty for missing critical equipment

            total_points += points

            match = FeasibilityMatch(
                requirement=equipment_name,
                category="equipment",
                matched=matched,
                site_capability=site_item if matched else "Not available",
                confidence=confidence,
                points=points,
                reasoning=f"{'Found' if matched else 'Missing'} {criticality} equipment"
            )
            matches.append(match)

            if criticality == "critical" and not matched:
                flags.append(f"Critical equipment missing: {equipment_name}")

        return matches, max(0, total_points), flags

    def _score_staff(self, protocol_reqs: Dict, site_profile: Dict, max_points: int) -> Tuple[List[FeasibilityMatch], int, List[str]]:
        """Score staffing requirements"""
        matches = []
        flags = []

        staff_reqs = protocol_reqs.get("requirements", {}).get("staff", [])
        site_staff = site_profile.get("staff_resources", {})

        if not staff_reqs:
            return [], max_points, []

        points_per_item = max_points // len(staff_reqs)
        total_points = 0

        for req in staff_reqs:
            role = req.get("role", "")
            fte_required = req.get("fte_required", 0)
            criticality = req.get("criticality", "optional")

            # Check coordinator FTE specifically
            if "coordinator" in role.lower():
                site_fte = site_staff.get("coordinators_fte", 0)
                matched = site_fte >= fte_required if fte_required else site_fte > 0
                confidence = min(1.0, site_fte / max(fte_required, 1)) if fte_required else 0.8
                site_capability = f"{site_fte} FTE available"
            else:
                # Other staff types - check if site has specialists
                specialists = site_staff.get("specialist_access", [])
                matched = any(role.lower() in spec.lower() for spec in specialists)
                confidence = 0.7 if matched else 0.0
                site_capability = "Specialist access available" if matched else "Not available"

            points = points_per_item if matched else 0
            if criticality == "critical" and not matched:
                points = -points_per_item

            total_points += points

            match = FeasibilityMatch(
                requirement=f"{role} ({fte_required} FTE)" if fte_required else role,
                category="staff",
                matched=matched,
                site_capability=site_capability,
                confidence=confidence,
                points=points,
                reasoning=f"{'Adequate' if matched else 'Insufficient'} {role} staffing"
            )
            matches.append(match)

            if criticality == "critical" and not matched:
                flags.append(f"Critical staffing gap: {role}")

        return matches, max(0, total_points), flags

    def _score_population(self, protocol_reqs: Dict, site_profile: Dict, max_points: int) -> Tuple[List[FeasibilityMatch], int, List[str]]:
        """Score patient population requirements"""
        matches = []
        flags = []

        pop_reqs = protocol_reqs.get("requirements", {}).get("population", {})
        site_pop = site_profile.get("population_capabilities", {})

        if not pop_reqs:
            return [], max_points, []

        total_points = 0
        req_count = 0

        # Age range check
        if "age_range" in pop_reqs:
            req_count += 1
            req_age = pop_reqs["age_range"]
            site_ages = site_pop.get("age_ranges_served", [])

            # Check if site serves the required age range
            matched = any(self._age_range_overlap(req_age, age_str) for age_str in site_ages)
            confidence = 0.9 if matched else 0.0

            points = (max_points // 4) if matched else 0
            total_points += points

            match = FeasibilityMatch(
                requirement=f"Ages {req_age['min']}-{req_age['max']}",
                category="population",
                matched=matched,
                site_capability=", ".join(site_ages) if site_ages else "No age data",
                confidence=confidence,
                points=points,
                reasoning="Age range compatibility"
            )
            matches.append(match)

        # Enrollment target check
        if "target_enrollment" in pop_reqs:
            req_count += 1
            target = pop_reqs["target_enrollment"]
            annual_volume = site_pop.get("annual_patient_volume", 0)

            # Assume 25% of annual volume is recruitable
            recruitable = annual_volume * 0.25
            matched = recruitable >= target
            confidence = min(1.0, recruitable / target) if target > 0 else 0.0

            points = (max_points // 2) if matched else max(0, int((max_points // 2) * confidence))
            total_points += points

            match = FeasibilityMatch(
                requirement=f"{target} patients needed",
                category="population",
                matched=matched,
                site_capability=f"~{int(recruitable)} recruitable from {annual_volume:,} annual volume",
                confidence=confidence,
                points=points,
                reasoning="Enrollment target feasibility"
            )
            matches.append(match)

            if not matched:
                flags.append(f"High enrollment target: {target} patients needed")

        # If no specific requirements, give full points
        if req_count == 0:
            total_points = max_points

        return matches, total_points, flags

    def _score_experience(self, protocol_reqs: Dict, site_profile: Dict, max_points: int) -> Tuple[List[FeasibilityMatch], int, List[str]]:
        """Score relevant experience"""
        matches = []
        flags = []

        site_experience = site_profile.get("experience_history", {})
        therapeutic_areas = site_experience.get("therapeutic_areas", [])
        sponsors = site_experience.get("previous_sponsors", [])

        total_points = 0

        # Check therapeutic area experience
        if "primary_indication" in protocol_reqs.get("requirements", {}).get("population", {}):
            indication = protocol_reqs["requirements"]["population"]["primary_indication"]
            matched = any(indication.lower() in area.lower() for area in therapeutic_areas)
            confidence = 0.9 if matched else 0.0
            points = (max_points // 2) if matched else 0
            total_points += points

            match = FeasibilityMatch(
                requirement=f"{indication} experience",
                category="experience",
                matched=matched,
                site_capability=", ".join(therapeutic_areas[:3]) if therapeutic_areas else "No therapeutic areas listed",
                confidence=confidence,
                points=points,
                reasoning="Therapeutic area experience"
            )
            matches.append(match)

        # Assume some sponsor experience points
        if sponsors:
            points = max_points // 2
            total_points += points

            match = FeasibilityMatch(
                requirement="Clinical trial experience",
                category="experience",
                matched=True,
                site_capability=f"{len(sponsors)} previous sponsors",
                confidence=min(1.0, len(sponsors) / 5),  # Max confidence at 5+ sponsors
                points=points,
                reasoning="Previous sponsor experience"
            )
            matches.append(match)

        return matches, total_points, flags

    def _score_procedures(self, protocol_reqs: Dict, site_profile: Dict, max_points: int) -> Tuple[List[FeasibilityMatch], int, List[str]]:
        """Score procedural capabilities"""
        matches = []
        flags = []

        # For now, give some basic points if site has procedure capabilities
        available_procedures = site_profile.get("procedures_equipment", {}).get("available_procedures", [])

        if available_procedures:
            match = FeasibilityMatch(
                requirement="Basic procedural capabilities",
                category="procedures",
                matched=True,
                site_capability=f"{len(available_procedures)} procedures available",
                confidence=0.8,
                points=max_points,
                reasoning="Site has procedural capabilities"
            )
            matches.append(match)
            return matches, max_points, flags
        else:
            return matches, 0, []

    def _match_equipment(self, required: str, available: List[str]) -> Tuple[bool, str, float]:
        """Match required equipment against available equipment with fuzzy matching"""
        required_lower = required.lower()

        for item in available:
            item_lower = item.lower()

            # Exact match
            if required_lower == item_lower:
                return True, item, 1.0

            # Partial match
            if required_lower in item_lower or item_lower in required_lower:
                return True, item, 0.8

            # Keyword match
            req_keywords = required_lower.split()
            item_keywords = item_lower.split()

            if any(keyword in item_keywords for keyword in req_keywords):
                return True, item, 0.6

        return False, "", 0.0

    def _age_range_overlap(self, req_range: Dict, site_range_str: str) -> bool:
        """Check if age ranges overlap"""
        try:
            # Parse site age range string like "18-65" or "65+"
            if "-" in site_range_str:
                parts = site_range_str.split("-")
                site_min = int(parts[0])
                site_max = int(parts[1]) if parts[1] != "" else 100
            elif "+" in site_range_str:
                site_min = int(site_range_str.replace("+", ""))
                site_max = 100
            else:
                return False

            # Check overlap
            req_min = req_range["min"]
            req_max = req_range["max"]

            return not (req_max < site_min or req_min > site_max)

        except (ValueError, KeyError):
            return False