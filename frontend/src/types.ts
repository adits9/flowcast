export type Category = "dining" | "fitness" | "study";
export type CrowdStatus = "quiet" | "moderate" | "busy" | "closed" | "unknown";
export interface ForecastPoint {
  at: string;
  minutes_ahead: number;
  occupancy: number;
  percent: number;
  wait_minutes: number;
  lower_percent: number;
  upper_percent: number;
  is_open: boolean;
}
export interface Location {
  id: string;
  name: string;
  category: Category;
  building: string;
  description: string;
  capacity: number;
  occupancy: number;
  percent: number;
  available: number;
  walk_minutes: number;
  opens: number;
  closes: number;
  is_open: boolean;
  status: CrowdStatus;
  tags: string[];
  x: number;
  y: number;
  wait_minutes: number | null;
  updated_at: string;
  source: string;
  forecast: ForecastPoint[];
  stale: boolean;
}
export interface Overview {
  campus: string;
  timezone: string;
  demo_mode: boolean;
  updated_at: string;
  checkin_expiry_hours: number;
  weather: {
    temperature_c: number;
    rain_mm: number;
    description: string;
    source: string;
    stale: boolean;
  };
  events: {
    id: number;
    title: string;
    venue: string;
    starts_at: string;
    ends_at: string;
  }[];
  locations: Location[];
  model: {
    source: string;
    algorithm?: string;
    occupancy_mae_pp?: number;
    wait_mae_minutes?: number;
    training_rows?: number;
    validation_rows?: number;
    trained_at?: string;
    features: string[];
  };
}
export interface Alert {
  location_id: string;
  location_name: string;
  kind: "quiet" | "busy";
  at: string;
  message: string;
}
export interface Checkin {
  location_id: string | null;
  expires_at: string | null;
}
