import { ReactNode, useEffect, useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { Line, OrbitControls } from '@react-three/drei';
import {
  apiBaseUrl,
  checkHealth,
  getContactWindows,
  getOpsPolicyComparison,
  getOrbitTrack,
  getPosition,
  getSatellite,
  getSimulatedEvents,
  getSimulatedTelemetry,
  ingestCelesTrak,
  listSatellites,
  type ContactWindowParams,
  type OrbitTrackParams,
  type SimulationParams,
} from './api';
import type {
  ContactWindowListResponse,
  OpsPolicyComparisonResponse,
  OrbitTrackResponse,
  SatelliteListResponse,
  SatellitePositionResponse,
  SatelliteRecord,
  SimulatedEventWorkflowResponse,
  SimulatedTelemetryResponse,
} from './types';

const ISS_NORAD_ID = 25544;
const telemetryScenarios = ['nominal', 'thermal_drift', 'power_drop', 'comms_degradation'];
const opsPolicies = ['conservative_ops', 'balanced_ops', 'relaxed_ops'];


type CatalogLoadMode = 'none' | 'cache' | 'ingest-cache' | 'force-refresh' | 'error-cache-available';

interface CatalogStatusState {
  mode: CatalogLoadMode;
  totalRecords: number;
  visibleRecords: number;
  lastIngestedAt?: string;
  message: string;
}

function buildCatalogStatus(response: SatelliteListResponse, mode: CatalogLoadMode): CatalogStatusState {
  const ingestedTimes = response.items
    .map((item) => item.ingested_at)
    .filter(Boolean)
    .sort();
  const lastIngestedAt = ingestedTimes.length > 0 ? ingestedTimes[ingestedTimes.length - 1] : undefined;
  const sourceLabel = mode === 'force-refresh' ? 'refreshed from CelesTrak' : mode === 'ingest-cache' ? 'ingest / cached catalog' : 'cached catalog';
  return {
    mode,
    totalRecords: response.count,
    visibleRecords: response.items.length,
    lastIngestedAt,
    message: `${response.count.toLocaleString()} records loaded · ${sourceLabel}`,
  };
}

function friendlyCatalogError(error: unknown, cachedCount: number): string {
  const rawMessage = error instanceof Error ? error.message : String(error);
  const lower = rawMessage.toLowerCase();
  if (lower.includes('celestrak') && (lower.includes('403') || lower.includes('502') || lower.includes('bad gateway'))) {
    const cacheHint = cachedCount > 0
      ? ` The cached catalog is still available (${cachedCount.toLocaleString()} records). Use "Load cached catalog" and retry refresh later.`
      : ' No cached catalog is loaded in the UI yet; try "Load cached catalog" if local cache exists.';
    return `CelesTrak rejected a repeated public-catalog download because the source may not have updated yet.${cacheHint}`;
  }
  return rawMessage;
}

const groundStationPresets = [
  {
    label: 'Pacific demo station',
    ground_station_name: 'Pacific demo station',
    latitude_deg: 8.45,
    longitude_deg: -106.2,
    altitude_m: 0,
  },
  {
    label: 'Wallops Island',
    ground_station_name: 'Wallops Island',
    latitude_deg: 37.9402,
    longitude_deg: -75.4664,
    altitude_m: 10,
  },
  {
    label: 'Svalbard reference',
    ground_station_name: 'Svalbard reference',
    latitude_deg: 78.2298,
    longitude_deg: 15.4078,
    altitude_m: 460,
  },
];

function toDatetimeLocalValue(date: Date): string {
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

function datetimeLocalToIso(value: string): string {
  return new Date(value).toISOString();
}

function formatDate(value: string | null | undefined): string {
  if (!value) return 'Unknown';
  return new Date(value).toLocaleString();
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'Unknown';
  return value.toFixed(digits);
}

function mapLeft(longitudeDeg: number): number {
  return ((longitudeDeg + 180) / 360) * 100;
}

function mapTop(latitudeDeg: number): number {
  return ((90 - latitudeDeg) / 180) * 100;
}

function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'fresh' | 'stale' | 'warning' | 'neutral' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function DataLineageCard({ selected }: { selected: SatelliteRecord | null }) {
  return (
    <section className="card lineage-card">
      <div className="section-eyebrow">Data lineage and limits</div>
      <h2>Public orbit context, derived estimates</h2>
      <p>
        Catalog records come from CelesTrak public GP JSON. Position and contact-window outputs
        are approximate SGP4-derived estimates from public orbit elements.
      </p>
      <div className="lineage-grid">
        <div>
          <span className="label">Source</span>
          <strong>{selected?.source.name ?? 'CelesTrak public GP JSON'}</strong>
        </div>
        <div>
          <span className="label">Lineage type</span>
          <strong>{selected?.source.type ?? 'real_public_orbit_data'}</strong>
        </div>
        <div>
          <span className="label">Freshness</span>
          {selected ? (
            <Badge tone={selected.freshness_status === 'fresh' ? 'fresh' : selected.freshness_status === 'stale' ? 'stale' : 'neutral'}>
              {selected.freshness_status}
            </Badge>
          ) : (
            <Badge>select a satellite</Badge>
          )}
        </div>
      </div>
      <ul className="limits-list">
        <li>No live spacecraft connection or live telemetry.</li>
        <li>No validated contact scheduling or mission-grade operations claim.</li>
        <li>No RF link budget, antenna mask, terrain, weather, downlink, or telecommand model.</li>
        <li>Manual or preset ground-station inputs only; no browser geolocation is requested.</li>
      </ul>
    </section>
  );
}

function MissionMap({
  position,
  contactWindows,
  station,
}: {
  position: SatellitePositionResponse | null;
  contactWindows: ContactWindowListResponse | null;
  station: ContactWindowParams;
}) {
  const satelliteGeo = position?.approximate_geodetic;
  const satelliteStyle = satelliteGeo
    ? { left: `${mapLeft(satelliteGeo.longitude_deg)}%`, top: `${mapTop(satelliteGeo.latitude_deg)}%` }
    : undefined;
  const stationStyle = {
    left: `${mapLeft(station.longitude_deg)}%`,
    top: `${mapTop(station.latitude_deg)}%`,
  };

  return (
    <section className="card map-card">
      <div className="section-eyebrow">Approximate 2D context</div>
      <h2>Satellite / ground-station view</h2>
      <div className="world-map" aria-label="Approximate equirectangular world map">
        <div className="equator" />
        <div className="prime-meridian" />
        <div className="track-line" />
        <div className="marker station-marker" style={stationStyle} title="Ground station">
          <span>GS</span>
        </div>
        {satelliteStyle ? (
          <div className="marker satellite-marker" style={satelliteStyle} title="Approximate satellite position">
            <span>SAT</span>
          </div>
        ) : null}
      </div>
      <div className="map-readout">
        <div>
          <span className="label">Ground station</span>
          <strong>
            {station.ground_station_name} ({formatNumber(station.latitude_deg)}, {formatNumber(station.longitude_deg)})
          </strong>
        </div>
        <div>
          <span className="label">Satellite geodetic estimate</span>
          <strong>
            {satelliteGeo
              ? `${formatNumber(satelliteGeo.latitude_deg)}, ${formatNumber(satelliteGeo.longitude_deg)} / ${formatNumber(
                  satelliteGeo.altitude_km,
                  1,
                )} km`
              : 'Request a position estimate'}
          </strong>
        </div>
        <div>
          <span className="label">Estimated windows</span>
          <strong>{contactWindows ? `${contactWindows.count} window(s)` : 'Not calculated yet'}</strong>
        </div>
      </div>
      <p className="hint">The map uses a simple equirectangular projection and is for orientation only.</p>
    </section>
  );
}

function kmToScene(value: { x: number; y: number; z: number }): [number, number, number] {
  const scale = 1 / 2200;
  return [value.x * scale, value.z * scale, -value.y * scale];
}

function OrbitPlaybackScene({ track, currentIndex }: { track: OrbitTrackResponse | null; currentIndex: number }) {
  const orbitPoints = useMemo(() => track?.points.map((point) => kmToScene(point.position_km)) ?? [], [track]);
  const markerPoint = orbitPoints[Math.min(currentIndex, Math.max(orbitPoints.length - 1, 0))];

  return (
    <Canvas camera={{ position: [0, 0, 8], fov: 46 }}>
      <ambientLight intensity={0.65} />
      <directionalLight position={[4, 3, 5]} intensity={1.2} />
      <mesh>
        <sphereGeometry args={[2.9, 48, 48]} />
        <meshStandardMaterial color="#102647" roughness={0.7} metalness={0.05} />
      </mesh>
      <mesh>
        <sphereGeometry args={[2.93, 48, 48]} />
        <meshBasicMaterial color="#2f80ed" wireframe transparent opacity={0.18} />
      </mesh>
      <Line points={[[-3.4, 0, 0], [3.4, 0, 0]]} color="#64748b" lineWidth={1} transparent opacity={0.45} />
      {orbitPoints.length > 1 ? <Line points={orbitPoints} color="#7dd3fc" lineWidth={2} /> : null}
      {markerPoint ? (
        <mesh position={markerPoint}>
          <sphereGeometry args={[0.12, 24, 24]} />
          <meshStandardMaterial color="#fbbf24" emissive="#f59e0b" emissiveIntensity={0.8} />
        </mesh>
      ) : null}
      <OrbitControls enablePan={false} minDistance={5} maxDistance={12} />
    </Canvas>
  );
}

function OrbitPlaybackCard({
  selectedId,
  track,
  trackParams,
  currentIndex,
  isPlaying,
  playbackSpeed,
  onTrackParamsChange,
  onLoadTrack,
  onSetCurrentIndex,
  onTogglePlaying,
  onReset,
  onPlaybackSpeedChange,
}: {
  selectedId: number | null;
  track: OrbitTrackResponse | null;
  trackParams: OrbitTrackParams;
  currentIndex: number;
  isPlaying: boolean;
  playbackSpeed: number;
  onTrackParamsChange: (params: OrbitTrackParams) => void;
  onLoadTrack: () => void;
  onSetCurrentIndex: (index: number) => void;
  onTogglePlaying: () => void;
  onReset: () => void;
  onPlaybackSpeedChange: (speed: number) => void;
}) {
  const currentPoint = track?.points[currentIndex] ?? null;
  const maxIndex = Math.max((track?.points.length ?? 1) - 1, 0);

  return (
    <section className="card orbit-card">
      <div className="section-eyebrow">Approximate 3D orbit playback</div>
      <h2>Local globe and SGP4-derived track</h2>
      <p>
        This visualization samples public orbit elements through the local SGP4 approximation and renders a
        procedural globe in the browser. It does not use Cesium, Cesium Ion tokens, external map services, live tracking,
        or mission-grade flight dynamics validation.
      </p>
      <div className="orbit-layout">
        <div className="orbit-canvas" aria-label="Approximate 3D orbit playback globe">
          <OrbitPlaybackScene track={track} currentIndex={currentIndex} />
        </div>
        <div className="orbit-controls">
          <div className="form-grid compact-form-grid">
            <label>Start<input type="datetime-local" value={trackParams.start} onChange={(e) => onTrackParamsChange({ ...trackParams, start: e.target.value })} /></label>
            <label>End<input type="datetime-local" value={trackParams.end} onChange={(e) => onTrackParamsChange({ ...trackParams, end: e.target.value })} /></label>
            <label>Step seconds<input type="number" value={trackParams.step_seconds} onChange={(e) => onTrackParamsChange({ ...trackParams, step_seconds: Number(e.target.value) })} /></label>
          </div>
          <button disabled={!selectedId} onClick={onLoadTrack}>Load orbit track</button>
          {track ? (
            <>
              <div className="button-row playback-buttons">
                <button onClick={onTogglePlaying}>{isPlaying ? 'Pause' : 'Play'}</button>
                <button className="secondary" onClick={onReset}>Reset</button>
                <label className="speed-control">Speed
                  <select value={playbackSpeed} onChange={(e) => onPlaybackSpeedChange(Number(e.target.value))}>
                    <option value={0.5}>0.5x</option>
                    <option value={1}>1x</option>
                    <option value={2}>2x</option>
                    <option value={4}>4x</option>
                  </select>
                </label>
              </div>
              <label className="scrub-control">
                Playback frame
                <input type="range" min={0} max={maxIndex} value={currentIndex} onChange={(e) => onSetCurrentIndex(Number(e.target.value))} />
              </label>
              <div className="facts-grid orbit-readout">
                <div><span className="label">Samples</span><strong>{track.sample_count}</strong></div>
                <div><span className="label">Frame</span><strong>{currentIndex + 1} / {track.sample_count}</strong></div>
                <div><span className="label">Current time</span><strong>{formatDate(currentPoint?.timestamp)}</strong></div>
                <div><span className="label">Altitude</span><strong>{formatNumber(currentPoint?.approximate_geodetic.altitude_km, 1)} km</strong></div>
                <div><span className="label">Latitude</span><strong>{formatNumber(currentPoint?.approximate_geodetic.latitude_deg)}°</strong></div>
                <div><span className="label">Longitude</span><strong>{formatNumber(currentPoint?.approximate_geodetic.longitude_deg)}°</strong></div>
              </div>
              <div className="orbit-legend">
        <strong>Approximate SGP4-derived path · public CelesTrak orbit elements · not live tracking</strong>
        <span>
          Marker shows the selected playback frame. The path is sampled from the start/end/step controls; altitude scaling is visual context, not a flight-dynamics claim.
        </span>
      </div>
      <p className="hint">{track.limitations.join(' · ')}</p>
            </>
          ) : <p className="hint">Load a bounded track to see approximate playback over the selected public orbit record.</p>}
        </div>
      </div>
    </section>
  );
}

export default function App() {
  const [health, setHealth] = useState('checking');
  const [satellites, setSatellites] = useState<SatelliteRecord[]>([]);
  const [catalogStatus, setCatalogStatus] = useState<CatalogStatusState>({
    mode: 'none',
    totalRecords: 0,
    visibleRecords: 0,
    message: 'No catalog loaded yet.',
  });
  const [catalogNotice, setCatalogNotice] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selected, setSelected] = useState<SatelliteRecord | null>(null);
  const [search, setSearch] = useState('');
  const [positionAt, setPositionAt] = useState(toDatetimeLocalValue(new Date()));
  const [position, setPosition] = useState<SatellitePositionResponse | null>(null);
  const [orbitTrack, setOrbitTrack] = useState<OrbitTrackResponse | null>(null);
  const [orbitTrackParams, setOrbitTrackParams] = useState<OrbitTrackParams>(() => {
    const now = new Date();
    const end = new Date(now.getTime() + 90 * 60_000);
    return { start: toDatetimeLocalValue(now), end: toDatetimeLocalValue(end), step_seconds: 180 };
  });
  const [orbitFrame, setOrbitFrame] = useState(0);
  const [orbitPlaying, setOrbitPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [contactWindows, setContactWindows] = useState<ContactWindowListResponse | null>(null);
  const [simulation, setSimulation] = useState<SimulationParams>({
    scenario: 'thermal_drift',
    seed: 42,
    duration_minutes: 60,
    step_seconds: 300,
  });
  const [policy, setPolicy] = useState('balanced_ops');
  const [telemetry, setTelemetry] = useState<SimulatedTelemetryResponse | null>(null);
  const [eventWorkflow, setEventWorkflow] = useState<SimulatedEventWorkflowResponse | null>(null);
  const [policyComparison, setPolicyComparison] = useState<OpsPolicyComparisonResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [station, setStation] = useState<ContactWindowParams>(() => {
    const now = new Date();
    const end = new Date(now.getTime() + 90 * 60_000);
    return {
      ...groundStationPresets[0],
      start: toDatetimeLocalValue(now),
      end: toDatetimeLocalValue(end),
      step_seconds: 60,
      min_elevation_deg: 10,
    };
  });

  const matchingSatellites = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return normalized
      ? satellites.filter((item) =>
          `${item.object_name} ${item.norad_cat_id} ${item.object_id ?? ''}`.toLowerCase().includes(normalized),
        )
      : satellites;
  }, [satellites, search]);

  const filteredSatellites = useMemo(() => matchingSatellites.slice(0, 80), [matchingSatellites]);

  const latestSubsystemSamples = useMemo(() => {
    if (!telemetry) return [];
    const bySubsystem = new Map<string, SimulatedTelemetryResponse['samples'][number]>();
    for (const sample of telemetry.samples) {
      bySubsystem.set(sample.subsystem, sample);
    }
    return Array.from(bySubsystem.values());
  }, [telemetry]);

  async function loadCatalog() {
    setBusy('Loading catalog');
    setError(null);
    try {
      const response = await listSatellites();
      applySatelliteList(response, 'cache');
      setCatalogNotice(null);
    } catch (err) {
      setError(friendlyCatalogError(err, satellites.length));
    } finally {
      setBusy(null);
    }
  }

  function applySatelliteList(response: SatelliteListResponse, mode: CatalogLoadMode) {
    setSatellites(response.items);
    setCatalogStatus(buildCatalogStatus(response, mode));
    if (response.items.length > 0) {
      const preferred = response.items.find((item) => item.norad_cat_id === ISS_NORAD_ID) ?? response.items[0];
      setSelectedId((current) => {
        if (current && response.items.some((item) => item.norad_cat_id === current)) return current;
        return preferred.norad_cat_id;
      });
      setCatalogNotice('Catalog refreshed; selected satellite and derived panels are preserved when the selected NORAD ID remains in the catalog. Recompute derived panels only if you changed parameters.');
    }
  }

  async function refreshIngest(force: boolean) {
    setBusy(force ? 'Force refreshing CelesTrak data' : 'Refreshing CelesTrak data');
    setError(null);
    try {
      const response = await ingestCelesTrak(force);
      applySatelliteList(response, force ? 'force-refresh' : 'ingest-cache');
    } catch (err) {
      setError(friendlyCatalogError(err, satellites.length));
      if (satellites.length > 0) {
        setCatalogStatus((current) => ({
          ...current,
          mode: 'error-cache-available',
          message: `${current.totalRecords.toLocaleString()} cached records remain available · CelesTrak refresh limited`,
        }));
      }
    } finally {
      setBusy(null);
    }
  }

  async function requestPosition() {
    if (!selectedId) return;
    setBusy('Calculating approximate position');
    setError(null);
    try {
      setPosition(await getPosition(selectedId, datetimeLocalToIso(positionAt)));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function requestOrbitTrack() {
    if (!selectedId) return;
    setBusy('Sampling approximate orbit track');
    setError(null);
    try {
      const response = await getOrbitTrack(selectedId, {
        start: datetimeLocalToIso(orbitTrackParams.start),
        end: datetimeLocalToIso(orbitTrackParams.end),
        step_seconds: orbitTrackParams.step_seconds,
      });
      setOrbitTrack(response);
      setOrbitFrame(0);
      setOrbitPlaying(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function requestContactWindows() {
    if (!selectedId) return;
    setBusy('Estimating contact windows');
    setError(null);
    try {
      setContactWindows(
        await getContactWindows(selectedId, {
          ...station,
          start: datetimeLocalToIso(station.start),
          end: datetimeLocalToIso(station.end),
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function requestSimulatedOpsWorkflow() {
    if (!selectedId) return;
    setBusy('Generating simulated telemetry and event workflow');
    setError(null);
    try {
      const [telemetryResponse, eventsResponse, comparisonResponse] = await Promise.all([
        getSimulatedTelemetry(selectedId, simulation),
        getSimulatedEvents(selectedId, { ...simulation, policy }),
        getOpsPolicyComparison(selectedId, simulation),
      ]);
      setTelemetry(telemetryResponse);
      setEventWorkflow(eventsResponse);
      setPolicyComparison(comparisonResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    checkHealth()
      .then((response) => setHealth(response.status))
      .catch(() => setHealth('offline'));
    void loadCatalog();
  }, []);

  useEffect(() => {
    if (!orbitPlaying || !orbitTrack || orbitTrack.points.length < 2) return;
    const interval = window.setInterval(() => {
      setOrbitFrame((current) => (current >= orbitTrack.points.length - 1 ? 0 : current + 1));
    }, Math.max(120, 700 / playbackSpeed));
    return () => window.clearInterval(interval);
  }, [orbitPlaying, orbitTrack, playbackSpeed]);

  useEffect(() => {
    if (selectedId === null) {
      setSelected(null);
      return;
    }
    getSatellite(selectedId)
      .then(setSelected)
      .catch(() => setSelected(satellites.find((item) => item.norad_cat_id === selectedId) ?? null));
  }, [selectedId, satellites]);

  useEffect(() => {
    setPosition(null);
    setOrbitTrack(null);
    setOrbitFrame(0);
    setOrbitPlaying(false);
    setContactWindows(null);
    setTelemetry(null);
    setEventWorkflow(null);
    setPolicyComparison(null);
  }, [selectedId]);

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <div className="section-eyebrow">Mission Ops Lite</div>
          <h1>Mission data review dashboard for public orbit-derived planning</h1>
          <p>
            Review public catalog ingestion, freshness, approximate SGP4 position, and estimated
            ground-station contact windows from the local backend.
          </p>
        </div>
        <div className="status-stack">
          <Badge tone={health === 'ok' ? 'fresh' : 'stale'}>Backend {health}</Badge>
          <Badge>{apiBaseUrl()}</Badge>
        </div>
      </header>

      {error ? (
        <div className="error-banner">
          <span>{error}</span>
          {error.includes('CelesTrak') ? <button className="secondary inline-action" onClick={loadCatalog}>Load cached catalog</button> : null}
        </div>
      ) : null}
      {busy ? <div className="busy-banner">{busy}…</div> : null}

      <div className="dashboard-grid">
        <DataLineageCard selected={selected} />

        <section className="card controls-card">
          <div className="section-eyebrow">Catalog controls</div>
          <h2>Public CelesTrak catalog</h2>
          <div className="button-row">
            <button onClick={loadCatalog}>Load cached catalog</button>
            <button onClick={() => refreshIngest(false)}>Ingest / use cache</button>
            <button className="secondary" onClick={() => refreshIngest(true)}>Force refresh</button>
          </div>
          <div className="catalog-status">
            <strong>{catalogStatus.message}</strong>
            <span>
              Visible matches: {matchingSatellites.length.toLocaleString()} / {catalogStatus.totalRecords.toLocaleString()}
              {catalogStatus.lastIngestedAt ? ` · last ingested ${formatDate(catalogStatus.lastIngestedAt)}` : ''}
            </span>
            <span>Source: CelesTrak public GP active · mode: {catalogStatus.mode}</span>
          </div>
          {catalogNotice ? <p className="hint preserve-note">{catalogNotice}</p> : null}
          <label>
            Search satellite name, NORAD ID, or object ID
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="ISS, 25544, STARLINK" />
          </label>
          <div className="satellite-list">
            {filteredSatellites.map((item) => (
              <button
                className={item.norad_cat_id === selectedId ? 'satellite-row selected' : 'satellite-row'}
                key={item.norad_cat_id}
                onClick={() => setSelectedId(item.norad_cat_id)}
              >
                <span>{item.object_name}</span>
                <strong>{item.norad_cat_id}</strong>
              </button>
            ))}
            {filteredSatellites.length === 0 && satellites.length === 0 ? <p className="hint">No catalog rows loaded yet. Run ingest first or load the cached catalog.</p> : null}
            {filteredSatellites.length === 0 && satellites.length > 0 ? (
              <p className="hint">No matches for "{search}" in {satellites.length.toLocaleString()} loaded records. Try another object name or NORAD catalog ID.</p>
            ) : null}
          </div>
        </section>

        <section className="card detail-card">
          <div className="section-eyebrow">Selected satellite</div>
          <h2>{selected?.object_name ?? 'No satellite selected'}</h2>
          {selected ? (
            <div className="facts-grid">
              <div><span className="label">NORAD ID</span><strong>{selected.norad_cat_id}</strong></div>
              <div><span className="label">Object ID</span><strong>{selected.object_id ?? 'Unknown'}</strong></div>
              <div><span className="label">Source epoch</span><strong>{formatDate(selected.epoch)}</strong></div>
              <div><span className="label">Ingested at</span><strong>{formatDate(selected.ingested_at)}</strong></div>
              <div><span className="label">Epoch age</span><strong>{formatNumber(selected.epoch_age_hours, 1)} h</strong></div>
              <div><span className="label">Inclination</span><strong>{formatNumber(selected.inclination)}°</strong></div>
            </div>
          ) : (
            <p className="hint">Load the catalog and choose a satellite.</p>
          )}
        </section>

        <section className="card position-card">
          <div className="section-eyebrow">Approximate position</div>
          <h2>SGP4-derived state</h2>
          <label>
            Requested timestamp
            <input type="datetime-local" value={positionAt} onChange={(event) => setPositionAt(event.target.value)} />
          </label>
          <button disabled={!selectedId} onClick={requestPosition}>Calculate position</button>
          {position ? (
            <div className="facts-grid">
              <div><span className="label">Latitude</span><strong>{formatNumber(position.approximate_geodetic.latitude_deg)}°</strong></div>
              <div><span className="label">Longitude</span><strong>{formatNumber(position.approximate_geodetic.longitude_deg)}°</strong></div>
              <div><span className="label">Altitude</span><strong>{formatNumber(position.approximate_geodetic.altitude_km, 1)} km</strong></div>
              <div><span className="label">Frame</span><strong>{position.coordinate_frame}</strong></div>
            </div>
          ) : <p className="hint">Position is calculated on demand from the selected public orbit record.</p>}
        </section>

        <OrbitPlaybackCard
          selectedId={selectedId}
          track={orbitTrack}
          trackParams={orbitTrackParams}
          currentIndex={orbitFrame}
          isPlaying={orbitPlaying}
          playbackSpeed={playbackSpeed}
          onTrackParamsChange={setOrbitTrackParams}
          onLoadTrack={requestOrbitTrack}
          onSetCurrentIndex={(index) => {
            setOrbitFrame(index);
            setOrbitPlaying(false);
          }}
          onTogglePlaying={() => setOrbitPlaying((current) => !current)}
          onReset={() => {
            setOrbitFrame(0);
            setOrbitPlaying(false);
          }}
          onPlaybackSpeedChange={setPlaybackSpeed}
        />

        <section className="card contact-card">
          <div className="section-eyebrow">Contact windows</div>
          <h2>Ground-station estimate</h2>
          <label>
            Preset station
            <select
              onChange={(event) => {
                const preset = groundStationPresets[Number(event.target.value)];
                setStation((current) => ({ ...current, ...preset }));
              }}
            >
              {groundStationPresets.map((preset, index) => <option value={index} key={preset.label}>{preset.label}</option>)}
            </select>
          </label>
          <div className="form-grid">
            <label>Station name<input value={station.ground_station_name} onChange={(e) => setStation({ ...station, ground_station_name: e.target.value })} /></label>
            <label>Latitude<input type="number" value={station.latitude_deg} onChange={(e) => setStation({ ...station, latitude_deg: Number(e.target.value) })} /></label>
            <label>Longitude<input type="number" value={station.longitude_deg} onChange={(e) => setStation({ ...station, longitude_deg: Number(e.target.value) })} /></label>
            <label>Altitude m<input type="number" value={station.altitude_m} onChange={(e) => setStation({ ...station, altitude_m: Number(e.target.value) })} /></label>
            <label>Start<input type="datetime-local" value={station.start} onChange={(e) => setStation({ ...station, start: e.target.value })} /></label>
            <label>End<input type="datetime-local" value={station.end} onChange={(e) => setStation({ ...station, end: e.target.value })} /></label>
            <label>Step seconds<input type="number" value={station.step_seconds} onChange={(e) => setStation({ ...station, step_seconds: Number(e.target.value) })} /></label>
            <label>Min elevation<input type="number" value={station.min_elevation_deg} onChange={(e) => setStation({ ...station, min_elevation_deg: Number(e.target.value) })} /></label>
          </div>
          <button disabled={!selectedId} onClick={requestContactWindows}>Estimate contact windows</button>
          {contactWindows && contactWindows.count > 0 ? (
            <table>
              <thead><tr><th>Start</th><th>End</th><th>Peak</th><th>Duration</th><th>Max elev.</th></tr></thead>
              <tbody>
                {contactWindows.windows.map((window) => (
                  <tr key={`${window.start}-${window.end}`}>
                    <td>{formatDate(window.start)}</td>
                    <td>{formatDate(window.end)}</td>
                    <td>{formatDate(window.peak_at)}</td>
                    <td>{Math.round(window.duration_seconds)} s</td>
                    <td>{formatNumber(window.max_elevation_deg)}°</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : contactWindows && contactWindows.count === 0 ? (
            <div className="zero-state">
              <strong>No estimated contact windows for this time range and minimum elevation.</strong>
              <p>
                Station: {contactWindows.ground_station.name} · {formatDate(contactWindows.start)} to {formatDate(contactWindows.end)} · min elevation {formatNumber(contactWindows.min_elevation_deg)}°.
                Try a longer time range, lower min elevation, or another ground station.
              </p>
              <p className="hint">This estimate does not model RF link budget, terrain, weather, antenna masks, scheduling conflicts, or operations constraints.</p>
            </div>
          ) : <p className="hint">Contact windows are sampled estimates and are not stored by the backend.</p>}
        </section>

        <section className="card simulation-card">
          <div className="section-eyebrow">Simulated telemetry</div>
          <h2>Scenario-backed subsystem health</h2>
          <p>
            This panel layers deterministic simulated spacecraft telemetry on the selected public orbit
            record. It is not live spacecraft telemetry and is not a spacecraft monitoring system.
          </p>
          <div className="form-grid">
            <label>
              Scenario
              <select
                value={simulation.scenario}
                onChange={(e) => setSimulation({ ...simulation, scenario: e.target.value })}
              >
                {telemetryScenarios.map((scenario) => <option value={scenario} key={scenario}>{scenario}</option>)}
              </select>
            </label>
            <label>
              Policy
              <select value={policy} onChange={(e) => setPolicy(e.target.value)}>
                {opsPolicies.map((item) => <option value={item} key={item}>{item}</option>)}
              </select>
            </label>
            <label>Seed<input type="number" value={simulation.seed} onChange={(e) => setSimulation({ ...simulation, seed: Number(e.target.value) })} /></label>
            <label>Duration minutes<input type="number" value={simulation.duration_minutes} onChange={(e) => setSimulation({ ...simulation, duration_minutes: Number(e.target.value) })} /></label>
            <label>Step seconds<input type="number" value={simulation.step_seconds} onChange={(e) => setSimulation({ ...simulation, step_seconds: Number(e.target.value) })} /></label>
          </div>
          <button disabled={!selectedId} onClick={requestSimulatedOpsWorkflow}>Generate simulated workflow</button>
          {telemetry ? (
            <>
              <div className="lineage-grid telemetry-meta">
                <div><span className="label">Data kind</span><strong>{telemetry.data_kind}</strong></div>
                <div><span className="label">Generated at</span><strong>{formatDate(telemetry.generated_at)}</strong></div>
                <div><span className="label">Samples</span><strong>{telemetry.samples.length}</strong></div>
              </div>
              <div className="health-tile-grid">
                {latestSubsystemSamples.map((sample) => (
                  <div className="health-tile" key={sample.subsystem}>
                    <span className="label">{sample.subsystem}</span>
                    <strong>{formatNumber(sample.measurement_value, 2)} {sample.unit}</strong>
                    <Badge tone={sample.status === 'critical' ? 'stale' : sample.status === 'warning' ? 'warning' : 'fresh'}>
                      {sample.status} · {sample.measurement_name}
                    </Badge>
                  </div>
                ))}
              </div>
            </>
          ) : <p className="hint">Generate a deterministic stream to see simulated subsystem health tiles.</p>}
        </section>

        <section className="card event-card">
          <div className="section-eyebrow">Event workflow</div>
          <h2>Policy-driven event timeline</h2>
          {eventWorkflow ? (
            <>
              <div className="facts-grid">
                <div><span className="label">Selected policy</span><strong>{eventWorkflow.policy}</strong></div>
                <div><span className="label">Events</span><strong>{eventWorkflow.event_count}</strong></div>
                <div><span className="label">Scenario</span><strong>{eventWorkflow.scenario}</strong></div>
              </div>
              <p className="runbook-summary">{eventWorkflow.runbook_summary}</p>
              {eventWorkflow.events.length > 0 ? (
                <table>
                  <thead><tr><th>Time</th><th>Severity</th><th>Subsystem</th><th>Trigger</th><th>Operator check</th></tr></thead>
                  <tbody>
                    {eventWorkflow.events.map((event) => (
                      <tr key={event.event_id}>
                        <td>{formatDate(event.event_time)}</td>
                        <td><Badge tone={event.severity === 'critical' ? 'stale' : 'warning'}>{event.severity}</Badge></td>
                        <td>{event.subsystem}</td>
                        <td>{event.triggered_by}: {formatNumber(event.measurement_value, 2)} / threshold {formatNumber(event.threshold, 2)}</td>
                        <td>{event.recommended_operator_check}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <p className="hint">No warning or critical events generated for this scenario/policy.</p>}
            </>
          ) : <p className="hint">Run the simulated workflow to generate warning/critical events and a runbook-style summary.</p>}
        </section>

        <section className="card policy-card">
          <div className="section-eyebrow">Operations policy comparison</div>
          <h2>Alert timing and tradeoffs</h2>
          {policyComparison ? (
            <table>
              <thead><tr><th>Policy</th><th>Events</th><th>First warning</th><th>First critical</th><th>Top subsystem</th><th>Recommended action</th></tr></thead>
              <tbody>
                {Object.entries(policyComparison.policies).map(([name, summary]) => (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>{summary.event_count}</td>
                    <td>{formatDate(summary.first_warning_time)}</td>
                    <td>{formatDate(summary.first_critical_time)}</td>
                    <td>{summary.top_affected_subsystem ?? 'None'}</td>
                    <td>{summary.recommended_operator_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="hint">Comparison uses the same simulated stream across conservative, balanced, and relaxed policies.</p>}
        </section>

        <MissionMap position={position} contactWindows={contactWindows} station={station} />
      </div>
    </main>
  );
}
