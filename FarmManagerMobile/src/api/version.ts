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

import { Platform, NativeModules } from "react-native";

/** 当前应用版本名，与 build.gradle versionName 同步。 */
export const APP_VERSION = "1.0.4";

/** 当前应用构建号，与 build.gradle versionCode + VERSION 文件同步。
 *  发版时务必同步更新此值与 build.gradle 中的 versionCode。
 */
export const APP_BUILD_NUMBER = 5;

/** 从原生层获取应用 build 号（优先），失败时回退到 JS 常量。 */
export async function getAppVersionCode(): Promise<number> {
  try {
    // Android: BuildConfig.VERSION_CODE
    if (Platform.OS === "android" && NativeModules.AppInfo) {
      const code = await NativeModules.AppInfo.getVersionCode?.();
      if (typeof code === "number") return code;
    }
  } catch {
    // ignore
  }
  return APP_BUILD_NUMBER;
}
