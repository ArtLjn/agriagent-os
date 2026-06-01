import { apiClient } from "./client";

let _deviceInfo: typeof import("react-native-device-info") | null = null;

try {
  _deviceInfo = require("react-native-device-info").default;
} catch {
  _deviceInfo = null;
}

function di() {
  return _deviceInfo;
}

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

/** 当前应用版本名（运行时从原生层读取，与 build.gradle versionName 同步）。 */
export const APP_VERSION: string = (() => {
  try {
    return di()?.getVersion() ?? "1.0.0";
  } catch {
    return "1.0.0";
  }
})();

/** 当前应用构建号（运行时从原生层读取，与 build.gradle versionCode 同步）。 */
export const APP_BUILD_NUMBER: number = (() => {
  try {
    const build = di()?.getBuildNumber() ?? "1";
    const code = parseInt(build, 10);
    return isNaN(code) ? 1 : code;
  } catch {
    return 1;
  }
})();

/** 获取应用 build 号。优先从原生层读取，失败时回退到 JS 常量。 */
export async function getAppVersionCode(): Promise<number> {
  try {
    const build = di()?.getBuildNumber();
    if (build) {
      const code = parseInt(build, 10);
      if (!isNaN(code)) return code;
    }
  } catch {
    // ignore
  }
  return APP_BUILD_NUMBER;
}
