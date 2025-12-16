def test_register_and_login(client):
    r = client.post(
        "/api/register",
        json={
            "username": "testuser1",
            "email": "test@example1.com",
            "password": "secret",
        },
    )
    assert r.status_code == 200

    r = client.post("/api/token", data={"username": "testuser", "password": "secret"})
    assert r.status_code == 200
    assert "access_token" in r.json()
