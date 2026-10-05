"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { AlertView } from "@/lib/entities";

function hasSession() {
  return document.cookie.split("; ").some((c) => c.startsWith("os_session="));
}

export default function DashboardPage() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<AlertView[] | null>(null);

  useEffect(() => {
    if (!hasSession()) {
      router.replace("/login");
      return;
    }
    fetch("/api/alerts", { cache: "no-store" })
      .then((r) => r.json())
      .then(setAlerts);
  }, [router]);

  async function acknowledge(alertId: string) {
    const res = await fetch(`/api/alerts/${alertId}/acknowledge`, { method: "POST" });
    if (!res.ok) return;
    const updated: AlertView = await res.json();
    setAlerts((prev) => prev && prev.map((a) => (a.alertId === alertId ? updated : a)));
  }

  function logout() {
    document.cookie = "os_session=; Max-Age=0; path=/";
    router.replace("/login");
  }

  if (!alerts) return <p id="loading">Loading...</p>;

  return (
    <main>
      <h1 id="dashboardTitle">Orbital Sentinel - Alert Dashboard</h1>
      <button id="logoutBtn" onClick={logout}>Logout</button>
      <p id="alertCount">{alerts.length} alerts</p>
      <table id="alertTable" border={1} cellPadding={6} style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Alert ID</th>
            <th>Satellite</th>
            <th>Risk Level</th>
            <th>Severity</th>
            <th>Created At</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((a, i) => (
            <tr key={a.alertId} id={`alert-${a.alertId}`}>
              <td className="rank">{i + 1}</td>
              <td className="alertId">{a.alertId}</td>
              <td className="satelliteName">{a.satelliteName}</td>
              <td className="riskLevel">{a.riskLevel} ({a.riskLabel})</td>
              <td className="severityLevel">{a.severityLevel}</td>
              <td className="createdAt">{a.createdAt}</td>
              <td className="status" id={`status-${a.alertId}`}>{a.status}</td>
              <td>
                <button id={`ack-${a.alertId}`} disabled={a.status === "Acknowledged"} onClick={() => acknowledge(a.alertId)}>
                  Acknowledge
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
