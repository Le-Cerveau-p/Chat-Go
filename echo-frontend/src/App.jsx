import { useState } from "react";
import Login from "./pages/Login";
import Chat from "./pages/Chat";

function App() {
  const [token, setToken] = useState(
    localStorage.getItem("token")
  );

  if (!token) {
    return <Login onLogin={setToken} />;
  }

  return <Chat token={token} />;
}

export default App;
