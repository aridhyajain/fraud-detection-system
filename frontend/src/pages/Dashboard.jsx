import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import TransactionTable from "../components/TransactionTable";
import CreateUserModal from "../components/CreateUserModal";

export default function Dashboard() {
  const navigate = useNavigate();
  const [transactions, setTransactions] = useState([]);
  const [stats, setStats] = useState({ total_transactions_today: 0, total_blocked_today: 0, total_pending_otp: 0, fraud_rate_percentage: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      const [txRes, statsRes] = await Promise.all([
        fetch("/api/v1/transactions/", { headers: { Authorization: `Bearer ${token}` } }),
        fetch("/api/v1/admin/stats", { headers: { Authorization: `Bearer ${token}` } })
      ]);
      
      if (txRes.status === 401 || statsRes.status === 401) {
        localStorage.removeItem("access_token");
        navigate("/login", { replace: true });
        return;
      }
      
      if (!txRes.ok) throw new Error("Failed to fetch transactions");
      if (!statsRes.ok) throw new Error("Failed to fetch stats");
      
      const txData = await txRes.json();
      const statsData = await statsRes.json();
      
      // Sort by timestamp descending
      txData.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setTransactions(txData);
      setStats(statsData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      navigate("/login", { replace: true });
    } else {
      fetchData();
    }
  }, [navigate]);

  const handleActionComplete = () => {
    fetchData();
  };

  const isHighRisk = (t) => t.risk_tier === "HIGH" || t.risk_score >= 71 || t.isFlaggedFraud;
  const isPendingOtp = (t) => t.status === "pending_otp";

  return (
    <div className="dashboard-container" style={{ padding: "2rem", minHeight: "100vh" }}>
      <header className="dashboard-header" style={{ marginBottom: "2rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: "2.5rem", fontWeight: "800", background: "var(--gradient-primary)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Fraud Detection Center
          </h1>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>
            Real-time monitoring and threat mitigation
          </p>
        </div>
        <div style={{ display: "flex", gap: "1rem" }}>
          <button 
            onClick={() => navigate("/users")}
            style={{
              padding: "0.75rem 1.5rem",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-subtle)",
              background: "var(--bg-card)",
              color: "var(--text-primary)",
              fontWeight: "600",
              cursor: "pointer",
              transition: "all 0.2s"
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.borderColor = "var(--accent-indigo)";
              e.currentTarget.style.color = "var(--accent-indigo)";
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.borderColor = "var(--border-subtle)";
              e.currentTarget.style.color = "var(--text-primary)";
            }}
          >
            Users
          </button>
          <button 
            onClick={() => setIsModalOpen(true)}
            style={{
              padding: "0.75rem 1.5rem",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "var(--accent-indigo)",
              color: "white",
              fontWeight: "600",
              cursor: "pointer",
              transition: "all 0.2s"
            }}
            onMouseOver={(e) => e.currentTarget.style.opacity = 0.9}
            onMouseOut={(e) => e.currentTarget.style.opacity = 1}
          >
            Add User
          </button>
          <button 
            onClick={() => {
              localStorage.removeItem("access_token");
              navigate("/login");
            }}
            style={{
              padding: "0.75rem 1.5rem",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-subtle)",
              background: "var(--bg-card)",
              color: "var(--text-primary)",
              cursor: "pointer",
              transition: "all 0.2s"
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.borderColor = "var(--accent-rose)";
              e.currentTarget.style.color = "var(--accent-rose)";
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.borderColor = "var(--border-subtle)";
              e.currentTarget.style.color = "var(--text-primary)";
            }}
          >
            Logout
          </button>
        </div>
      </header>

      <div className="stats-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1.5rem", marginBottom: "3rem" }}>
        <StatCard title="Total Today" value={stats.total_transactions_today} icon="📊" />
        <StatCard title="Blocked Today" value={stats.total_blocked_today} icon="🚫" highlight={stats.total_blocked_today > 0} />
        <StatCard title="Pending OTP" value={stats.total_pending_otp} icon="⚠️" />
        <StatCard title="Fraud Rate %" value={`${stats.fraud_rate_percentage}%`} icon="📈" />
      </div>

      <div style={{ display: "grid", gap: "2rem", gridTemplateColumns: "1fr" }}>
        {/* Pending OTP Transactions */}
        <div className="table-section" style={{ background: "var(--bg-card)", borderRadius: "var(--radius-xl)", padding: "1.5rem", border: "1px solid var(--border-subtle)", boxShadow: "var(--shadow-lg)" }}>
          <h2 style={{ marginBottom: "1.5rem", fontSize: "1.5rem", fontWeight: "600", color: "var(--accent-amber)" }}>Pending OTP Verification</h2>
          {loading ? (
            <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
              <p>Loading transactions...</p>
            </div>
          ) : (
            <TransactionTable 
              transactions={transactions.filter(isPendingOtp)} 
              onActionComplete={handleActionComplete} 
              isAdmin={true}
            />
          )}
        </div>

        {/* Main Flagged Transactions */}
        <div className="table-section" style={{ background: "var(--bg-card)", borderRadius: "var(--radius-xl)", padding: "1.5rem", border: "1px solid var(--border-subtle)", boxShadow: "var(--shadow-lg)" }}>
          <h2 style={{ marginBottom: "1.5rem", fontSize: "1.5rem", fontWeight: "600", color: "var(--accent-rose)" }}>Flagged Transactions (Action Required)</h2>
          {error && <div style={{ color: "var(--accent-rose)", marginBottom: "1rem" }}>{error}</div>}
          {loading ? (
            <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
              <div className="spinner" style={{ margin: "0 auto", width: "40px", height: "40px", border: "3px solid rgba(99,102,241,0.3)", borderRadius: "50%", borderTopColor: "var(--accent-indigo)", animation: "spin 1s ease-in-out infinite" }} />
              <p style={{ marginTop: "1rem" }}>Loading transactions...</p>
            </div>
          ) : (
            <TransactionTable 
              transactions={transactions.filter(isHighRisk)} 
              onActionComplete={handleActionComplete} 
              isAdmin={true}
            />
          )}
        </div>
      </div>

      <CreateUserModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onUserCreated={() => {}} />
    </div>
  );
}

function StatCard({ title, value, icon, highlight }) {
  return (
    <div style={{
      background: highlight ? "linear-gradient(135deg, rgba(251,113,133,0.1), rgba(17,24,39,0.8))" : "var(--bg-card)",
      border: `1px solid ${highlight ? "rgba(251,113,133,0.3)" : "var(--border-subtle)"}`,
      borderRadius: "var(--radius-lg)",
      padding: "1.5rem",
      display: "flex",
      alignItems: "center",
      boxShadow: highlight ? "0 0 20px rgba(251,113,133,0.15)" : "var(--shadow-md)",
      transition: "transform 0.2s",
      cursor: "default"
    }}
    onMouseOver={(e) => e.currentTarget.style.transform = "translateY(-4px)"}
    onMouseOut={(e) => e.currentTarget.style.transform = "translateY(0)"}
    >
      <div style={{ fontSize: "2.5rem", marginRight: "1rem", opacity: 0.8 }}>{icon}</div>
      <div>
        <h3 style={{ color: "var(--text-secondary)", fontSize: "0.875rem", fontWeight: "500", textTransform: "uppercase", letterSpacing: "0.05em" }}>{title}</h3>
        <div style={{ fontSize: "2rem", fontWeight: "700", color: highlight ? "var(--accent-rose)" : "var(--text-primary)", marginTop: "0.25rem" }}>
          {value}
        </div>
      </div>
    </div>
  );
}
