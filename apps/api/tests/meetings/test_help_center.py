"""Database-backed Help Center integration coverage."""

from httpx import AsyncClient


async def test_help_articles_are_seeded_searchable_and_admin_extensible(
    meeting_client: AsyncClient,
    meeting_identity: tuple[dict[str, str], str],
) -> None:
    headers, _ = meeting_identity
    articles = await meeting_client.get("/api/v1/help/articles", headers=headers)
    assert articles.status_code == 200
    assert len(articles.json()["data"]) >= 20
    assert any(row["title"] == "Backup & Restore" for row in articles.json()["data"])

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

    analytics = await meeting_client.get("/api/v1/help/analytics", headers=headers)
    assert analytics.status_code == 200
    assert analytics.json()["data"]["total_views"] >= 2
