export const FALLBACK_APK_DOWNLOAD_URL = '/downloads/farm-manager-latest.apk';

export type AppVersionResponse = {
  latest_version?: string;
  latest_version_code?: number;
  download_url?: string;
  changelog?: string;
  force_update?: boolean;
};

export type AppVersionInfo = {
  latestVersion: string;
  latestVersionCode: number;
  downloadUrl: string;
  changelog: string;
  forceUpdate: boolean;
};

export const FALLBACK_APP_VERSION: AppVersionInfo = {
  latestVersion: '0.0.0',
  latestVersionCode: 0,
  downloadUrl: FALLBACK_APK_DOWNLOAD_URL,
  changelog: '暂无更新说明',
  forceUpdate: false,
};

export function extractDownloadUrl(response: Pick<AppVersionResponse, 'download_url'>) {
  return response.download_url?.trim() || FALLBACK_APK_DOWNLOAD_URL;
}

export function normalizeAppVersion(response: AppVersionResponse): AppVersionInfo {
  const latestVersion = response.latest_version?.trim() || FALLBACK_APP_VERSION.latestVersion;
  const changelog = response.changelog?.trim() || FALLBACK_APP_VERSION.changelog;

  return {
    latestVersion,
    latestVersionCode: response.latest_version_code ?? FALLBACK_APP_VERSION.latestVersionCode,
    downloadUrl: extractDownloadUrl(response),
    changelog,
    forceUpdate: response.force_update ?? FALLBACK_APP_VERSION.forceUpdate,
  };
}

export function formatVersionLabel(version: string) {
  const text = version.trim();
  if (!text || text === FALLBACK_APP_VERSION.latestVersion) {
    return '版本获取中';
  }
  return text.startsWith('v') || text.startsWith('V') ? text : `v${text}`;
}
