import React from 'react';

export default function RiskBadge({ score = 0, tier = "Low" }) {
  let badgeStyle = {
    padding: "4px 10px",
    borderRadius: "12px",
    fontSize: "0.75rem",
    fontWeight: "700",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    boxShadow: "var(--shadow-sm)",
    transition: "all 0.3s ease"
  };

  const isHigh = tier === "High" || score >= 80;
  const isMedium = tier === "Medium" || (score >= 40 && score < 80);

  if (isHigh) {
    badgeStyle.backgroundColor = "rgba(251, 113, 133, 0.15)";
    badgeStyle.color = "var(--accent-rose)";
    badgeStyle.border = "1px solid rgba(251, 113, 133, 0.3)";
    badgeStyle.boxShadow = "0 0 12px rgba(251, 113, 133, 0.4)";
  } else if (isMedium) {
    badgeStyle.backgroundColor = "rgba(251, 191, 36, 0.15)";
    badgeStyle.color = "var(--accent-amber)";
    badgeStyle.border = "1px solid rgba(251, 191, 36, 0.3)";
  } else {
    badgeStyle.backgroundColor = "rgba(52, 211, 153, 0.15)";
    badgeStyle.color = "var(--accent-emerald)";
    badgeStyle.border = "1px solid rgba(52, 211, 153, 0.3)";
  }

  return (
    <span 
      style={badgeStyle} 
      title={`Risk Score: ${score}`}
      className={isHigh ? "badge-pulse-high" : ""}
    >
      {tier}
    </span>
  );
}
