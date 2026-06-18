import type {
  ContactWindowListResponse,
  OpsPolicyComparisonResponse,
  SatelliteListResponse,
  SatellitePositionResponse,
  SatelliteRecord,
  SimulatedEventWorkflowResponse,
  SimulatedTelemetryResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}${body ? ` — ${body}` : ''}`);
  }
  return response.json() as Promise<T>;
}

export function apiBaseUrl(): string {
  return API_BASE_URL;
}

export function checkHealth(): Promise<{ status: string }> {
  return requestJson('/health');
}

export function ingestCelesTrak(force = false): Promise<SatelliteListResponse> {
  return requestJson(`/ingest/celestrak${force ? '?force=true' : ''}`, { method: 'POST' });
}

export function listSatellites(): Promise<SatelliteListResponse> {
  return requestJson('/satellites');
}

export function getSatellite(noradCatId: number): Promise<SatelliteRecord> {
  return requestJson(`/satellites/${noradCatId}`);
}

export function getPosition(noradCatId: number, atIso: string): Promise<SatellitePositionResponse> {
  const query = new URLSearchParams({ at: atIso });
  return requestJson(`/satellites/${noradCatId}/position?${query.toString()}`);
}

export interface ContactWindowParams {
  latitude_deg: number;
  longitude_deg: number;
  altitude_m: number;
  ground_station_name: string;
  start: string;
  end: string;
  step_seconds: number;
  min_elevation_deg: number;
}

export interface SimulationParams {
  scenario: string;
  seed: number;
  duration_minutes: number;
  step_seconds: number;
}

export function getSimulatedTelemetry(
  noradCatId: number,
  params: SimulationParams,
): Promise<SimulatedTelemetryResponse> {
  const query = new URLSearchParams({
    scenario: params.scenario,
    seed: String(params.seed),
    duration_minutes: String(params.duration_minutes),
    step_seconds: String(params.step_seconds),
  });
  return requestJson(`/satellites/${noradCatId}/telemetry/simulated?${query.toString()}`);
}

export function getSimulatedEvents(
  noradCatId: number,
  params: SimulationParams & { policy: string },
): Promise<SimulatedEventWorkflowResponse> {
  const query = new URLSearchParams({
    scenario: params.scenario,
    policy: params.policy,
    seed: String(params.seed),
    duration_minutes: String(params.duration_minutes),
    step_seconds: String(params.step_seconds),
  });
  return requestJson(`/satellites/${noradCatId}/events/simulated?${query.toString()}`);
}

export function getOpsPolicyComparison(
  noradCatId: number,
  params: SimulationParams,
): Promise<OpsPolicyComparisonResponse> {
  const query = new URLSearchParams({
    scenario: params.scenario,
    seed: String(params.seed),
    duration_minutes: String(params.duration_minutes),
    step_seconds: String(params.step_seconds),
  });
  return requestJson(`/satellites/${noradCatId}/ops-policy-comparison?${query.toString()}`);
}

export function getContactWindows(
  noradCatId: number,
  params: ContactWindowParams,
): Promise<ContactWindowListResponse> {
  const query = new URLSearchParams({
    latitude_deg: String(params.latitude_deg),
    longitude_deg: String(params.longitude_deg),
    altitude_m: String(params.altitude_m),
    ground_station_name: params.ground_station_name,
    start: params.start,
    end: params.end,
    step_seconds: String(params.step_seconds),
    min_elevation_deg: String(params.min_elevation_deg),
  });
  return requestJson(`/satellites/${noradCatId}/contact-windows?${query.toString()}`);
}
