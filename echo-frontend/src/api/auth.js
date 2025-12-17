const API =
    import.meta.env.VITE_API_BASE;

export async function login(username, password) {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);

    const res = await fetch(`${API}/api/token`, {
        method: "POST",
        body: form,
    });

    if (!res.ok) throw new Error("Login failed");
    return res.json();
}