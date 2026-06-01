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

import { Platform } from "react-native";

/** 当前应用版本名，与 build.gradle versionName 同步。 */
export const APP_VERSION = "1.0.3";

/** 当前应用构建号，与 build.gradle versionCode + VERSION 文件同步。 */
export const APP_BUILD_NUMBER = 5;
