export function connectChatSocket(token, onMessage) {
    const ws = new WebSocket(`ws://localhost:8000/ws/chat?token=${token}`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        onMessage(data);
    };

    return ws;
}