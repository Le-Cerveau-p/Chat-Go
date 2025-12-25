import { API_BASE, WS_BASE } from "../config";
export function connectChatSocket(token, onMessage) {
    const ws = new WebSocket(`${WS_BASE}/ws/chat?token=${token}`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        onMessage(data);
    };

    return ws;
}