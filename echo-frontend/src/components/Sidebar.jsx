import { useState } from "react";
import OnlineUsersModal from "./OnlineUsersModal";
import ProfileModal from "./ProfileModal";
import NewGroupModal from "./NewGroupModal";
import "../components/sidebar.css";

export default function Sidebar({ open, chats, activeChat, onSelectChat, me, openPersonalChat }) {
  const [search, setSearch] = useState("");
  const filteredChats = chats.filter(chat =>
    chat.name.toLowerCase().includes(search.toLowerCase())
  );
  const sortedChats = [...filteredChats].sort(
  (a, b) =>
    new Date(b.last_message_at || 0) -
    new Date(a.last_message_at || 0)
  );
  const [showOnline, setShowOnline] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [showNewGroup, setShowNewGroup] = useState(false);
  

  return (
    <>
    <aside className={`sidebar ${open ? "open" : ""}`}>
      
  {/* TOP */}
      <div className="sidebar-header ">Echo</div>

      <input
        className="chat-search"
        placeholder="Search chats"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

  {/* CHAT LIST */}
      <div className="chat-list">
        {sortedChats.map((chat) => (
          <div
            key={chat.thread_id}
            className={`chat-item ${
              activeChat?.thread_id === chat.thread_id ? "active" : ""
            }`}
            onClick={() => onSelectChat(chat)}
          >
            <span className="chat-name">{chat.name}</span>

            {chat.unread_count > 0 && (
              <span className="unread-badge">
                {chat.unread_count}
              </span>
            )}
          </div>
        ))}

        <div
          className="chat-item new-group"
          onClick={() => setShowNewGroup(true)}
        >
          + New Group
        </div>
      </div>

      {/* ONLINE */}
      <div className="sidebar-online">
        <button className="online-btn" onClick={() => setShowOnline(true)}>
          Who’s Online
          </button>
      </div>

      {/* PROFILE */}
      <div className="sidebar-footer">
        <div
          className="profile"
          onClick={() => setShowProfile(true)}
        >
          <span>{me?.username}</span>
        </div>
      </div>
    </aside>
    {/* ✅ MODAL GOES HERE */}
    {showOnline && (
      <OnlineUsersModal 
      onClose={() => setShowOnline(false)}
      onSelectUser={openPersonalChat}
      />
    )}
    {showProfile && (
      <ProfileModal
        me={me}
        onClose={() => setShowProfile(false)}
        onLogout={() => {
          localStorage.removeItem("token");
          window.location.href = "/login";
        }}
      />
    )}
    {showNewGroup && (
      <NewGroupModal
        onClose={() => setShowNewGroup(false)}
        onCreated={(thread) => {
          // add new chat immediately
          onSelectChat(thread);
        }}
      />
    )}
    </>
  );
}
