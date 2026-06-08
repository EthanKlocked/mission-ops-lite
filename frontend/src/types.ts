export type FreshnessStatus = 'fresh' | 'stale' | 'unknown';

export interface DataSource {
  name: string;
  url: string;
  type: 'real_public_orbit_data';
}

export interface SatelliteRecord {
  object_name: string;
  object_id: string | null;
  norad_cat_id: number;
  epoch: string | null;
  mean_motion: number | null;
  inclination: number | null;
  eccentricity: number | null;
  source: DataSource;
  ingested_at: string;
  epoch_age_hours: number | null;
  freshness_status: FreshnessStatus;
  raw_record_available: boolean;
}

export interface SatelliteListResponse {
  count: number;
  items: SatelliteRecord[];
}

export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

export interface ApproximateGeodeticPosition {
  latitude_deg: number;
  longitude_deg: number;
  altitude_km: number;
}

export interface SatellitePositionResponse {
  object_name: string;
  norad_cat_id: number;
  source: DataSource;
  source_epoch: string;
  requested_at: string;
  time_delta_minutes_from_epoch: number;
  propagator: string;
  coordinate_frame: string;
  position_km: Vector3;
  velocity_km_s: Vector3;
  approximate_geodetic: ApproximateGeodeticPosition;
  freshness_status: FreshnessStatus;
  epoch_age_hours: number | null;
  is_approximate: boolean;
  limitations: string[];
}

export interface GroundStation {
  name: string;
  latitude_deg: number;
  longitude_deg: number;
  altitude_m: number;
}

export interface ContactWindow {
  start: string;
  end: string;
  peak_at: string;
  duration_seconds: number;
  max_elevation_deg: number;
}

export interface ContactWindowListResponse {
  object_name: string;
  norad_cat_id: number;
  source: DataSource;
  source_epoch: string;
  start: string;
  end: string;
  ground_station: GroundStation;
  min_elevation_deg: number;
  step_seconds: number;
  propagator: string;
  is_approximate: boolean;
  freshness_status: FreshnessStatus;
  epoch_age_hours: number | null;
  count: number;
  windows: ContactWindow[];
  limitations: string[];
}
