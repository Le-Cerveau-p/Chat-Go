def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_thread(client):
    # login
    r = client.post("/api/token", data={"username": "testuser", "password": "secret"})
    token = r.json()["access_token"]

    r = client.post(
        "/api/threads",
        json={"name": "Test Thread", "is_group": True},
        headers=auth_header(token),
    )

    assert r.status_code == 200
    assert "id" in r.json()
