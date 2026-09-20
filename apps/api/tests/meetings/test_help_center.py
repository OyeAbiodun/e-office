"""Database-backed Help Center integration coverage."""

from httpx import AsyncClient


async def test_help_articles_are_seeded_searchable_and_admin_extensible(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    headers, _ = meeting_identity
    articles = await meeting_client.get("/api/v1/help/articles", headers=headers)
    assert articles.status_code == 200
    assert len(articles.json()["data"]) >= 40
    assert any(row["title"] == "Backup & Restore" for row in articles.json()["data"])
    assert any(row["title"] == "Employee Learning Path" for row in articles.json()["data"])

    expected_searches = {
        "request leave": "leave",
        "download payslip": "payroll",
        "approve voucher": "vouchers",
        "weekly report": "reporting-intelligence",
        "create project": "projects",
        "access denied": "quick-start",
        "change password": "first-login",
    }
    for phrase, slug in expected_searches.items():
        result = await meeting_client.get(
            "/api/v1/help/articles", params={"search": phrase}, headers=headers
        )
        assert result.status_code == 200
        assert slug in [row["slug"] for row in result.json()["data"]]

    search = await meeting_client.get("/api/v1/help/articles?search=kubernetes", headers=headers)
    assert [row["slug"] for row in search.json()["data"]] == ["deploy-kubernetes"]

    created = await meeting_client.post(
        "/api/v1/help/articles",
        headers=headers,
        json={
            "slug": "custom-operating-guide",
            "title": "Custom Operating Guide",
            "summary": "Organization-specific operating guidance.",
            "category": "Administrator Guide",
            "content": "# Custom Operating Guide\n\n## Procedure\n\n1. Verify policy.",
            "version": 1,
        },
    )
    assert created.status_code == 201
    fetched = await meeting_client.get(
        "/api/v1/help/articles/custom-operating-guide", headers=headers
    )
    assert fetched.json()["data"]["version"] == 1

    context = await meeting_client.get("/api/v1/help/context/calendar", headers=headers)
    assert context.status_code == 200
    assert context.json()["data"]["article"]["slug"] == "calendar"
    for context_id, slug in {
        "dashboard": "quick-start",
        "my-space": "my-space",
        "projects": "projects",
        "tasks": "tasks-activities",
        "leave": "leave",
        "payroll": "payroll",
        "finance": "finance",
        "vouchers": "vouchers",
        "reports": "reporting-intelligence",
        "administration": "administration",
    }.items():
        response = await meeting_client.get(f"/api/v1/help/context/{context_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["data"]["article"]["slug"] == slug

    article_id = context.json()["data"]["article"]["id"]
    favorited = await meeting_client.post(
        f"/api/v1/help/articles/{article_id}/favorite", headers=headers
    )
    assert favorited.json()["data"]["favorite"] is True
    favorites = await meeting_client.get("/api/v1/help/favorites", headers=headers)
    assert any(row["slug"] == "calendar" for row in favorites.json()["data"])

    revision = await meeting_client.post(
        "/api/v1/help/articles/custom-operating-guide/revisions",
        headers=headers,
        json={
            "title": "Custom Operating Guide",
            "summary": "Reviewed organization-specific operating guidance.",
            "category": "Administrator Handbook",
            "content": "# Custom Operating Guide\n\n## Reviewed procedure",
            "workflow_status": "review",
            "context_ids": ["administration"],
        },
    )
    assert revision.status_code == 201
    assert revision.json()["data"]["version"] == 2
    versions = await meeting_client.get(
        "/api/v1/help/articles/custom-operating-guide/versions", headers=headers
    )
    assert [row["version"] for row in versions.json()["data"]] == [2, 1]

    customized = await meeting_client.post(
        "/api/v1/help/articles/finance/revisions",
        headers=headers,
        json={
            "title": "Finance Center — Organization Procedure",
            "summary": "Administrator-approved finance operating procedure.",
            "category": "Finance & Payroll",
            "content": (
                "# Finance Center\n\n## Organization procedure\n\n" "Keep this approved guidance."
            ),
            "workflow_status": "published",
            "context_ids": ["finance"],
        },
    )
    assert customized.status_code == 201
    assert customized.json()["data"]["version"] == 2

    # Listing invokes baseline reconciliation again. Administrator-authored
    # revisions must remain authoritative and must never be overwritten.
    await meeting_client.get("/api/v1/help/articles", headers=headers)
    preserved = await meeting_client.get("/api/v1/help/articles/finance", headers=headers)
    assert preserved.json()["data"]["title"] == "Finance Center — Organization Procedure"
    assert preserved.json()["data"]["version"] == 2

    analytics = await meeting_client.get("/api/v1/help/analytics", headers=headers)
    assert analytics.status_code == 200
    assert analytics.json()["data"]["total_views"] >= 2


async def test_support_requests_are_persisted_with_safe_context(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    headers, _ = meeting_identity
    created = await meeting_client.post(
        "/api/v1/help/support",
        headers=headers,
        json={
            "request_type": "issue",
            "priority": "high",
            "subject": "Calendar workflow is blocked",
            "description": "The event editor remains unavailable after the calendar loads.",
            "page_url": "http://localhost/calendar",
            "module": "calendar",
            "diagnostics": {
                "route": "/calendar",
                "viewport": "1440x900",
                "password": "must-not-be-stored",
            },
        },
    )
    assert created.status_code == 201
    request = created.json()["data"]
    assert request["reference"].startswith("OF-")
    assert request["status"] == "open"

    history = await meeting_client.get("/api/v1/help/support", headers=headers)
    assert history.status_code == 200
    assert any(row["reference"] == request["reference"] for row in history.json()["data"])
