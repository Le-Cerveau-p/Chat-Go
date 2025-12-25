import { useEffect, useState } from "react";
import { API_BASE, WS_BASE } from "../config";

export default function OnlineUsersModal({ onClose, onSelectUser }) {
  const [users, setUsers] = useState([]);
  const token = localStorage.getItem("token");

  useEffect(() => {
    async function loadOnline() {
      const res = await fetch(`${API_BASE}/api/online-users`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) return;
      setUsers(await res.json());
    }

    loadOnline();
  }, [token]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Online Users</h3>

        <div className="online-list">
          {users.length === 0 && <p>No one online</p>}

          {users.map((u) => (
            <div key={u.id} 
            className="online-user clickable"
            onClick={() => {
                onSelectUser(u);
                onClose();
              }}>
              <span className="status-dot" />
              {u.username}
            </div>
          ))}
        </div>

        <button className="close-btn" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}