import { useEffect, useState } from "react";
import "../components/newgroup.css";

export default function NewGroupModal({ onClose, onCreated }) {
  const [name, setName] = useState("");
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [selected, setSelected] = useState([]);

  const token = localStorage.getItem("token");

  useEffect(() => {
    fetch("http://localhost:8000/api/online-users", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((r) => r.json())
      .then(setOnlineUsers);
  }, [token]);

  const toggleUser = (user) => {
    setSelected((prev) =>
      prev.some((u) => u.id === user.id)
        ? prev.filter((u) => u.id !== user.id)
        : [...prev, user]
    );
  };

  const createGroup = async () => {
    if (!name.trim()) {
      alert("Group name required");
      return;
    }

    // 1️⃣ Create thread
    const res = await fetch("http://localhost:8000/api/threads", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name,
        is_group: true,
      }),
    });

    if (!res.ok) {
      alert("Failed to create group");
      return;
    }

    const thread = await res.json();

    // 2️⃣ Add members
    for (const user of selected) {
      await fetch(
        `http://localhost:8000/api/threads/${thread.id}/members`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_id: user.id,
            is_admin: false,
          }),
        }
      );
    }

    // 3️⃣ Update UI
    onCreated(thread);
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Group</h3>

        <input
          className="modal-input"
          placeholder="Group name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <div className="user-list">
          {onlineUsers.map((u) => (
            <div
              key={u.id}
              className={`user-item ${
                selected.some((s) => s.id === u.id) ? "selected" : ""
              }`}
              onClick={() => toggleUser(u)}
            >
              {u.username}
            </div>
          ))}
        </div>

        <div className="modal-footer">
          <button onClick={() => {createGroup(); onClose()}}>Create</button>
        </div>
      </div>
    </div>
  );
}