"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type EvaluationMetrics } from "@/lib/api";
import type { DetectionView } from "@/lib/entities";
import { useUser } from "@/lib/useUser";

const PAGE_SIZE = 25;

function MetricsCard({ title, metrics }: { title: string; metrics: EvaluationMetrics | null }) {
  if (!metrics) return null;
  if (!metrics.available) {
    return (
      <div style={{ border: "1px solid #ccc", padding: 10, marginBottom: 10 }}>
        <h3>{title}</h3>
        <p>{metrics.message}</p>
      </div>
    );
  }
  return (
    <div style={{ border: "1px solid #ccc", padding: 10, marginBottom: 10 }}>
      <h3>{title}</h3>
      <table border={1} cellPadding={4} style={{ borderCollapse: "collapse" }}>
        <tbody>
          <tr><th>Channels</th><td>{metrics.channelsEvaluated}</td></tr>
          <tr><th>Precision</th><td>{metrics.precision?.toFixed(3)}</td></tr>
          <tr><th>Recall</th><td>{metrics.recall?.toFixed(3)}</td></tr>
          <tr><th>F1</th><td>{metrics.f1?.toFixed(3)}</td></tr>
          <tr><th>Point FPR</th><td>{metrics.pointFpr?.toFixed(4)}</td></tr>
        </tbody>
      </table>
    </div>
  );
}

export default function EvaluationPage() {
  const { user, error: userError } = useUser(["Evaluator", "Administrator"]);
  const [baseline, setBaseline] = useState<EvaluationMetrics | null>(null);
  const [without, setWithout] = useState<EvaluationMetrics | null>(null);
  const [withFilter, setWithFilter] = useState<EvaluationMetrics | null>(null);

  const [detections, setDetections] = useState<DetectionView[] | null>(null);
  const [satelliteFilter, setSatelliteFilter] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    api.evaluationMetrics().then(setBaseline).catch(() => {});
    api.evaluationMetrics(undefined, "off").then(setWithout).catch(() => {});
    api.evaluationMetrics(undefined, "on").then(setWithFilter).catch(() => {});
  }, [user]);

  useEffect(() => {
    if (!user) return;
    api
      .detections({
        satelliteId: satelliteFilter || undefined,
        outcome: outcomeFilter || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      .then(setDetections)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load the detection log."));
  }, [user, satelliteFilter, outcomeFilter, page]);

  if (userError) return <p id="evalError">{userError}</p>;
  if (!user) return <p id="loading">Loading...</p>;

  return (
    <main>
      <h1 id="evaluationTitle">Orbital Sentinel - Evaluation</h1>

      <h2>Accuracy (REQ-5, REQ-11)</h2>
      <p>
        Precomputed offline by <code>python -m app.evaluation.baseline</code> and{" "}
        <code>python -m app.evaluation.reports</code>, not recomputed live (SRS section 5.1's 1-second
        budget would not survive scoring the whole labelled dataset on every page load).
      </p>
      <MetricsCard title="Baseline (no persistence filter)" metrics={baseline} />
      <MetricsCard title="REQ-11: without the persistence filter" metrics={without} />
      <MetricsCard title="REQ-11: with the persistence filter" metrics={withFilter} />

      <h2>Detection Log (REQ-18)</h2>
      <div>
        <label htmlFor="satelliteFilter">Satellite ID: </label>
        <input
          id="satelliteFilter"
          value={satelliteFilter}
          onChange={(e) => {
            setPage(0);
            setSatelliteFilter(e.target.value);
          }}
        />
        <label htmlFor="outcomeFilter" style={{ marginLeft: 12 }}>Outcome: </label>
        <select
          id="outcomeFilter"
          value={outcomeFilter}
          onChange={(e) => {
            setPage(0);
            setOutcomeFilter(e.target.value);
          }}
        >
          <option value="">All</option>
          <option value="Confirmed">Confirmed</option>
          <option value="Suppressed">Suppressed</option>
        </select>
      </div>

      {error && <p id="detectionError">{error}</p>}
      {!detections ? (
        <p>Loading detections...</p>
      ) : (
        <>
          <p id="detectionCount">{detections.length} detections (page {page + 1})</p>
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
          <button id="prevPage" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
            Previous
          </button>
          <button id="nextPage" onClick={() => setPage((p) => p + 1)} disabled={detections.length < PAGE_SIZE}>
            Next
          </button>
        </>
      )}
    </main>
  );
}
