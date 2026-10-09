import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import "./Login.css";

const API = "/api/v1/auth";

export default function Login() {
  const nav = useNavigate();
  const [step, setStep] = useState("creds");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState(["","","","","",""]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showPw, setShowPw] = useState(false);
  const otpRefs = useRef([]);

  useEffect(() => {
    if (localStorage.getItem("access_token")) nav("/dashboard", { replace: true });
  }, [nav]);

  useEffect(() => {
    if (step === "otp" && otpRefs.current[0]) otpRefs.current[0].focus();
  }, [step]);

  async function handleLogin(e) {
    e.preventDefault();
    setError(""); setSuccess(""); setLoading(true);
    try {
      const r = await fetch(`${API}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Login failed");
      setSuccess(d.message);
      setStep("otp");
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  function otpChange(i, v) {
    if (!/^\d*$/.test(v)) return;
    const n = [...otp]; n[i] = v.slice(-1); setOtp(n);
    if (v && i < 5) otpRefs.current[i+1]?.focus();
  }
  function otpKey(i, e) {
    if (e.key === "Backspace" && !otp[i] && i > 0) otpRefs.current[i-1]?.focus();
  }
  function otpPaste(e) {
    e.preventDefault();
    const p = e.clipboardData.getData("text").replace(/\D/g,"").slice(0,6);
    const n = [...otp]; for (let i=0;i<6;i++) n[i]=p[i]||"";
    setOtp(n); otpRefs.current[Math.min(p.length,5)]?.focus();
  }

  async function handleOtp(e) {
    e.preventDefault();
    setError(""); setLoading(true);
    const code = otp.join("");
    if (code.length !== 6) { setError("Enter all 6 digits"); setLoading(false); return; }
    try {
      const r = await fetch(`${API}/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, otp_code: code }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "OTP failed");
      localStorage.setItem("access_token", d.access_token);
      setSuccess("Authenticated! Redirecting…");
      setTimeout(() => nav("/dashboard", { replace: true }), 800);
    } catch (err) {
      setError(err.message);
      setOtp(["","","","","",""]); otpRefs.current[0]?.focus();
    } finally { setLoading(false); }
  }

  function goBack() {
    setStep("creds"); setOtp(["","","","","",""]); setError(""); setSuccess("");
  }

  return (
    <div className="login-page">
      <div className="login-bg-mesh" />
      <div className="login-bg-orb login-bg-orb--1" />
      <div className="login-bg-orb login-bg-orb--2" />
      <div className="login-bg-orb login-bg-orb--3" />

      <div className="login-container">
        <div className="login-header">
          <div className="login-logo">
            <div className="login-logo__icon">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M12 2L3 7V12C3 17.55 6.84 22.74 12 24C17.16 22.74 21 17.55 21 12V7L12 2Z" fill="url(#sg)" opacity="0.2"/>
                <path d="M12 2L3 7V12C3 17.55 6.84 22.74 12 24C17.16 22.74 21 17.55 21 12V7L12 2Z" stroke="url(#sg)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M9 12L11 14L15 10" stroke="url(#sg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <defs><linearGradient id="sg" x1="3" y1="2" x2="21" y2="24"><stop stopColor="#6366f1"/><stop offset="1" stopColor="#a78bfa"/></linearGradient></defs>
              </svg>
            </div>
            <h1 className="login-logo__title">FraudShield</h1>
          </div>
          <p className="login-subtitle">{step==="creds"?"Sign in to the admin panel":"Enter the verification code"}</p>
        </div>

        <div className="login-steps">
          <div className={`login-step ${step==="creds"?"login-step--active":"login-step--done"}`}>
            <span className="login-step__num">1</span><span className="login-step__label">Credentials</span>
          </div>
          <div className="login-step__divider"/>
          <div className={`login-step ${step==="otp"?"login-step--active":""}`}>
            <span className="login-step__num">2</span><span className="login-step__label">Verify OTP</span>
          </div>
        </div>

        <div className="login-card" key={step}>
          {error && <div className="login-toast login-toast--error" role="alert"><span>{error}</span></div>}
          {success && <div className="login-toast login-toast--success" role="status"><span>{success}</span></div>}

          {step === "creds" && (
            <form onSubmit={handleLogin} className="login-form" autoComplete="off">
              <div className="login-field">
                <label htmlFor="login-username" className="login-label">Username</label>
                <div className="login-input-wrap">
                  <input id="login-username" type="text" className="login-input" placeholder="Enter your username" value={username} onChange={e=>setUsername(e.target.value)} required autoFocus/>
                </div>
              </div>
              <div className="login-field">
                <label htmlFor="login-password" className="login-label">Password</label>
                <div className="login-input-wrap">
                  <input id="login-password" type={showPw?"text":"password"} className="login-input" placeholder="Enter your password" value={password} onChange={e=>setPassword(e.target.value)} required/>
                  <button type="button" className="login-toggle-pw" onClick={()=>setShowPw(!showPw)} aria-label={showPw?"Hide password":"Show password"}>
                    {showPw?"🙈":"👁️"}
                  </button>
                </div>
              </div>
              <button id="login-submit" type="submit" className="login-btn login-btn--primary" disabled={loading||!username||!password}>
                {loading ? <span className="login-btn__spinner"/> : "Sign In →"}
              </button>
            </form>
          )}

          {step === "otp" && (
            <form onSubmit={handleOtp} className="login-form">
              <p className="login-otp-hint">A 6-digit code was sent to your registered email.</p>
              <div className="login-otp-boxes" onPaste={otpPaste}>
                {otp.map((d,i)=>(
                  <input key={i} id={`otp-${i}`} ref={el=>otpRefs.current[i]=el} type="text" inputMode="numeric" maxLength={1} className="login-otp-digit" value={d} onChange={e=>otpChange(i,e.target.value)} onKeyDown={e=>otpKey(i,e)}/>
                ))}
              </div>
              <button id="otp-submit" type="submit" className="login-btn login-btn--primary" disabled={loading||otp.join("").length!==6}>
                {loading ? <span className="login-btn__spinner"/> : "Verify & Continue →"}
              </button>
              <button type="button" className="login-btn login-btn--ghost" onClick={goBack}>← Back to Sign In</button>
            </form>
          )}
        </div>

        <p className="login-footer">Protected by two-factor authentication</p>
      </div>
    </div>
  );
}
