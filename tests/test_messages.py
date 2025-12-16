def test_send_message(client):
    r = client.post("/api/token", data={"username": "testuser", "password": "secret"})
    token = r.json()["access_token"]

    # create thread
    r = client.post(
        "/api/threads",
        json={"name": "Msg Thread", "is_group": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    thread_id = r.json()["id"]

    # send message
    r = client.post(
        "/api/messages",
        json={"thread_id": thread_id, "content": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200
    assert r.json()["content"] == "hello"
