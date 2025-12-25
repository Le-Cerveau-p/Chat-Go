import { useEffect, useRef, useState } from "react";
import { API_BASE, WS_BASE } from "../config";
import { connectChatSocket } from "../ws/chatSocket";
import "../components/chat.css";
import { truncate, formatFileSize, isImage } from "./File"

export default function ChatView({ threadId, onRead }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [typingUsers, setTypingUsers] = useState({});
  const [me, setMe] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploads, setUploads] = useState([]);
  const [showInfo, setShowInfo] = useState(false);

  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);
  const dragCounter = useRef(0);
  const fileInputRef = useRef(null);

  const token = localStorage.getItem("token");


  /* ---------------- EFFECTS ---------------- */
  useEffect(() => {
    const beforeUnload = () => {
      console.log("PAGE IS RELOADING");
    };

    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, []);

  useEffect(() => {
    if (!threadId) return;

    async function loadMe() {
      const res = await fetch(`${API_BASE}/api/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setMe(await res.json());
    }

    

    async function loadHistory() {
      const res = await fetch(
        `${API_BASE}/api/threads/${threadId}/messages`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setMessages(await res.json());
    }

    loadMe();
    loadHistory();

    const ws = connectChatSocket(token, (data) => {
      if (data.type === "message" || data.type === "file" || data.system) {
        setMessages((prev) => [...prev, data]);
      }

      if (data.type === "read") {
        setMessages((prev) =>
          prev.map((m) =>
            m.sender === me?.username
              ? { ...m, read_count: (m.read_count || 0) + 1 }
              : m
          )
        );
      }

      if (data.type === "typing") {
        setTypingUsers((prev) => {
          const next = { ...prev };
          if (data.is_typing) {
            next[data.user_id] = data.username;
          } else {
            delete next[data.user_id];
          }
          return next;
        });
      }
    });

    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ action: "join", thread_id: threadId }));
    };

    return () => ws.close();
  }, [threadId, token]);

  useEffect(() => {
    if (!threadId) return;

    // Tell backend
    fetch(`${API_BASE}/api/threads/${threadId}/read`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });

    // Tell Layout (local UI update)
    onRead?.(threadId);
  }, [threadId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* ---------------- ACTIONS ---------------- */

  const sendMessage = () => {
    if (!text.trim()) return;
    wsRef.current?.send(
      JSON.stringify({
        action: "message",
        thread_id: threadId,
        content: text,
      })
    );
    setText("");
  };

  const startUpload = (file) => {
    const id = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const xhr = new XMLHttpRequest();
  
    const uploadItem = {
      id,
      file,
      progress: 0,
      xhr,
    };
  
    setUploads((prev) => [...prev, uploadItem]);
  
    const formData = new FormData();
    formData.append("file", file);
  
    xhr.open(
      "POST",
      `${API_BASE}/api/threads/${ threadId }/upload`
    );
  
    xhr.setRequestHeader(
      "Authorization",
      `Bearer ${token}`
    );
  
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
  
      const percent = Math.round(
        (e.loaded / e.total) * 100
      );
  
      setUploads((prev) =>
        prev.map((u) =>
          u.id === id ? { ...u, progress: percent } : u
        )
      );
    };
  
    xhr.onload = () => {
      setUploads((prev) => prev.filter((u) => u.id !== id));
    };
  
    xhr.onerror = () => {
      setUploads((prev) => prev.filter((u) => u.id !== id));
      alert(`Upload failed: ${file.name}`);
    };
  
    xhr.send(formData);
  };
  

  const cancelUpload = (id) => {
    setUploads((prev) => {
      const target = prev.find((u) => u.id === id);
      if (target) target.xhr.abort();
      return prev.filter((u) => u.id !== id);
    });
  };
  const onDragEnter = (e) => {
    e.preventDefault();
    dragCounter.current += 1;
    setDragActive(true);
  };
  
  const onDragLeave = (e) => {
    e.preventDefault();
    dragCounter.current -= 1;
  
    if (dragCounter.current === 0) {
      setDragActive(false);
    }
  };
  
  const onDragOver = (e) => {
    e.preventDefault();
  };
  
  const onDrop = (e) => {
    e.preventDefault();
  
    dragCounter.current = 0;
    setDragActive(false);
  
    Array.from(e.dataTransfer.files).forEach(startUpload);
  };
  
  
  
  

  const downloadFile = async (url, filename) => {
    const res = await fetch(`${API_BASE}${url}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  
    if (!res.ok) {
      alert("Download failed");
      return;
    }
  
    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
  
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
  
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
  };
  

  /* ---------------- UI ---------------- */

  return (
    <div className="chat-container" 
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}>
        {dragActive && (
          <div className="drag-overlay">Drop files to upload</div>
        )}
      {/* <h2 className="thread-title">{displayName}</h2> */}

      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={m.system ? "system" : `message ${m.sender === me?.username ? "me" : "other"}`}>
            {!m.system && (
              <>
                <span className="sender">{m.sender}</span>
                {m.type === "file" ? (
                  <div className="file-message">
                    {isImage(m.filename) ? (
                      <img
                        src={`${API_BASE}${m.file_url}/preview`}
                        className="image-preview"
                        onClick={() => downloadFile(m.file_url, m.filename)}
                      />
                    ) : (
                      <span
                        className="file-link"
                        onClick={() => downloadFile(m.file_url, m.filename)}
                        title={m.filename}
                      >
                        {truncate(m.filename)}
                      </span>
                    )}

                    <div className="file-meta">
                      {formatFileSize(m.file_size)}
                    </div>
                  </div>
                ) : (
                  <span className="content">{m.content}</span>
                )}

                {m.sender === me?.username && (
                  <span className="receipt">
                    {m.read_count > 0 ? "✓✓" : "✓"}
                  </span>
                )}
              </>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      {Object.values(typingUsers)
        .filter((username) => username !== me?.username).length > 0 && (
          <div className="typing-indicator">
            {Object.values(typingUsers)
              .filter((username) => username !== me?.username)
              .join(", ")}{" "}
            typing...
          </div>
      )}

      {uploads.length > 0 && (
        <div className="upload-list">
          {uploads.map((u) => (
            <div key={u.id} className="upload-item">
              <span>{truncate(u.file.name)}</span>
              <div className="upload-bar">
                <div
                  className="upload-bar-fill"
                  style={{ width: `${u.progress}%` }}
                />
              </div>
              <button onClick={() => cancelUpload(u.id)}>✕</button>
            </div>
          ))}
        </div>
      )}

      <div className="input-bar">
        <input
          value={text}
          onChange={(e) => {setText(e.target.value); 
            wsRef.current?.send(
              JSON.stringify({
                action: "typing_start",
                thread_id: threadId,
              })
            );
          }}
          onBlur={() =>
            wsRef.current?.send(
              JSON.stringify({
                action: "typing_stop",
                thread_id: threadId,
              })
            )
          }

          placeholder="Type a message..."
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
        />
        <input
          type="file"
          ref={fileInputRef}
          multiple
          hidden
          onChange={(e) => {
            Array.from(e.target.files).forEach(startUpload);
            e.target.value = "";
          }}
        />

        <button type="button" onClick={() => fileInputRef.current.click()}>
          📎
        </button>
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
}
