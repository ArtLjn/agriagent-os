import { Platform, PermissionsAndroid } from 'react-native';
import Geolocation from '@react-native-community/geolocation';

export interface LocationCoords {
  latitude: number;
  longitude: number;
}

/**
 * 请求位置权限，成功返回 true。
 * Android 动态申请，iOS 由系统弹窗处理。
 */
export async function requestLocationPermission(): Promise<boolean> {
  if (Platform.OS === 'ios') {
    return new Promise((resolve) => {
      Geolocation.requestAuthorization(
        () => resolve(true),
        () => resolve(false),
      );
    });
  }

  try {
    const granted = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
      {
        title: '位置权限',
        message: '用于自动设置您所在城市，获取准确的天气预报',
        buttonNeutral: '稍后再问',
        buttonNegative: '拒绝',
        buttonPositive: '允许',
      },
    );
    return granted === PermissionsAndroid.RESULTS.GRANTED;
  } catch {
    return false;
  }
}

/**
 * 获取当前位置坐标。
 * 返回 null 表示获取失败。
 */
export function getCurrentPosition(): Promise<LocationCoords | null> {
  return new Promise((resolve) => {
    Geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      () => resolve(null),
      { timeout: 10000, maximumAge: 60000 },
    );
  });
}

/**
 * 完整定位流程：请求权限 → 获取坐标。
 * 失败返回 null。
 */
export async function detectLocation(): Promise<LocationCoords | null> {
  const hasPermission = await requestLocationPermission();
  if (!hasPermission) {
    return null;
  }
  return getCurrentPosition();
}
