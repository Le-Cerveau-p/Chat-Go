export default function ProfileModal({ me, onClose, onLogout }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Profile</h3>

        <div className="profile-info">
          <div><strong>Username:</strong> {me?.username}</div>
          <div><strong>ID:</strong> {me?.id}</div>
        </div>

        <div className="modal-footer">
          <button className="logout-btn" onClick={onLogout}>
            Logout
          </button>
        </div>
      </div>
    </div>
  );
}