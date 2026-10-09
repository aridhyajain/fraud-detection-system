import React, { useState } from "react";

export default function CreateUserModal({ isOpen, onClose, onUserCreated }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch("/api/v1/admin/users/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ name, email, password, role: "user" })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to create user");
      
      onUserCreated(data);
      onClose();
      // Reset form
      setName(""); setEmail(""); setPassword("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: "rgba(0,0,0,0.7)", zIndex: 1000,
      display: "flex", alignItems: "center", justifyContent: "center"
    }}>
      <div style={{
        background: "var(--bg-card)",
        padding: "2rem",
        borderRadius: "var(--radius-xl)",
        width: "100%",
        maxWidth: "400px",
        border: "1px solid var(--border-subtle)",
        boxShadow: "var(--shadow-lg)"
      }}>
        <h2 style={{ marginBottom: "1.5rem", fontSize: "1.5rem", color: "var(--text-primary)" }}>Create New User</h2>
        {error && <div style={{ color: "var(--accent-rose)", marginBottom: "1rem" }}>{error}</div>}
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div>
            <label style={{ display: "block", marginBottom: "0.5rem", color: "var(--text-secondary)" }}>Name</label>
            <input type="text" required value={name} onChange={e => setName(e.target.value)}
              style={{ width: "100%", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)", background: "rgba(255,255,255,0.05)", color: "var(--text-primary)" }} />
          </div>
          <div>
            <label style={{ display: "block", marginBottom: "0.5rem", color: "var(--text-secondary)" }}>Email</label>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
              style={{ width: "100%", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)", background: "rgba(255,255,255,0.05)", color: "var(--text-primary)" }} />
          </div>
          <div>
            <label style={{ display: "block", marginBottom: "0.5rem", color: "var(--text-secondary)" }}>Password</label>
            <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
              style={{ width: "100%", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)", background: "rgba(255,255,255,0.05)", color: "var(--text-primary)" }} />
          </div>
          <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
            <button type="button" onClick={onClose} style={{ flex: 1, padding: "0.75rem", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", background: "transparent", color: "var(--text-primary)", cursor: "pointer" }}>Cancel</button>
            <button type="submit" disabled={loading} style={{ flex: 1, padding: "0.75rem", borderRadius: "var(--radius-md)", border: "none", background: "var(--accent-indigo)", color: "white", fontWeight: "600", cursor: "pointer" }}>
              {loading ? "Creating..." : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
