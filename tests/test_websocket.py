def test_websocket_chat_flow(client):
    # login
    r = client.post("/api/token", data={"username": "testuser", "password": "secret"})
    token = r.json()["access_token"]

    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        # join thread
        ws.send_json({"action": "join", "thread_id": 1})

        joined = False

        for _ in range(3):
            data = ws.receive_json()
            if "message" in data and "joined" in data["message"]:
                joined = True
                break

        assert joined
