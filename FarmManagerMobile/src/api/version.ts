import { apiClient } from './client';

export interface VersionInfo {
  latest_version: string;
  latest_version_code: number;
  download_url: string;
  changelog: string;
  force_update: boolean;
}

export const versionApi = {
  check: (currentVersionCode: number) =>
    apiClient.get<VersionInfo>('/app/version', {
      params: { current_version_code: currentVersionCode },
    }),
};

/** 当前应用版本号，与 VERSION 文件及 build.gradle 保持一致。 */
const APP_VERSION_CODE = 3;

export async function getAppVersionCode(): Promise<number> {
  return APP_VERSION_CODE;
}
