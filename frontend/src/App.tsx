import { ReactNode, useEffect, useMemo, useState } from 'react';
import {
  apiBaseUrl,
  checkHealth,
  getContactWindows,
  getPosition,
  getSatellite,
  ingestCelesTrak,
  listSatellites,
  type ContactWindowParams,
} from './api';
import type {
  ContactWindowListResponse,
  SatelliteListResponse,
  SatellitePositionResponse,
  SatelliteRecord,
} from './types';

const ISS_NORAD_ID = 25544;

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

function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'fresh' | 'stale' | 'neutral' }) {
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

export default function App() {
  const [health, setHealth] = useState('checking');
  const [satellites, setSatellites] = useState<SatelliteRecord[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selected, setSelected] = useState<SatelliteRecord | null>(null);
  const [search, setSearch] = useState('');
  const [positionAt, setPositionAt] = useState(toDatetimeLocalValue(new Date()));
  const [position, setPosition] = useState<SatellitePositionResponse | null>(null);
  const [contactWindows, setContactWindows] = useState<ContactWindowListResponse | null>(null);
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

  const filteredSatellites = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const list = normalized
      ? satellites.filter((item) =>
          `${item.object_name} ${item.norad_cat_id} ${item.object_id ?? ''}`.toLowerCase().includes(normalized),
        )
      : satellites;
    return list.slice(0, 80);
  }, [satellites, search]);

  async function loadCatalog() {
    setBusy('Loading catalog');
    setError(null);
    try {
      const response = await listSatellites();
      applySatelliteList(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  function applySatelliteList(response: SatelliteListResponse) {
    setSatellites(response.items);
    if (response.items.length > 0) {
      const preferred = response.items.find((item) => item.norad_cat_id === ISS_NORAD_ID) ?? response.items[0];
      setSelectedId((current) => current ?? preferred.norad_cat_id);
    }
  }

  async function refreshIngest(force: boolean) {
    setBusy(force ? 'Force refreshing CelesTrak data' : 'Refreshing CelesTrak data');
    setError(null);
    try {
      const response = await ingestCelesTrak(force);
      applySatelliteList(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
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

  useEffect(() => {
    checkHealth()
      .then((response) => setHealth(response.status))
      .catch(() => setHealth('offline'));
    void loadCatalog();
  }, []);

  useEffect(() => {
    if (selectedId === null) {
      setSelected(null);
      return;
    }
    getSatellite(selectedId)
      .then(setSelected)
      .catch(() => setSelected(satellites.find((item) => item.norad_cat_id === selectedId) ?? null));
    setPosition(null);
    setContactWindows(null);
  }, [selectedId, satellites]);

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <div className="section-eyebrow">Mission Ops Lite</div>
          <h1>Operator dashboard for public orbit-derived planning</h1>
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

      {error ? <div className="error-banner">{error}</div> : null}
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
            {filteredSatellites.length === 0 ? <p className="hint">No catalog rows loaded yet. Run ingest first.</p> : null}
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
          {contactWindows ? (
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
          ) : <p className="hint">Contact windows are sampled estimates and are not stored by the backend.</p>}
        </section>

        <MissionMap position={position} contactWindows={contactWindows} station={station} />
      </div>
    </main>
  );
}
