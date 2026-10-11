"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError, type Channel, type SatelliteHealth, type TelemetrySeries } from "@/lib/api";
import { useStream } from "@/lib/useStream";

// Recharts needs one row per point; anomaly ranges are rendered as a shaded Area
// using a band that is only non-zero inside a flagged range (REQ-17).
function buildChartRows(series: TelemetrySeries) {
  const bandMax = Math.max(...series.points, 0) * 1.05 || 1;
  const bandMin = Math.min(...series.points, 0) * 1.05;
  return series.pointIndices.map((index, i) => {
    const inRange = series.anomalyRanges.some((r) => index >= r.start && index <= r.end);
    return { index, value: series.points[i], anomalyBand: inRange ? [bandMin, bandMax] : null };
  });
}

export default function SatelliteHealthPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const satelliteId = params.id;

  const [health, setHealth] = useState<SatelliteHealth | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<string>("");
  const [series, setSeries] = useState<TelemetrySeries | null>(null);
  const [error, setError] = useState("");

  const loadHealth = useCallback(() => {
    api
      .satelliteHealth(satelliteId)
      .then(setHealth)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) router.replace("/login");
        else if (err instanceof ApiError && err.status === 404) setError(`Satellite ${satelliteId} not found.`);
        else setError("Could not load satellite health.");
      });
  }, [satelliteId, router]);

  useEffect(() => {
    loadHealth();
    api.satelliteChannels(satelliteId).then(setChannels).catch(() => {});
  }, [satelliteId, loadHealth]);

  // Default to the top attributed channel once health loads, if nothing picked yet.
  useEffect(() => {
    if (!selectedChannel && health?.attributedChannels.length) {
      setSelectedChannel(health.attributedChannels[0].channelId);
    }
  }, [health, selectedChannel]);

  useEffect(() => {
    if (!selectedChannel) return;
    api.satelliteTelemetry(satelliteId, selectedChannel).then(setSeries).catch(() => setSeries(null));
  }, [satelliteId, selectedChannel]);

  useStream((evt) => {
    if (evt.satelliteId === satelliteId) {
      loadHealth();
      if (selectedChannel) api.satelliteTelemetry(satelliteId, selectedChannel).then(setSeries).catch(() => {});
    }
  });

  if (error) return <p id="healthError">{error}</p>;
  if (!health) return <p id="loading">Loading...</p>;

  return (
    <main>
      <h1 id="healthTitle">{health.satelliteName} - Health Panel</h1>
      {health.isProxy && (
        <p id="proxyBadge" style={{ color: "#8a5a00" }}>
          Replayed telemetry (proxy satellite: {health.telemetrySource ?? "see docs/ARCHITECTURE.md section 4.3"})
        </p>
      )}
      <table border={1} cellPadding={6} style={{ borderCollapse: "collapse" }}>
        <tbody>
          <tr>
            <th style={{ textAlign: "left" }}>Verdict</th>
            <td id="verdict">{health.verdict}</td>
          </tr>
          <tr>
            <th style={{ textAlign: "left" }}>Risk Level</th>
            <td id="riskLevel">{health.riskLevel ?? "-"}</td>
          </tr>
          <tr>
            <th style={{ textAlign: "left" }}>Severity</th>
            <td id="severityLevel">{health.severityLevel ?? "-"}</td>
          </tr>
          <tr>
            <th style={{ textAlign: "left" }}>Anomaly Score</th>
            <td id="anomalyScore">{health.anomalyScore?.toFixed(3) ?? "-"}</td>
          </tr>
          <tr>
            <th style={{ textAlign: "left" }}>Detected At</th>
            <td id="detectedAt">{health.detectedAt ?? "-"}</td>
          </tr>
        </tbody>
      </table>

      <h2>Attributed Channels</h2>
      {health.attributedChannels.length === 0 ? (
        <p id="attributionUnknown">unknown (no channel stood out)</p>
      ) : (
        <ul id="attributedChannels">
          {health.attributedChannels.map((c) => (
            <li key={c.channelId}>
              <button onClick={() => setSelectedChannel(c.channelId)}>
                {c.channelName} ({(c.contributionScore * 100).toFixed(0)}%)
              </button>
            </li>
          ))}
        </ul>
      )}

      <h2>Telemetry</h2>
      <label htmlFor="channelSelect">Channel: </label>
      <select id="channelSelect" value={selectedChannel} onChange={(e) => setSelectedChannel(e.target.value)}>
        <option value="">-- choose a channel --</option>
        {channels.map((c) => (
          <option key={c.channelId} value={c.channelId}>
            {c.channelName}
            {c.unit ? ` (${c.unit})` : ""}
          </option>
        ))}
      </select>

      {series && (
        <div id="telemetryChart" style={{ width: "100%", height: 320, marginTop: 12 }}>
          <ResponsiveContainer>
            <ComposedChart data={buildChartRows(series)}>
              <XAxis dataKey="index" />
              <YAxis />
              <Tooltip />
              {/* Shaded band over the ranges the model actually flagged (REQ-17) */}
              <Area dataKey="anomalyBand" stroke="none" fill="#f3b4b4" isAnimationActive={false} connectNulls={false} />
              <Line dataKey="value" dot={false} stroke="#2563eb" isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
          <p>
            {series.totalPoints} points total ({series.points.length} shown, downsampled);{" "}
            {series.anomalyRanges.length} flagged range(s) shaded.
          </p>
        </div>
      )}
    </main>
  );
}
