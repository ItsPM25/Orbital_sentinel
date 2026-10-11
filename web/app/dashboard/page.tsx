"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type { AlertView } from "@/lib/entities";
import { useStream } from "@/lib/useStream";

export default function DashboardPage() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<AlertView[] | null>(null);

  const reload = useCallback(() => {
    fetch("/api/alerts", { cache: "no-store" }).then(async (res) => {
      // 401 means there is no valid session.
      if (!res.ok) {
        router.replace("/login");
        return;
      }
      setAlerts(await res.json());
    });
  }, [router]);

  useEffect(() => {
    reload();
  }, [reload]);

  // REQ-16 live updates: a new or escalated alert, or a fresh detection, refreshes the list.
  useStream((evt) => {
    if (evt.event === "alert.created" || evt.event === "alert.updated" || evt.event === "ranking") {
      reload();
    }
  });

  async function acknowledge(alertId: string) {
    const res = await fetch(`/api/alerts/${alertId}/acknowledge`, { method: "POST" });
    if (!res.ok) return;
    const updated: AlertView = await res.json();
    setAlerts((prev) => prev && prev.map((a) => (a.alertId === alertId ? updated : a)));
  }

  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    router.replace("/login");
  }

  if (!alerts) return <p id="loading">Loading...</p>;

  return (
    <main>
      <h1 id="dashboardTitle">Orbital Sentinel - Alert Dashboard</h1>
      <nav>
        <Link href="/globe">Globe</Link> | <Link href="/evaluation">Evaluation</Link> | <button id="logoutBtn" onClick={logout}>Logout</button>
      </nav>
      <p id="alertCount">{alerts.length} alerts</p>
      <table id="alertTable" border={1} cellPadding={6} style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Alert ID</th>
            <th>Satellite</th>
            <th>Risk Level</th>
            <th>Severity</th>
            <th>Attributed Channel</th>
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
              <td className="satelliteName">
                <Link href={`/satellites/${a.satelliteId}`}>{a.satelliteName}</Link>
              </td>
              <td className="riskLevel">{a.riskLevel} ({a.riskLabel})</td>
              <td className="severityLevel">{a.severityLevel}</td>
              <td className="attributedChannel">{a.attributedChannel ?? "unknown"}</td>
              <td className="createdAt">{a.createdAt}</td>
              <td className="status" id={`status-${a.alertId}`}>{a.status}</td>
              <td>
                <button id={`ack-${a.alertId}`} disabled={a.status !== "AlertRaised"} onClick={() => acknowledge(a.alertId)}>
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
