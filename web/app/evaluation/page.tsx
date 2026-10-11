"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { DetectionView } from "@/lib/entities";

export default function EvaluationPage() {
  const router = useRouter();
  const [detections, setDetections] = useState<DetectionView[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/detections?limit=200", { cache: "no-store" }).then(async (res) => {
      if (res.status === 401) {
        router.replace("/login");
        return;
      }
      if (!res.ok) {
        setError("Could not load the detection log.");
        return;
      }
      setDetections(await res.json());
    });
  }, [router]);

  if (error) return <p id="evalError">{error}</p>;
  if (!detections) return <p id="loading">Loading...</p>;

  return (
    <main>
      <h1 id="evaluationTitle">Orbital Sentinel - Detection Log</h1>
      <p>
        Every above-threshold telemetry window (REQ-18). Accuracy figures (precision / recall / F1 /
        point false-positive rate) are generated offline by{" "}
        <code>python -m app.evaluation.baseline</code> and reported in{" "}
        <code>docs/results/phase2_baseline.md</code>, since computing them live over the full labelled
        dataset would exceed the 1-second update budget (SRS REQ-5, section 5.1).
      </p>
      <p id="detectionCount">{detections.length} detections</p>
      <table id="detectionTable" border={1} cellPadding={6} style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>Detection ID</th>
            <th>Satellite</th>
            <th>Timestamp</th>
            <th>Anomaly Score</th>
            <th>Severity</th>
            <th>Persistence</th>
            <th>Outcome</th>
          </tr>
        </thead>
        <tbody>
          {detections.map((d) => (
            <tr key={d.detectionId} id={`detection-${d.detectionId}`}>
              <td>{d.detectionId}</td>
              <td>{d.satelliteName}</td>
              <td>{d.timestamp}</td>
              <td>{d.anomalyScore.toFixed(3)}</td>
              <td>{d.severityLevel ?? "-"}</td>
              <td>{d.persistenceCount}</td>
              <td>{d.outcome ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
