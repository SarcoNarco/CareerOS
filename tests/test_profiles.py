def test_create_profile(client, auth_headers) -> None:
    response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Sarosh",
            "email": "sarosh@example.com",
            "timezone": "Asia/Kolkata",
            "headline": "CS Student",
            "summary": "Focused on ML internships.",
            "target_roles": ["Machine Learning Intern"],
            "target_locations": ["India", "Remote"],
            "work_preferences": {"remote": True},
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["headline"] == "CS Student"
    assert payload["user"]["display_name"] == "Sarosh"
    assert payload["target_roles"] == ["Machine Learning Intern"]

