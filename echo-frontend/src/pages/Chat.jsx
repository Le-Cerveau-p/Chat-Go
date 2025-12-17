import { useEffect, useRef, useState } from "react";
import { connectChatSocket } from "../ws/chatSocket";
import "../components/chat.css";

export const truncate = (text, max = 20) => {
  if (!text) return "";
  return text.length > max ? text.slice(0, max) + "..." : text;
};

export const formatFileSize = (bytes) => {
  if (!bytes) return "";
  const sizes = ["B", "KB", "MB", "GB"];
  let i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(1) + " " + sizes[i];
};

export const isImage = (filename) =>
  /\.(jpg|jpeg|png|gif|webp)$/i.test(filename);


export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [typingUsers, setTypingUsers] = useState({});
  const [readReceipts, setReadReceipts] = useState({});
  const [me, setMe] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const dragCounter = useRef(0);
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);
  let typingTimeout = useRef(null);
  const fileInputRef = useRef(null);

  const token = localStorage.getItem("token");const [uploads, setUploads] = useState([]);
  /*
  uploads = [
    {
      id,
      file,
      progress,
      xhr
    }
  ]
  */


  useEffect(() => {
    async function loadMe() {
      const res = await fetch("http://localhost:8000/api/me", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
  
      const data = await res.json();
      setMe(data);
    }
  
    loadMe();

    async function loadHistory() {
      const res = await fetch(
        "http://localhost:8000/api/threads/1/messages",
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      const data = await res.json();
      setMessages(data);

      await fetch("http://localhost:8000/api/threads/1/read", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    }
  
    loadHistory();
    fetch("http://localhost:8000/api/threads/1/read", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    

    const ws = connectChatSocket(token, (data) => {
      if (data.type === "message" || data.type === "file" || data.system) {
        setMessages((m) => [...m, data]);
      }

      if (data.type === "read") {
        setMessages((prev) =>
          prev.map((m) => {
            // Only update messages I sent
            if (m.sender === me?.username) {
              return {
                ...m,
                read_count: (m.read_count || 0) + 1,
              };
            }
            return m;
          })
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
      ws.send(JSON.stringify({ action: "join", thread_id: 1 }));
    };

    return () => ws.close();
  }, [token]);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  

  const sendMessage = () => {
    if (!text.trim() || !wsRef.current) return;

    wsRef.current.send(
      JSON.stringify({
        action: "message",
        thread_id: 1,
        content: text,
      })
    );

    setText("");
  };


  const startUpload = (file) => {
    const id = crypto.randomUUID();
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
      "http://localhost:8000/api/threads/1/upload"
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
    const res = await fetch(`http://localhost:8000${url}`, {
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
  
  

  return (
    <div className="chat-container" 
    onDragEnter={onDragEnter}
    onDragLeave={onDragLeave}
    onDragOver={onDragOver}
    onDrop={onDrop}>
      {dragActive && (<div className="drag-overlay">Drop files to upload</div>)}

      <h2 className="thread-title">Thread 1</h2>

      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={m.system ? "system" : "message"}>
          {!m.system && (
            <>
              <span className="sender">{m.sender}</span>

              {m.type === "file" ? (
                <div className="file-message">
                  <span className="file-icon">📎</span>

                  {isImage(m.filename) ? (
                    <img
                      src={`http://localhost:8000${m.file_url}/preview`}
                      alt={m.filename}
                      className="image-preview"
                      onClick={() => downloadFile(m.file_url, m.filename)}
                    />
                  ) : (
                    <span
                      className="file-link"
                      onClick={() => downloadFile(m.file_url, m.filename)}
                      title={m.filename}
                    >
                      {truncate(m.filename, 20)}
                    </span>
                  )}

                  <div className="file-meta">
                    <span className="file-size">
                      {formatFileSize(m.file_size)}
                    </span>
                  </div>
                </div>
              ) : (
                <span className="content">{m.content}</span>
              )}
        
              {m.sender === me?.username && (
                <span className="receipt">
                  {m.read_count > 0 ? "✓✓" : m.delivered_count > 0 ? "✓" : ""}
                </span>
              )}
            </>
          )}
          </div>
        
        ))}
        <div ref={messagesEndRef} />

      </div>
      {Object.values(typingUsers).length > 0 && (
      <div className="typing-indicator">
        {Object.values(typingUsers).join(", ")} typing...
      </div>
      )}

      {uploads.length > 0 && (
        <div className="upload-list">
          {uploads.map((u) => (
            <div key={u.id} className="upload-item">
              <span className="upload-name">
                {truncate(u.file.name, 20)}
              </span>

              <div className="upload-bar">
                <div
                  className="upload-bar-fill"
                  style={{ width: `${u.progress}%` }}
                />
              </div>

              <span className="upload-percent">
                {u.progress}%
              </span>

              <button
                className="upload-cancel"
                onClick={() => cancelUpload(u.id)}
              >
                ✕
              </button>
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
                thread_id: 1,
              })
            );
          }}
          onBlur={() =>
            wsRef.current?.send(
              JSON.stringify({
                action: "typing_stop",
                thread_id: 1,
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
          style={{ display: "none" }}
          onChange={(e) => {
            Array.from(e.target.files).forEach(startUpload);
            e.target.value = "";
          }}
        />

        <button onClick={() => fileInputRef.current.click()}>
          📎
        </button>

        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
}
