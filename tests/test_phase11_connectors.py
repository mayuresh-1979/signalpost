import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from norway_company_agent.external_footprint import (
    PLATFORMS,
    SIGNAL_TYPES,
    validate_observation,
    publishable_observation,
)
from scripts.extract_verified_social_handles import extract_handles
from scripts.extract_company_site_news import extract_news_observations, observation as site_news_observation


def test_handles_require_publishable_website():
    """Verify that unpublishable or unavailable websites yield 0 handle observations."""
    profile_unavailable = {
        "organisation_number": "123456789",
        "evidence": {
            "website": {
                "status": "not_found",
            }
        }
    }
    assert extract_handles(profile_unavailable) == []

    profile_unpublishable = {
        "organisation_number": "123456789",
        "evidence": {
            "website": {
                "status": "available",
                "source_url": "https://example.no/",
                "content_sha256": "a" * 64,
                "value": {
                    "identity_assessment": {"publishable": False, "score": 0.3},
                    "social_links": [{"platform": "facebook", "url": "https://facebook.com/test"}],
                }
            }
        }
    }
    assert extract_handles(profile_unpublishable) == []


def test_handles_require_valid_hash_and_url():
    """Verify that missing or invalid digest/URL yields 0 handle observations."""
    profile_bad_hash = {
        "organisation_number": "123456789",
        "evidence": {
            "website": {
                "status": "available",
                "source_url": "https://example.no/",
                "content_sha256": "short_hash",
                "value": {
                    "identity_assessment": {"publishable": True, "score": 0.95},
                    "social_links": [{"platform": "facebook", "url": "https://facebook.com/test"}],
                }
            }
        }
    }
    assert extract_handles(profile_bad_hash) == []


def test_handles_extracted_are_fully_publishable():
    """Verify that handles extracted from a valid profile pass all validator gates."""
    profile_valid = {
        "organisation_number": "991429999",
        "evidence": {
            "website": {
                "status": "available",
                "source_url": "https://www.hoiland-gard.no/",
                "content_sha256": "c" * 64,
                "retrieved_at": "2026-09-24T02:00:00Z",
                "value": {
                    "final_url": "https://www.hoiland-gard.no/",
                    "content_sha256": "c" * 64,
                    "identity_assessment": {"publishable": True, "score": 0.96},
                    "social_links": [
                        {"platform": "facebook", "url": "https://facebook.com/Hoilandgard"},
                        {"platform": "instagram", "url": "https://instagram.com/hoilandgard"},
                    ],
                }
            }
        }
    }
    obs = extract_handles(profile_valid)
    assert len(obs) == 2
    for item in obs:
        errors = validate_observation(item)
        assert errors == [], f"Validation errors: {errors}"
        assert publishable_observation(item) is True
        assert item["platform"] in PLATFORMS
        assert item["signal_type"] in SIGNAL_TYPES
        assert item["acquisition_mode"] == "permitted_public_page"
        assert item["rights_status"] == "approved"


def test_quarantined_connectors_fail_publishable_gate():
    """Verify that experimental and unapproved connectors fail publishable_observation."""
    # Google News RSS (rights_review_experiment)
    news_obs = {
        "id": "news-1",
        "organisation_number": "991429999",
        "platform": "news",
        "signal_type": "public_mention",
        "source_url": "https://news.example.no/article-1",
        "retrieved_at": "2026-09-24T02:00:00Z",
        "content_sha256": "d" * 64,
        "exact_entity": True,
        "identity_proof": [{"type": "exact_legal_name", "value": "Test"}],
        "acquisition_mode": "rights_review_experiment",
        "rights_status": "review_required",
        "source_class": "public_news",
        "evidence_span": "Article snippet",
    }
    assert not publishable_observation(news_obs)

    # Google Places / Maps scraper (unofficial_api_experiment)
    places_obs = {
        "id": "places-1",
        "organisation_number": "991429999",
        "platform": "google_places",
        "signal_type": "place_summary",
        "source_url": "https://maps.google.com/?cid=123",
        "retrieved_at": "2026-09-24T02:00:00Z",
        "content_sha256": "e" * 64,
        "exact_entity": True,
        "identity_proof": [{"type": "places_identity_resolution", "value": "Test"}],
        "acquisition_mode": "unofficial_api_experiment",
        "rights_status": "review_required",
        "source_class": "public_business_listing",
        "evidence_span": "Title; Address; Phone",
    }
    assert not publishable_observation(places_obs)


