import { useEffect, useState } from "react";
import AddMembersModal from "./AddMembersModal";

export default function ThreadInfoModal({ threadId, onClose, me }) {
  const [thread, setThread] = useState(null);
  const [members, setMembers] = useState([]);
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [showAdd, setShowAdd] = useState(false);

  const token = localStorage.getItem("token");

  const isAdmin = members.some(
    (m) => m.user_id === me?.id && m.is_admin
  );

  async function refreshMembers() {
    const res = await fetch(
      `http://localhost:8000/api/threads/${threadId}/members`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (res.ok) setMembers(await res.json());
  }

  async function promote(userId) {
    await fetch(
      `http://localhost:8000/api/threads/${threadId}/promote`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ user_id: userId }),
      }
    );
    refreshMembers();
  }

  async function demote(userId) {
    await fetch(
      `http://localhost:8000/api/threads/${threadId}/demote`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ user_id: userId }),
      }
    );
    refreshMembers();
  }

  async function remove(userId) {
    await fetch(
      `http://localhost:8000/api/threads/${threadId}/remove`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ user_id: userId }),
      }
    );
    refreshMembers();
  }

  useEffect(() => {
    async function load() {
      const [t, m, o] = await Promise.all([
        fetch(`http://localhost:8000/api/threads/${threadId}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`http://localhost:8000/api/threads/${threadId}/members`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`http://localhost:8000/api/online-users`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (t.ok) setThread(await t.json());
      if (m.ok) setMembers(await m.json());
      if (o.ok) setOnlineUsers(await o.json());
    }

    load();
  }, [threadId, token]);

  console.log({
    threadIsGroup: thread?.is_group,
    isAdmin,
    meId: me?.id,
    members,
  });

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h3>Thread Info</h3>

        <h4>Members</h4>
        {members.map((m) => (
          <div key={m.user_id} className="member-row">
            <span>
              {m.username}
              {m.is_admin && <span className="admin-badge"> (admin)</span>}
            </span>

            {thread?.is_group && isAdmin && m.user_id !== me.id && (
              <div className="actions">
                {!m.is_admin && (
                  <button onClick={() => promote(m.user_id)}>Promote</button>
                )}
                {m.is_admin && (
                  <button onClick={() => demote(m.user_id)}>Demote</button>
                )}
                <button className="danger" onClick={() => remove(m.user_id)}>
                  Remove
                </button>
              </div>
            )}
          </div>
        ))}

        {isAdmin && (
          <button onClick={() => setShowAdd(true)}>Add Members</button>
        )}

        {thread?.is_group && (
          <button
            className="danger full"
            onClick={async () => {
              await fetch(
                `http://localhost:8000/api/threads/${threadId}/leave`,
                {
                  method: "POST",
                  headers: { Authorization: `Bearer ${token}` },
                }
              );
              onClose();
            }}
          >
            Leave group
          </button>
        )}

        <button onClick={onClose}>Close</button>

        {showAdd && (
          <AddMembersModal
            threadId={threadId}
            members={members}
            onlineUsers={onlineUsers}
            onClose={() => setShowAdd(false)}
            onAdded={refreshMembers}
          />
        )}
      </div>
    </div>
  );
}