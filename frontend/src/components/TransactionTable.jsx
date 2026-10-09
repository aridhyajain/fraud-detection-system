import React, { useState } from "react";
import RiskBadge from "./RiskBadge";

export default function TransactionTable({ transactions, onActionComplete, hideRiskScore = false, isAdmin = false }) {
  const [processingId, setProcessingId] = useState(null);

  const handleAction = async (id, action) => {
    setProcessingId(id);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`/api/v1/transactions/${id}/${action}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) throw new Error("Action failed");
      if (onActionComplete) onActionComplete();
    } catch (err) {
      console.error(err);
      alert("Failed to perform action");
    } finally {
      setProcessingId(null);
    }
  };

  if (!transactions || transactions.length === 0) {
    return <div style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>No transactions found.</div>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", whiteSpace: "nowrap" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", fontSize: "0.875rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            <th style={{ padding: "1rem" }}>ID</th>
            <th style={{ padding: "1rem" }}>Amount</th>
            <th style={{ padding: "1rem" }}>Sender</th>
            <th style={{ padding: "1rem" }}>Receiver</th>
            <th style={{ padding: "1rem" }}>Time</th>
            {!hideRiskScore && <th style={{ padding: "1rem" }}>Risk</th>}
            <th style={{ padding: "1rem", textAlign: "right" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((t) => (
            <tr key={t.id} className="table-row" style={{ borderBottom: "1px solid rgba(75,85,99,0.2)", transition: "background 0.2s" }}
                onMouseOver={(e) => e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.02)"}
                onMouseOut={(e) => e.currentTarget.style.backgroundColor = "transparent"}>
              <td style={{ padding: "1rem" }}>#{t.id}</td>
              <td style={{ padding: "1rem", fontWeight: "600" }}>${t.amount.toFixed(2)}</td>
              <td style={{ padding: "1rem" }}>{t.nameOrig}</td>
              <td style={{ padding: "1rem" }}>{t.nameDest}</td>
              <td style={{ padding: "1rem", color: "var(--text-muted)", fontSize: "0.875rem" }}>
                {new Date(t.timestamp).toLocaleString()}
              </td>
              {!hideRiskScore && (
                <td style={{ padding: "1rem" }}>
                  <RiskBadge score={t.risk_score} tier={t.risk_tier} />
                </td>
              )}
              <td style={{ padding: "1rem", textAlign: "right" }}>
                {(t.risk_tier === "HIGH" || t.risk_score >= 71 || t.isFlaggedFraud === 1) && t.isFraud === 0 ? (
                  <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                    <button
                      onClick={() => handleAction(t.id, "confirm-fraud")}
                      disabled={processingId === t.id}
                      style={{
                        padding: "0.5rem 1rem",
                        borderRadius: "var(--radius-sm)",
                        border: "none",
                        background: "rgba(251, 113, 133, 0.2)",
                        color: "var(--accent-rose)",
                        fontWeight: "600",
                        cursor: processingId === t.id ? "not-allowed" : "pointer",
                        opacity: processingId === t.id ? 0.5 : 1,
                        transition: "all 0.2s"
                      }}
                      onMouseOver={(e) => {
                        if (processingId !== t.id) e.currentTarget.style.background = "rgba(251, 113, 133, 0.3)"
                      }}
                      onMouseOut={(e) => {
                        if (processingId !== t.id) e.currentTarget.style.background = "rgba(251, 113, 133, 0.2)"
                      }}
                    >
                      {processingId === t.id ? "..." : "Confirm Fraud"}
                    </button>
                    <button
                      onClick={() => handleAction(t.id, "false-positive")}
                      disabled={processingId === t.id}
                      style={{
                        padding: "0.5rem 1rem",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        background: "transparent",
                        color: "var(--text-secondary)",
                        fontWeight: "600",
                        cursor: processingId === t.id ? "not-allowed" : "pointer",
                        opacity: processingId === t.id ? 0.5 : 1,
                        transition: "all 0.2s"
                      }}
                      onMouseOver={(e) => {
                        if (processingId !== t.id) e.currentTarget.style.color = "var(--text-primary)"
                      }}
                      onMouseOut={(e) => {
                        if (processingId !== t.id) e.currentTarget.style.color = "var(--text-secondary)"
                      }}
                    >
                      False Positive
                    </button>
                  </div>
                ) : t.isFraud === 1 ? (
                  <span style={{ color: "var(--accent-rose)", fontWeight: "600", fontSize: "0.875rem" }}>Confirmed Fraud</span>
                ) : (t.risk_tier === "Low" && t.risk_score === 0 && t.isFlaggedFraud === 0) ? (
                  <span style={{ color: "var(--accent-emerald)", fontWeight: "600", fontSize: "0.875rem" }}>Cleared</span>
                ) : (isAdmin && t.status === "pending_otp") ? (
                  <button
                    onClick={() => handleAction(t.id, "clear-pending")}
                    disabled={processingId === t.id}
                    style={{
                      padding: "0.5rem 1rem",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border-subtle)",
                      background: "transparent",
                      color: "var(--text-primary)",
                      fontWeight: "600",
                      cursor: processingId === t.id ? "not-allowed" : "pointer",
                      opacity: processingId === t.id ? 0.5 : 1,
                      transition: "all 0.2s"
                    }}
                  >
                    {processingId === t.id ? "..." : "Clear Manually"}
                  </button>
                ) : (
                  <span style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>-</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