def test_site_news_requires_publishable_website():
    """Verify that unpublishable website yields 0 site news observations."""
    profile = {
        "organisation_number": "123456789",
        "name": "TEST AS",
        "evidence": {
            "website": {
                "status": "available",
                "source_url": "https://example.no/",
                "content_sha256": "a" * 64,
                "value": {
                    "identity_assessment": {"publishable": False, "score": 0.3},
                    "pages": [
                        {
                            "url": "https://example.no/nyheter/artikkel-1",
                            "title": "Tittel",
                            "content_sha256": "b" * 64,
                            "text_excerpt": "Dette er en nyhetstekst.",
                        }
                    ],
                },
            }
        },
    }
    assert extract_news_observations(profile, max_articles=2) == []
    assert site_news_observation(profile) is None


def test_site_news_multi_article_and_norwegian_paths():
    """Verify Norwegian paths and multi-article extraction (up to max_articles)."""
    profile = {
        "organisation_number": "991429999",
        "name": "HØILAND GARD AS",
        "evidence": {
            "website": {
                "status": "available",
                "source_url": "https://www.hoiland-gard.no/",
                "content_sha256": "c" * 64,
                "retrieved_at": "2026-09-24T02:00:00Z",
                "value": {
                    "final_url": "https://www.hoiland-gard.no/",
                    "content_sha256": "c" * 64,
                    "identity_assessment": {"publishable": True, "score": 0.96},
                    "pages": [
                        {
                            "url": "https://www.hoiland-gard.no/pressemeldinger/nyhet-1",
                            "title": "Pressemelding 1",
                            "content_sha256": "d" * 64,
                            "text_excerpt": "Pressemelding tekst for Høiland Gard AS.",
                        },
                        {
                            "url": "https://www.hoiland-gard.no/artikkel/nyhet-2",
                            "title": "Artikkel 2",
                            "content_sha256": "e" * 64,
                            "text_excerpt": "Artikkel tekst for Høiland Gard AS.",
                        },
                        {
                            "url": "https://www.hoiland-gard.no/aktuelt/nyhet-3",
                            "title": "Aktuelt 3",
                            "content_sha256": "f" * 64,
                            "text_excerpt": "Aktuelt tekst for Høiland Gard AS.",
                        },
                    ],
                },
            }
        },
    }
    obs_max2 = extract_news_observations(profile, max_articles=2)
    assert len(obs_max2) == 2, f"Expected 2 observations, got {len(obs_max2)}"
    assert obs_max2[0]["id"] != obs_max2[1]["id"]
    for item in obs_max2:
        errors = validate_observation(item)
        assert errors == [], f"Validation errors: {errors}"
        assert publishable_observation(item) is True
        assert item["platform"] == "company_site"
        assert item["signal_type"] == "public_post"
        assert item["acquisition_mode"] == "permitted_public_page"
        assert item["rights_status"] == "approved"

    # Backward compatibility helper returns 1 observation
    single = site_news_observation(profile)
    assert single is not None
    assert single["id"] == obs_max2[0]["id"]


if __name__ == "__main__":
    test_handles_require_publishable_website()
    test_handles_require_valid_hash_and_url()
    test_handles_extracted_are_fully_publishable()
    test_quarantined_connectors_fail_publishable_gate()
    test_site_news_requires_publishable_website()
    test_site_news_multi_article_and_norwegian_paths()
    print("All Phase 11 & Phase 12B connector safety tests passed successfully!")
