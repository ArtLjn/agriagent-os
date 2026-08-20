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

interface LocationSearchItem extends Omit<LocationOption, 'display_name'> {
  display_name?: string;
}

interface LocationSearchResponse {
  items?: LocationSearchItem[];
  total?: number;
}

function normalizeLocation(item: LocationSearchItem): LocationOption | null {
  const displayName = item.display_name?.trim() || item.name?.trim() || item.full_name?.trim();
  if (!displayName) return null;
  return { ...item, display_name: displayName };
}

export async function searchLocations(q: string, limit: number = 20): Promise<LocationOption[]> {
  const res = await apiClient.get<LocationSearchResponse>('/locations/search', {
    params: { keyword: q, limit },
  });
  return (res.data.items ?? [])
    .map(normalizeLocation)
    .filter((item): item is LocationOption => item !== null);
}
