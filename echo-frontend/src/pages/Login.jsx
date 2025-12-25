import { useState } from "react";
import { API_BASE, WS_BASE } from "../config";
import { useNavigate, Link } from "react-router-dom";
import "./auth.css";

console.log(import.meta.env.VITE_API_BASE);

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);

    const res = await fetch(`${API_BASE}/api/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });

    if (!res.ok) {
      setError("Invalid username or password");
      return;
    }

    const data = await res.json();
    localStorage.setItem("token", data.access_token);
    navigate("/");
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="auth-title">Echo Login</div>

        {error && <div className="auth-error">{error}</div>}

        <input
          className="auth-input"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />

        <input
          className="auth-input"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button className="auth-btn" type="submit">
          Login
        </button>

        <div className="auth-switch">
          Don’t have an account? <Link to="/register">Sign up</Link>
        </div>
      </form>
    </div>
  );
}