import { useEffect,useState, useCallback } from "react";
import Sidebar from "../components/Sidebar";
import ChatView from "../components/ChatView";
import ChatPlaceholder from "../components/ChatPlaceholder";
import ThreadInfoModal from "../components/ThreadInfoModal";
import "./layout.css";

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeChat, setActiveChat] = useState(null);
  const [chats, setChats] = useState([]);
  const [showThreadInfo, setShowThreadInfo] = useState(false);
  
  const [me, setMe] = useState(null);

  const token = localStorage.getItem("token");

  const markThreadRead = (threadId) => {
    setChats(prev =>
      prev.map(chat =>
        chat.id === threadId
          ? { ...chat, unread_count: 0 }
          : chat
      )
    );
  };

  const updateSidebarFromMessage = (data) => {
    console.log("sidebar update");

    setChats(prev => {
      const updated = prev.map(chat => {
        if (chat.id !== data.thread_id) return chat;

        const isActive = activeChat?.id === chat.id;

        return {
          ...chat,
          last_message: data.content || "📎 File",
          last_message_at: data.created_at,
          unread_count: isActive
            ? 0
            : (chat.unread_count || 0) + 1,
        };
      });

      return updated.sort(
        (a, b) =>
          new Date(b.last_message_at || 0) -
          new Date(a.last_message_at || 0)
      );
    });
  };

  const handleIncomingMessage = (data) => {
    setChats(prev => {
      const updated = prev.map(chat => {
        if (chat.thread_id !== data.thread_id) return chat;

        const isActive = activeChat?.thread_id === chat.thread_id;

        return {
          ...chat,
          last_message: data.content || "📎 File",
          last_message_time: data.created_at,
          unread_count: isActive
            ? 0
            : (chat.unread_count || 0) + 1,
        };
      });
      console.log('rann')

      // move updated chat to top
      return updated.sort(
        (a, b) => 
          new Date(b.last_message_time || 0) - new Date(a.last_message_time || 0)
      );
    });
  };

  useEffect(() => {
    async function loadMe() {
      const res = await fetch("http://localhost:8000/api/me", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) return;

      const data = await res.json();
      setMe(data);
    }

    loadMe();
  }, [token]);

  const openPersonalChat = async (user) => {
    // 1. check if personal thread exists
    const res = await fetch(
      `http://localhost:8000/api/threads/personal/${user.id}`,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );

    let thread = await res.json();

    // 2. if not, create it
    if (!thread) {
      const createRes = await fetch("http://localhost:8000/api/threads", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: user.username,
          is_group: false,
        }),
      });

      thread = await createRes.json();

      // add the other user
      await fetch(
        `http://localhost:8000/api/threads/${thread.id}/members`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            user_id: user.id,
            is_admin: false,
          }),
        }
      );

      // update sidebar
      setChats((prev) => [...prev, thread]);
    }

    setActiveChat(thread);
    setSidebarOpen(false);
  };

  useEffect(() => {
    async function loadChats() {
      const res = await fetch("http://localhost:8000/api/chats", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) return;

      const data = await res.json();
      setChats(data);
    }

    loadChats();
  }, [token]);

  
  const refreshChats = useCallback(async () => {
    const res = await fetch("http://localhost:8000/api/chats", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!res.ok) return;

    const data = await res.json();
    setChats(data);
  }, [token]);

  useEffect(() => {
    if (!token) return;

    const ws = new WebSocket(
      `ws://localhost:8000/ws/chat?token=${token}`
    );

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "message" || data.type === "file") {
        handleIncomingMessage(data);
      }

      if (data.type === "thread_added") {
        refreshChats();
      }
    };

    return () => ws.close();
  }, [token, refreshChats]);

  
  const selectChat = (chat) => {
    setActiveChat(chat);
    setChats(prev =>
      prev.map(c =>
        c.thread_id === chat.thread_id ? { ...c, unread_count: 0 } : c
      )
    );
    setSidebarOpen(false); // important for mobile
  };

  

  return (
    <div className="app-shell">
      <Sidebar
        open={sidebarOpen}
        chats={chats}
        activeChat={activeChat}
        onSelectChat={selectChat}
        onClose={() => setSidebarOpen(false)}
        me={me}
        openPersonalChat={openPersonalChat}
      />

      <div className="main-content">
        <div className="top-bar">
          <button
            className="hamburger"
            onClick={() => setSidebarOpen(true)}
          >
            ☰
          </button>
          <span
            className="top-bar-title"
            onClick={() => {
              if (activeChat) setShowThreadInfo(true);
            }}
          >{activeChat ? activeChat.name : "Echo"}</span>
        </div>

        <div className="page-content" onClick={() => setSidebarOpen(false)}>
          {activeChat ? (
            <ChatView 
            threadId={activeChat.thread_id} 
            onRead={markThreadRead} />
          ) : (
            <ChatPlaceholder />
          )}
        </div>
      </div>
      {showThreadInfo && activeChat && (
        <ThreadInfoModal
          threadId={activeChat.thread_id ?? activeChat.id}
          me={me}
          onClose={() => setShowThreadInfo(false)}
        />
      )}
    </div>
  );
}
