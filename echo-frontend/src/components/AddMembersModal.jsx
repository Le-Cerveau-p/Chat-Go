import { useState } from "react";
import { API_BASE, WS_BASE } from "../config";

export default function AddMembersModal({
  threadId,
  members,
  onlineUsers,
  onClose,
  onAdded,
}) {
  const [selected, setSelected] = useState([]);
  const token = localStorage.getItem("token");

  const eligibleUsers = onlineUsers.filter(
    (u) => !members.some((m) => m.user_id === u.id)
  );

  const toggle = (id) => {
    setSelected((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : [...prev, id]
    );
  };

  const addMembers = async () => {
    for (const userId of selected) {
      await fetch(
        `${API_BASE}/api/threads/${threadId}/members`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_id: userId,
            is_admin: false,
          }),
        }
      );
    }

    onAdded();
  };

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h3>Add Members</h3>

        {eligibleUsers.map((u) => (
          <label key={u.id}>
            <input
                className="check-box"
              type="checkbox"
              checked={selected.includes(u.id)}
              onChange={() => toggle(u.id)}
            />
            {u.username}
          </label>
        ))}

        <div>
          <button onClick={onClose}>Cancel</button>
          <button disabled={!selected.length} onClick={addMembers}>
            Add
          </button>
        </div>
      </div>
    </div>
  );
}