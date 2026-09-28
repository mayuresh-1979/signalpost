
from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
from typing import Any


GENERIC_NAME_TOKENS = {
    "as",
    "asa",
    "ab",
    "aksjeselskap",
    "allmennaksjeselskap",
    "ans",
    "ba",
    "bbl",
    "borettslag",
    "da",
    "eiendom",
    "foretak",
    "holding",
    "inc",
    "ltd",
    "limited",
    "norge",
    "norway",
    "sa",
    "sameie",
    "stiftelse",
}


def _tokens(value: Any) -> list[str]:
    text = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )
    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )
    text = text.lower()
    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return [
        token
        for token in text.split()
        if token
        and token not in GENERIC_NAME_TOKENS
    ]


def _structured_names(
    structured: list[dict[str, Any]],
) -> list[str]:
    names: list[str] = []

    for item in structured:
        if not isinstance(item, dict):
            continue

        item_type = item.get("@type")

        if isinstance(item_type, list):
            types = {
                str(value).lower()
                for value in item_type
            }
        else:
            types = {
                str(item_type).lower()
            }

        if (
            "organization" in types
            or "corporation" in types
            or "localbusiness" in types
            or "organization"
            in str(item_type).lower()
        ):
            name = item.get("name")

            if name:
                names.append(str(name))

    return names


def _assessment(
    status: str,
    score: float,
    publishable: bool,
    reasons: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "score": score,
        "publishable": publishable,
        "reasons": reasons or [],
    }


