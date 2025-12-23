export default function TopBar({ onMenuClick }) {
  return (
    <div className="topbar">
      <button className="menu-btn" onClick={onMenuClick}>
        ☰
      </button>

      <div className="topbar-title">Chat</div>
    </div>
  );
}
