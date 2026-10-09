import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function UsersPage() {
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchUsers = async () => {
      const token = localStorage.getItem("access_token");
      if (!token) {
        navigate("/login");
        return;
      }
      
      try {
        const res = await fetch("/api/v1/admin/users", {
          headers: { Authorization: `Bearer ${token}` }
        });
        
        if (res.status === 401) {
          localStorage.removeItem("access_token");
          navigate("/login");
          return;
        }
        
        if (!res.ok) throw new Error("Failed to fetch users");
        
        const data = await res.json();
        setUsers(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchUsers();
  }, [navigate]);

  return (
    <div className="dashboard-container" style={{ padding: "2rem", minHeight: "100vh" }}>
      <header style={{ marginBottom: "2rem", display: "flex", alignItems: "center", gap: "1rem" }}>
        <button 
          onClick={() => navigate("/dashboard")}
          style={{
            padding: "0.5rem 1rem",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-subtle)",
            background: "var(--bg-card)",
            color: "var(--text-primary)",
            cursor: "pointer",
            fontWeight: "600",
          }}
        >
          &larr; Back
        </button>
        <h1 style={{ fontSize: "2rem", fontWeight: "800", background: "var(--gradient-primary)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", margin: 0 }}>
          All Users
        </h1>
      </header>
      
      <div style={{ background: "var(--bg-card)", borderRadius: "var(--radius-xl)", padding: "1.5rem", border: "1px solid var(--border-subtle)", boxShadow: "var(--shadow-lg)" }}>
        {error && <div style={{ color: "var(--accent-rose)", marginBottom: "1rem" }}>{error}</div>}
        
        {loading ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>Loading users...</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)" }}>
                  <th style={{ padding: "1rem", fontWeight: "600" }}>Name</th>
                  <th style={{ padding: "1rem", fontWeight: "600" }}>Email</th>
                  <th style={{ padding: "1rem", fontWeight: "600" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
                  <tr key={user.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                    <td style={{ padding: "1rem", color: "var(--text-primary)" }}>{user.name}</td>
                    <td style={{ padding: "1rem", color: "var(--text-secondary)" }}>{user.email}</td>
                    <td style={{ padding: "1rem" }}>
                      <span style={{
                        padding: "0.25rem 0.75rem",
                        borderRadius: "999px",
                        fontSize: "0.875rem",
                        fontWeight: "600",
                        backgroundColor: user.account_frozen ? "rgba(239, 68, 68, 0.1)" : "rgba(16, 185, 129, 0.1)",
                        color: user.account_frozen ? "var(--accent-rose)" : "var(--accent-emerald)"
                      }}>
                        {user.account_frozen ? "Frozen" : "Active"}
                      </span>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan="3" style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>
                      No users found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
