import { apiClient } from "./client";

export interface VersionInfo {
  latest_version: string;
  latest_version_code: number;
  download_url: string;
  changelog: string;
  force_update: boolean;
}

export const versionApi = {
  check: (currentVersionCode: number) =>
    apiClient.get<VersionInfo>("/api/app/version", {
      params: { current_version_code: currentVersionCode },
    }),
};

/** 当前应用版本名，与 android/app/build.gradle versionName 同步。 */
export const APP_VERSION = "1.2.5";

/** 当前应用构建号，与 android/app/build.gradle versionCode 同步。 */
export const APP_BUILD_NUMBER = 11;

/** 获取应用 build 号。 */
export async function getAppVersionCode(): Promise<number> {
  return APP_BUILD_NUMBER;
}