def assess_guessed_website_identity(
    profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Conservative identity gate for deterministic guessed website
    candidates.

    This gate is intentionally separate from the production
    registry-linked website identity gate.

    A guessed domain can only become publishable when the candidate
    provides strong identity evidence. In particular, multi-token
    legal names require an exact compact hostname match plus the
    complete legal-name token set in the title and meaningful page
    text.

    This function must NOT weaken assess_website_identity().
    """

    website = (
        profile
        .get("evidence", {})
        .get("website", {})
    )

    value = website.get("value") or {}

    core = _tokens(
        profile.get("name")
    )

    title = str(
        value.get("title") or ""
    )

    description = str(
        value.get("description") or ""
    )

    main_text = str(
        value.get("main_text_excerpt") or ""
    )

    structured = (
        value.get("structured_organisations")
        or []
    )

    pages = (
        value.get("pages")
        or []
    )

    page_titles = [
        str(page.get("title") or "")
        for page in pages
        if isinstance(page, dict)
        and page.get("title")
    ]

    page_text = [
        str(
            page.get("main_text_excerpt")
            or ""
        )
        for page in pages
        if isinstance(page, dict)
        and page.get("main_text_excerpt")
    ]

    all_text = " ".join(
        [
            title,
            description,
            main_text,
            *page_titles,
            *page_text,
        ]
    )

    normalized_all = " ".join(
        _tokens(all_text)
    )

    candidate_tokens = set(
        _tokens(all_text)
    )

    core_tokens = set(core)

    matched_tokens = sorted(
        core_tokens & candidate_tokens
    )

    token_ratio = (
        len(matched_tokens)
        / len(core_tokens)
        if core_tokens
        else 0.0
    )

    org_digits = re.sub(
        r"\D",
        "",
        str(
            profile.get(
                "organisation_number"
            )
            or ""
        ),
    )

    compact_text = re.sub(
        r"\D",
        "",
        all_text,
    )

    parked_markers = (
        "domain is for sale",
        "domain for sale",
        "hugedomains",
        "parked at",
        "miss hosting",
        "index of /",
        "proudly served by litespeed",
        "please wait while the requested page is loaded",
        "has been informing visitors",
    )

    if any(
        marker in normalized_all
        for marker in parked_markers
    ):
        return _assessment(
            "related_or_uncertain",
            0.1,
            False,
            [
                "candidate appears parked, "
                "for-sale, or otherwise "
                "non-company content"
            ],
        )

    structured_names = _structured_names(
        structured
    )

    if structured_names:
        structured_token_sets = [
            set(_tokens(name))
            for name in structured_names
            if name
        ]

        structured_raw = " ".join(
            json.dumps(
                obj,
                ensure_ascii=False,
            )
            for obj in structured
        )

        structured_digits = re.sub(
            r"\D",
            "",
            structured_raw,
        )

        if (
            org_digits
            and org_digits in structured_digits
        ):
            return _assessment(
                "exact",
                1.0,
                True,
                [
                    "structured organisation "
                    "data contains the registry "
                    "organisation number"
                ],
            )

        if any(
            core_tokens
            and core_tokens.issubset(tokens)
            for tokens in structured_token_sets
        ):
            return _assessment(
                "exact",
                0.98,
                True,
                [
                    "structured organisation "
                    "name matches the registry "
                    "legal-name tokens"
                ],
            )

        return _assessment(
            "related_or_uncertain",
            0.1,
            False,
            [
                "structured organisation "
                "evidence identifies a different "
                "organization"
            ],
        )

    if (
        org_digits
        and len(org_digits) == 9
        and org_digits in compact_text
    ):
        return _assessment(
            "exact",
            1.0,
            True,
            [
                "page content contains the "
                "registry organisation number"
            ],
        )

    identity_fields = [
        title,
        description,
    ]

    exact_name_in_identity = any(
        core_tokens
        and core_tokens.issubset(
            set(_tokens(field))
        )
        for field in identity_fields
    )

    substantive = (
        len(main_text.strip()) >= 120
    )

    if (
        len(core_tokens) >= 2
        and exact_name_in_identity
        and substantive
    ):
        return _assessment(
            "exact",
            0.96,
            True,
            [
                "page title or description "
                "contains the full legal-name "
                "token set",
                "page contains substantive "
                "company text",
            ],
        )

    if (
        len(core_tokens) >= 2
        and token_ratio >= 0.75
        and substantive
    ):
        signals = 0

        title_tokens = set(
            _tokens(title)
        )

        description_tokens = set(
            _tokens(description)
        )

        main_tokens = set(
            _tokens(main_text)
        )

        if core_tokens.issubset(
            title_tokens
        ):
            signals += 1

        if core_tokens.issubset(
            description_tokens
        ):
            signals += 1

        if len(
            core_tokens & main_tokens
        ) >= 2:
            signals += 1

        if len(page_text) >= 1:
            combined_page_tokens = set(
                _tokens(
                    " ".join(page_text)
                )
            )

            if len(
                core_tokens
                & combined_page_tokens
            ) >= 2:
                signals += 1

        if signals >= 2:
            return _assessment(
                "exact",
                0.92,
                True,
                [
                    "multiple independent "
                    "company-name signals agree",
                    "page contains substantive "
                    "company text",
                ],
            )

    final_url = str(
        value.get("final_url")
        or value.get("requested_url")
        or ""
    )

    hostname = ""

    try:
        hostname = (
            urllib.parse.urlparse(
                final_url
            ).hostname
            or ""
        ).lower()
    except Exception:
        hostname = ""

    hostname_label = (
        hostname.split(".")[0]
    )

    hostname_compact = re.sub(
        r"[^a-z0-9]",
        "",
        hostname_label,
    )

    name_compact = re.sub(
        r"[^a-z0-9]",
        "",
        "".join(core),
    )

    domain_name_match = (
        len(core_tokens) >= 2
        and bool(hostname_compact)
        and hostname_compact
        == name_compact
    )

    if domain_name_match:
        title_tokens = set(
            _tokens(title)
        )

        candidate_text_length = len(
            main_text.strip()
        )

        # Candidate-only rule:
        #
        # 1. The hostname must exactly match
        #    the compact legal name.
        # 2. The page title must contain the
        #    complete legal-name token set.
        # 3. The page must contain meaningful
        #    company text.
        #
        # This threshold is deliberately lower
        # than the normal registry-linked gate
        # because legitimate company homepages
        # can be very short.
        if (
            core_tokens.issubset(
                title_tokens
            )
            and candidate_text_length >= 60
        ):
            return _assessment(
                "exact",
                0.94,
                True,
                [
                    "candidate hostname exactly "
                    "matches the compact legal name",
                    "page title contains the full "
                    "legal-name token set",
                    "page contains meaningful "
                    "company text",
                ],
            )

    return _assessment(
        "related_or_uncertain",
        0.3,
        False,
        [
            "candidate website does not establish "
            "sufficient exact legal-entity identity"
        ],
    )


def assess_website_identity(
    profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Production identity gate for registry-linked
    or otherwise already selected company websites.

    This is the primary safety barrier. Do not loosen
    its thresholds merely to increase website coverage.
    """

    website = (
        profile
        .get("evidence", {})
        .get("website", {})
    )

    value = website.get("value") or {}

    name = str(
        profile.get("name") or ""
    )

    core = set(_tokens(name))

    title = str(
        value.get("title") or ""
    )

    description = str(
        value.get("description") or ""
    )

    main_text = str(
        value.get("main_text_excerpt") or ""
    )

    structured = (
        value.get(
            "structured_organisations"
        )
        or []
    )

    structured_names = _structured_names(
        structured
    )

    final_url = str(
        value.get("final_url")
        or value.get("requested_url")
        or website.get("source_url")
        or ""
    )

    try:
        hostname = (
            urllib.parse.urlparse(
                final_url
            ).hostname
            or ""
        ).lower()
    except Exception:
        hostname = ""

    rendered = (
        value.get("js_fallback")
        or {}
    )

    homepage_identity_parts = [
        title,
        description,
        value.get(
            "identity_text_excerpt"
        ),
        hostname,
        *structured_names,
        rendered.get("title"),
    ]

    homepage_identity_text = " ".join(
        str(item or "")
        for item in homepage_identity_parts
    )

    homepage_tokens = set(
        _tokens(homepage_identity_text)
    )

    title_tokens = set(
        _tokens(title)
    )

    description_tokens = set(
        _tokens(description)
    )

    main_tokens = set(
        _tokens(main_text)
    )

    substantive_homepage = (
        len(main_text.strip()) >= 120
    )

    reasons: list[str] = []
    score = 0.0
    status = "related_or_uncertain"

    org_number = str(
        profile.get(
            "organisation_number"
        )
        or ""
    )

    org_digits = re.sub(
        r"\D",
        "",
        org_number,
    )

    all_content = " ".join(
        [
            title,
            description,
            main_text,
            json.dumps(
                structured,
                ensure_ascii=False,
            ),
        ]
    )

    all_digits = re.sub(
        r"\D",
        "",
        all_content,
    )

    parked_markers = (
        "domain is for sale",
        "domain for sale",
        "hugedomains",
        "parked at",
        "miss hosting",
        "index of /",
        "proudly served by litespeed",
        "please wait while the requested page is loaded",
        "has been informing visitors",
    )

    normalized_content = " ".join(
        _tokens(all_content)
    )

    if any(
        marker in normalized_content
        for marker in parked_markers
    ):
        return _assessment(
            "related_or_uncertain",
            0.05,
            False,
            [
                "website appears parked, "
                "for-sale, or placeholder content"
            ],
        )

    # Strongest possible signal:
    # the actual registry organisation number
    # appears in structured/content evidence.
    if (
        org_digits
        and len(org_digits) == 9
        and org_digits in all_digits
    ):
        return _assessment(
            "exact",
            1.0,
            True,
            [
                "website evidence contains the "
                "registry organisation number"
            ],
        )

    # Structured organisation data is strong
    # entity evidence.
    if structured_names:
        structured_token_sets = [
            set(_tokens(item))
            for item in structured_names
            if item
        ]

        if any(
            core
            and core.issubset(tokens)
            for tokens in structured_token_sets
        ):
            return _assessment(
                "exact",
                0.98,
                True,
                [
                    "structured organisation name "
                    "matches the registry legal-name "
                    "tokens"
                ],
            )

        # Structured organisation data naming a
        # different entity is a strong negative.
        if structured_names:
            return _assessment(
                "related_or_uncertain",
                0.1,
                False,
                [
                    "structured organisation evidence "
                    "identifies a different organization"
                ],
            )

    if not core:
        return _assessment(
            "related_or_uncertain",
            0.0,
            False,
            [
                "registry legal name is empty or "
                "cannot be normalized"
            ],
        )

    exact_homepage_name = (
        set(core).issubset(
            title_tokens
        )
        or set(core).issubset(
            description_tokens
        )
    )

    exact_main_name = (
        len(core) >= 2
        and set(core).issubset(
            main_tokens
        )
    )

    # Full legal name in the identity layer
    # plus substantive company text.
    if (
        len(core) >= 2
        and exact_homepage_name
        and substantive_homepage
    ):
        score = 0.95
        status = "exact"

        reasons.extend(
            [
                "homepage title or description "
                "contains the full legal-name "
                "token set",
                "homepage contains substantive "
                "company text",
            ]
        )

    # Single-token legal names need additional
    # substantive evidence.
    elif (
        len(core) == 1
        and exact_homepage_name
        and substantive_homepage
    ):
        score = 0.95
        status = "exact"

        reasons.extend(
            [
                "homepage title or description "
                "contains the legal-name token",
                "homepage contains substantive "
                "company text",
            ]
        )

    # Multiple independent name signals.
    elif (
        len(core) >= 2
        and exact_main_name
        and substantive_homepage
    ):
        score = 0.92
        status = "exact"

        reasons.extend(
            [
                "full legal-name token set appears "
                "in substantive homepage text",
                "homepage contains substantive "
                "company text",
            ]
        )

    else:
        matched = (
            set(core)
            & homepage_tokens
        )

        ratio = (
            len(matched)
            / len(set(core))
            if core
            else 0.0
        )

        # Partial name agreement is useful for
        # diagnosis but is not publishable.
        if ratio >= 0.75:
            score = 0.75
            status = "review"

            reasons.extend(
                [
                    "most legal-name tokens are "
                    "present in website identity text",
                    "exact legal-entity identity was "
                    "not established",
                ]
            )
        elif ratio >= 0.5:
            score = 0.5
            status = "related_or_uncertain"

            reasons.extend(
                [
                    "some legal-name tokens are "
                    "present",
                    "website does not establish "
                    "exact legal-entity identity",
                ]
            )
        else:
            score = 0.3
            status = "related_or_uncertain"

            reasons.extend(
                [
                    "website identity text does not "
                    "sufficiently match the registry "
                    "legal name",
                ]
            )

    publishable = (
        status == "exact"
        and score >= 0.9
    )

    return _assessment(
        status,
        score,
        publishable,
        reasons,
    )


def assess_social_identity(
    profile: dict[str, Any],
    link: dict[str, Any],
) -> dict[str, Any]:
    """
    Conservative identity assessment for a social
    profile discovered from a company website.

    Social links are never promoted solely because
    their hostname is a permitted social platform.
    """

    url = str(
        link.get("url")
        or ""
    ).strip()

    platform = str(
        link.get("platform")
        or ""
    ).strip().lower()

    if not url:
        return {
            "platform": platform,
            "url": url,
            "status": "related_or_uncertain",
            "score": 0.0,
            "publishable": False,
            "reason": "social URL is empty",
            "method": (
                "deterministic_social_handle_identity_v1"
            ),
        }

    try:
        parsed = urllib.parse.urlparse(
            url
        )

        hostname = (
            parsed.hostname
            or ""
        ).lower()

        path = (
            parsed.path
            or ""
        ).strip("/")
    except Exception:
        return {
            "platform": platform,
            "url": url,
            "status": "related_or_uncertain",
            "score": 0.0,
            "publishable": False,
            "reason": "social URL could not be parsed",
            "method": (
                "deterministic_social_handle_identity_v1"
            ),
        }

    company_tokens = set(
        _tokens(
            profile.get("name")
        )
    )

    hostname_tokens = set(
        _tokens(hostname)
    )

    path_tokens = set(
        _tokens(
            path.replace(
                "/",
                " ",
            )
        )
    )

    website = (
        profile
        .get("evidence", {})
        .get("website", {})
    )

    website_value = (
        website.get("value")
        or {}
    )

    website_title_tokens = set(
        _tokens(
            website_value.get(
                "title"
            )
        )
    )

    website_text_tokens = set(
        _tokens(
            website_value.get(
                "main_text_excerpt"
            )
        )
    )

    # A social URL explicitly linked from an exact
    # company website is useful evidence, but the
    # handle still needs a company-name signal.
    handle_match = bool(
        company_tokens
        and (
            company_tokens.issubset(
                path_tokens
            )
            or len(
                company_tokens
                & path_tokens
            )
            >= max(
                1,
                min(
                    2,
                    len(company_tokens),
                ),
            )
        )
    )

    website_name_match = bool(
        company_tokens
        and (
            company_tokens.issubset(
                website_title_tokens
            )
            or company_tokens.issubset(
                website_text_tokens
            )
        )
    )

    platform_hosts = {
        "linkedin.com",
        "www.linkedin.com",
        "facebook.com",
        "www.facebook.com",
        "instagram.com",
        "www.instagram.com",
        "youtube.com",
        "www.youtube.com",
        "x.com",
        "www.x.com",
        "twitter.com",
        "www.twitter.com",
    }

    host_allowed = (
        hostname in platform_hosts
        or any(
            hostname.endswith(
                "." + root
            )
            for root in platform_hosts
        )
    )

    if (
        host_allowed
        and handle_match
        and website_name_match
    ):
        return {
            "platform": platform,
            "url": url,
            "status": "exact",
            "score": 0.95,
            "publishable": True,
            "reason": (
                "social handle matches the company "
                "name and the exact company website "
                "contains the same identity signal"
            ),
            "method": (
                "deterministic_social_handle_identity_v1"
            ),
        }

    if (
        host_allowed
        and website_name_match
    ):
        return {
            "platform": platform,
            "url": url,
            "status": "review",
            "score": 0.8,
            "publishable": False,
            "reason": (
                "social URL is linked from a matching "
                "company website but the social handle "
                "does not independently establish "
                "company identity"
            ),
            "method": (
                "deterministic_social_handle_identity_v1"
            ),
        }

    return {
        "platform": platform,
        "url": url,
        "status": "related_or_uncertain",
        "score": 0.3,
        "publishable": False,
        "reason": (
            "social URL does not establish sufficient "
            "exact company identity"
        ),
        "method": (
            "deterministic_social_handle_identity_v1"
        ),
    }


def apply_website_identity_gate(
    profile: dict[str, Any],
    website: dict[str, Any],
) -> dict[str, Any]:
    """
    Apply the production website identity gate and
    quarantine social links when exact company
    identity has not been established.
    """

    if website.get("status") != "available":
        return {
            "website": website,
            "assessment": None,
            "quarantined_social_links": 0,
        }

    temporary_profile = {
        **profile,
        "evidence": {
            **profile.get("evidence", {}),
            "website": website,
        },
    }

    value = website.get("value") or {}

    assessment = assess_website_identity(
        temporary_profile
    )

    value["identity_assessment"] = (
        assessment
    )

    original = list(
        value.get(
            "discovered_social_links"
        )
        or value.get(
            "social_links"
        )
        or []
    )

    value["discovered_social_links"] = (
        original
    )

    social_assessments = [
        assess_social_identity(
            profile,
            link,
        )
        for link in original
        if isinstance(link, dict)
    ]

    value["social_link_assessments"] = (
        social_assessments
    )

    publishable_social_links = [
        link
        for link, assessment in zip(
            original,
            social_assessments,
        )
        if assessment["publishable"]
    ]

    # Only expose social links as trusted company
    # links when both the website and social identity
    # gates pass.
    if assessment["publishable"]:
        value["social_links"] = (
            publishable_social_links
        )
    else:
        value["social_links"] = []

    website["value"] = value

    return {
        "website": website,
        "assessment": assessment,
        "quarantined_social_links": (
            len(original)
            - len(value["social_links"])
        ),
    }
