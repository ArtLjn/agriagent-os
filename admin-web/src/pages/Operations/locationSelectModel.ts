import type { DefaultOptionType } from 'antd/es/select';
import type { LocationOption } from '../../api/locations';
import type { UserSettings } from '../../api/operations';

type SettingsLocationFields = {
  default_city: string;
  default_lat: number;
  default_lon: number;
};

export interface LocationSelectOption extends DefaultOptionType {
  value: string;
  label: string;
  location: LocationOption;
}

export function buildLocationSelectOptions(locations: LocationOption[]): LocationSelectOption[] {
  return locations.map((location) => ({
    value: location.display_name,
    label: buildLocationOptionLabel(location),
    location,
  }));
}

export function buildSettingsLocationFields(location: LocationOption): SettingsLocationFields {
  return {
    default_city: location.display_name,
    default_lat: location.lat,
    default_lon: location.lon,
  };
}

export function buildCurrentLocationOption(settings: Pick<UserSettings, 'default_city' | 'default_lat' | 'default_lon'>): LocationOption | null {
  if (!settings.default_city || settings.default_lat == null || settings.default_lon == null) {
    return null;
  }
  return {
    display_name: settings.default_city,
    lat: settings.default_lat,
    lon: settings.default_lon,
  };
}

function buildLocationOptionLabel(location: LocationOption): string {
  const parents = [location.province, location.city].filter(Boolean).join(' / ');
  return parents ? `${location.display_name} · ${parents}` : location.display_name;
}
