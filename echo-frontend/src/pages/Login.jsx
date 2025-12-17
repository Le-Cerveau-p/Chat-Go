import { useState } from "react";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);

    const res = await fetch("http://localhost:8000/api/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: form,
    });

    if (!res.ok) {
      setError("Invalid credentials");
      return;
    }

    const data = await res.json();

    // 🔑 STORE TOKEN
    localStorage.setItem("token", data.access_token);

    // 🔁 Notify App
    onLogin(data.access_token);
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Login</h2>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <input
        placeholder="Username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />

      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      <button type="submit">Login</button>
    </form>
  );
}
