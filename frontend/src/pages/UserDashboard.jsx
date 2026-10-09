import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import TransactionTable from "../components/TransactionTable";

export default function UserDashboard() {
  const navigate = useNavigate();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Form State
  const [amount, setAmount] = useState("");
  const [receiver, setReceiver] = useState("");
  
  const [submitResult, setSubmitResult] = useState(null); // { status: "approved"|"pending_otp"|"blocked"|"frozen", message: "" }
  const [submitLoading, setSubmitLoading] = useState(false);
  const [transactionId, setTransactionId] = useState(null);
  
  // OTP State
  const [otp, setOtp] = useState("");
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpResult, setOtpResult] = useState(null); // { status: "success"|"error", message: "" }

  const fetchMyTransactions = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch("/api/v1/transactions/my", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.status === 401) {
        localStorage.removeItem("access_token");
        navigate("/login", { replace: true });
        return;
      }
      if (!res.ok) throw new Error("Failed to fetch transactions");
      const data = await res.json();
      data.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setTransactions(data);
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
      fetchMyTransactions();
    }
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitLoading(true);
    setSubmitResult(null);
    setOtpResult(null);
    setOtp("");
    
    try {
      const token = localStorage.getItem("access_token");
      const numAmount = parseFloat(amount);
      const payload = {
        step: 1,
        type: "UPI",
        amount: numAmount,
        nameOrig: "CurrentUser", // Dummy or fetch from token if available
        oldbalanceOrg: 50000,
        newbalanceOrig: 50000 - numAmount,
        nameDest: receiver,
        oldbalanceDest: 0,
        newbalanceDest: numAmount,
        isFraud: 0,
        isFlaggedFraud: 0
      };

      const res = await fetch("/api/v1/transactions/submit", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Submission failed");
      
      setSubmitResult({ status: data.status, message: data.message });
      if (data.transaction_id) {
        setTransactionId(data.transaction_id);
      }
      
      if (data.status !== "pending_otp" && data.status !== "blocked" && data.status !== "frozen") {
        setAmount("");
        setReceiver("");
      }
      
      fetchMyTransactions();
    } catch (err) {
      setSubmitResult({ status: "error", message: err.message });
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setOtpLoading(true);
    setOtpResult(null);
    
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch("/api/v1/transactions/verify-otp", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ transaction_id: transactionId, otp }),
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Verification failed");
      
      setOtpResult({ status: "success", message: "Transaction verified successfully!" });
      setSubmitResult(null); // Clear submit result to hide OTP form
      setAmount("");
      setReceiver("");
      fetchMyTransactions();
    } catch (err) {
      setOtpResult({ status: "error", message: err.message });
    } finally {
      setOtpLoading(false);
    }
  };

  return (
    <div className="dashboard-container" style={{ padding: "2rem", minHeight: "100vh" }}>
      <header className="dashboard-header" style={{ marginBottom: "2rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: "2.5rem", fontWeight: "800", background: "var(--gradient-primary)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            My Dashboard
          </h1>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem" }}>
            Send money and view history
          </p>
        </div>
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
      </header>

      <div style={{ display: "grid", gap: "2rem", gridTemplateColumns: "1fr" }}>
        {/* Transaction Form */}
        <div style={{ background: "var(--bg-card)", borderRadius: "var(--radius-xl)", padding: "1.5rem", border: "1px solid var(--border-subtle)", boxShadow: "var(--shadow-lg)", maxWidth: "600px" }}>
          <h2 style={{ marginBottom: "1.5rem", fontSize: "1.5rem", fontWeight: "600", color: "var(--text-primary)" }}>Send Money</h2>
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <label style={{ display: "block", marginBottom: "0.5rem", color: "var(--text-secondary)" }}>Amount (₹)</label>
              <input type="number" required value={amount} onChange={e => setAmount(e.target.value)}
                onKeyDown={e => {
                  const allowedKeys = ['Backspace', 'Delete', 'Tab', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'];
                  if (allowedKeys.includes(e.key)) return;
                  if ((e.ctrlKey || e.metaKey) && ['a', 'c', 'v', 'x'].includes(e.key.toLowerCase())) return;
                  if (!/^[0-9]$/.test(e.key)) e.preventDefault();
                }}
                onPaste={e => {
                  const pastedText = e.clipboardData.getData('text');
                  if (/[^0-9]/.test(pastedText)) e.preventDefault();
                }}
                style={{ width: "100%", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)", background: "rgba(255,255,255,0.05)", color: "var(--text-primary)" }} />
            </div>
            <div>
              <label style={{ display: "block", marginBottom: "0.5rem", color: "var(--text-secondary)" }}>Receiver ID</label>
              <input type="text" required value={receiver} onChange={e => setReceiver(e.target.value)} 
                style={{ width: "100%", padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)", background: "rgba(255,255,255,0.05)", color: "var(--text-primary)" }} />
            </div>
            <button type="submit" disabled={submitLoading} style={{ padding: "0.75rem", marginTop: "0.5rem", borderRadius: "var(--radius-md)", border: "none", background: "var(--accent-indigo)", color: "white", fontWeight: "600", cursor: "pointer" }}>
              {submitLoading ? "Processing..." : "Send"}
            </button>
          </form>

          {/* Submission Result */}
          {submitResult && (
            <div style={{ marginTop: "1.5rem", padding: "1rem", borderRadius: "var(--radius-md)", 
              backgroundColor: submitResult.status === "approved" ? "rgba(16, 185, 129, 0.1)" :
                               submitResult.status === "pending_otp" ? "rgba(245, 158, 11, 0.1)" :
                               submitResult.status === "blocked" ? "rgba(239, 68, 68, 0.1)" :
                               submitResult.status === "frozen" ? "rgba(107, 114, 128, 0.1)" : "rgba(239, 68, 68, 0.1)",
              border: `1px solid ${submitResult.status === "approved" ? "rgba(16, 185, 129, 0.3)" :
                                    submitResult.status === "pending_otp" ? "rgba(245, 158, 11, 0.3)" :
                                    submitResult.status === "blocked" ? "rgba(239, 68, 68, 0.3)" :
                                    submitResult.status === "frozen" ? "rgba(107, 114, 128, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
              color: submitResult.status === "approved" ? "var(--accent-emerald)" :
                     submitResult.status === "pending_otp" ? "var(--accent-amber)" :
                     submitResult.status === "blocked" ? "var(--accent-rose)" :
                     submitResult.status === "frozen" ? "var(--text-muted)" : "var(--accent-rose)"
            }}>
              {submitResult.status === "approved" && "✅ Approved — " + (submitResult.message || "Transaction successful.")}
              {submitResult.status === "pending_otp" && "⚠️ Under Review — " + (submitResult.message || "OTP required.")}
              {submitResult.status === "blocked" && "🚫 Blocked — " + (submitResult.message || "Transaction blocked.")}
              {submitResult.status === "frozen" && "❄️ Account Suspended — " + (submitResult.message || "Your account has been suspended. Please contact support.")}
              {submitResult.status === "error" && "❌ Error — " + submitResult.message}
            </div>
          )}

          {/* OTP Verification Form */}
          {submitResult?.status === "pending_otp" && (
            <form onSubmit={handleVerifyOtp} style={{ marginTop: "1rem", display: "flex", gap: "1rem" }}>
              <input type="text" required placeholder="Enter OTP" value={otp} onChange={e => setOtp(e.target.value)} 
                style={{ flex: 1, padding: "0.75rem", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)", background: "rgba(255,255,255,0.05)", color: "var(--text-primary)" }} />
              <button type="submit" disabled={otpLoading} style={{ padding: "0.75rem 1.5rem", borderRadius: "var(--radius-md)", border: "none", background: "var(--accent-amber)", color: "#000", fontWeight: "600", cursor: "pointer" }}>
                {otpLoading ? "..." : "Verify"}
              </button>
            </form>
          )}

          {/* OTP Verification Result */}
          {otpResult && (
            <div style={{ marginTop: "1rem", padding: "1rem", borderRadius: "var(--radius-md)",
              backgroundColor: otpResult.status === "success" ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
              border: `1px solid ${otpResult.status === "success" ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
              color: otpResult.status === "success" ? "var(--accent-emerald)" : "var(--accent-rose)"
            }}>
              {otpResult.status === "success" ? "✅ " : "❌ "} {otpResult.message}
            </div>
          )}
        </div>

        {/* Transaction History */}
        <div style={{ background: "var(--bg-card)", borderRadius: "var(--radius-xl)", padding: "1.5rem", border: "1px solid var(--border-subtle)", boxShadow: "var(--shadow-lg)" }}>
          <h2 style={{ marginBottom: "1.5rem", fontSize: "1.5rem", fontWeight: "600", color: "var(--text-primary)" }}>Transaction History</h2>
          {error && <div style={{ color: "var(--accent-rose)", marginBottom: "1rem" }}>{error}</div>}
          {loading ? (
            <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
              <p>Loading transactions...</p>
            </div>
          ) : (
            <TransactionTable 
              transactions={transactions}
              hideRiskScore={true}
            />
          )}
        </div>
      </div>
    </div>
  );
}
