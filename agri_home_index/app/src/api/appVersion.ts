import { type AppVersionResponse, normalizeAppVersion } from './appVersionCore';

const DEFAULT_API_BASE_URL = import.meta.env.DEV ? '' : 'https://api.farm.lllcnm.cn';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;

export {
  FALLBACK_APP_VERSION,
  FALLBACK_APK_DOWNLOAD_URL,
  extractDownloadUrl,
  formatVersionLabel,
  normalizeAppVersion,
} from './appVersionCore';

function buildApiUrl(path: string) {
  if (!API_BASE_URL) {
    return path;
  }
  return `${API_BASE_URL.replace(/\/$/, '')}${path}`;
}

export async function fetchAppVersion(fetcher: typeof fetch = fetch) {
  const response = await fetcher(buildApiUrl('/api/app/version'));
  if (!response.ok) {
    throw new Error(`获取 App 版本失败: ${response.status}`);
  }

  const data = (await response.json()) as AppVersionResponse;
  return normalizeAppVersion(data);
}
