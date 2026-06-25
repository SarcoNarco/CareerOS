from __future__ import annotations

from careeros.services.feature_builder import InternshipFeatures, ProfileFeatures


def build_score_explanation(
    profile_features: ProfileFeatures,
    internship_features: InternshipFeatures,
    scores: dict[str, float],
) -> dict[str, object]:
    matched_skills = sorted(profile_features.skill_names & internship_features.skill_names)
    matched_tokens = sorted(profile_features.tokens & internship_features.tokens)[:20]
    role_matches = _role_matches(
        target_roles=profile_features.target_roles,
        internship_title=internship_features.normalized_title,
        role_family=internship_features.role_family,
    )
    location_matches = _location_matches(
        target_locations=profile_features.target_locations,
        normalized_location=internship_features.normalized_location,
        work_mode=internship_features.work_mode.value,
    )

    return {
        "scoring_version": "hybrid:v1",
        "weights": {
            "normalized_feature_score": 0.40,
            "semantic_score": 0.25,
            "skill_score": 0.20,
            "experience_score": 0.15,
        },
        "component_scores": scores,
        "signals": {
            "matched_skills": matched_skills,
            "matched_claim_terms": matched_tokens,
            "role_matches": role_matches,
            "location_matches": location_matches,
            "hard_filter_passed": scores["hard_filter_passed"] == 1.0,
        },
        "summary": {
            "reason": "Deterministic hybrid score from normalized features, semantic similarity, skill overlap, and approved-claim text overlap.",
            "llm_generated": False,
        },
    }


def _role_matches(
    target_roles: set[str],
    internship_title: str | None,
    role_family: str | None,
) -> list[str]:
    haystack = " ".join(part for part in (internship_title, role_family) if part)
    return sorted(role for role in target_roles if role and _role_matches_text(role, haystack))


def _role_matches_text(role: str, text: str) -> bool:
    if role in text:
        return True
    if "backend" in role and ("swe" in text or "software" in text):
        return True
    if "software" in role and "swe" in text:
        return True
    if "machine learning" in role and "ml" in text:
        return True
    if role == "ml intern" and "ml" in text:
        return True
    if "data" in role and "data" in text:
        return True
    return False


def _location_matches(
    target_locations: set[str],
    normalized_location: str | None,
    work_mode: str,
) -> list[str]:
    haystack = " ".join(part for part in (normalized_location, work_mode) if part)
    return sorted(location for location in target_locations if location and location in haystack)
