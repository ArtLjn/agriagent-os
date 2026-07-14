import apiClient from './client';

export interface LocationOption {
  province?: string;
  city?: string;
  district?: string;
  name?: string;
  full_name?: string;
  display_name: string;
  adcode?: string;
  lat: number;
  lon: number;
  level?: string;
  coordinate_system?: string;
  coordinate_source?: string;
}

interface LocationSearchResponse {
  items?: LocationOption[];
  total?: number;
}

export async function searchLocations(q: string, limit: number = 20): Promise<LocationOption[]> {
  const res = await apiClient.get<LocationSearchResponse>('/locations/search', {
    params: { q, limit },
  });
  return res.data.items ?? [];
}
