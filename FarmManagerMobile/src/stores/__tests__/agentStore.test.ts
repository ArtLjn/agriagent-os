import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAgentStore } from '../agentStore';

jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  multiGet: jest.fn(),
  multiSet: jest.fn(),
  multiRemove: jest.fn(),
  clear: jest.fn(),
  getAllKeys: jest.fn(),
}));

jest.mock('../../api/client', () => ({
  agentApi: {
    streamChat: jest.fn(),
    getDailyAdvice: jest.fn(),
    refreshAdvice: jest.fn(),
    generateReport: jest.fn(),
    getReportHistory: jest.fn(),
  },
  weatherApi: {
    getForecast: jest.fn(),
  },
}));

const { weatherApi } = require('../../api/client');

const MOCK_WEATHER_DATA = {
  daily: {
    time: ['2026-05-27', '2026-05-28', '2026-05-29'],
    temperature_2m_max: [28, 30, 25],
    temperature_2m_min: [18, 20, 16],
    precipitation_sum: [0, 2, 8],
  },
};

beforeEach(() => {
  jest.clearAllMocks();
  useAgentStore.setState({
    messages: [],
    dailyAdvice: null,
    report: null,
    weather: null,
    loading: false,
    error: null,
    cityName: '苏州',
    cityLat: 31.3,
    cityLon: 120.62,
    reports: [],
    pendingAction: null,
  });
});

describe('loadCachedWeather', () => {
  it('有缓存时立即设置 weather state，不设 loading', async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValueOnce(
      JSON.stringify(MOCK_WEATHER_DATA)
    );

    await useAgentStore.getState().loadCachedWeather();

    expect(AsyncStorage.getItem).toHaveBeenCalledWith(
      'weather_cache_苏州'
    );
    expect(useAgentStore.getState().weather).toEqual(MOCK_WEATHER_DATA);
    expect(useAgentStore.getState().loading).toBe(false);
  });

  it('无缓存时不修改 weather state', async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValueOnce(null);

    await useAgentStore.getState().loadCachedWeather();

    expect(useAgentStore.getState().weather).toBeNull();
  });

  it('AsyncStorage 异常时不崩溃', async () => {
    (AsyncStorage.getItem as jest.Mock).mockRejectedValueOnce(
      new Error('读取失败')
    );

    await expect(
      useAgentStore.getState().loadCachedWeather()
    ).resolves.not.toThrow();
  });
});

describe('fetchWeather', () => {
  it('成功后将数据写入 AsyncStorage 并更新 state', async () => {
    weatherApi.getForecast.mockResolvedValueOnce({
      data: MOCK_WEATHER_DATA,
    });

    await useAgentStore.getState().fetchWeather(3);

    expect(useAgentStore.getState().weather).toEqual(MOCK_WEATHER_DATA);
    expect(AsyncStorage.setItem).toHaveBeenCalledWith(
      'weather_cache_苏州',
      JSON.stringify(MOCK_WEATHER_DATA)
    );
    expect(useAgentStore.getState().loading).toBe(false);
  });

  it('失败时不覆盖已有的 weather 数据', async () => {
    useAgentStore.setState({ weather: MOCK_WEATHER_DATA });
    weatherApi.getForecast.mockRejectedValueOnce(new Error('网络错误'));

    await useAgentStore.getState().fetchWeather(3);

    expect(useAgentStore.getState().weather).toEqual(MOCK_WEATHER_DATA);
    expect(useAgentStore.getState().error).toBe('网络错误');
  });
});

describe('setCity', () => {
  it('切换城市后自动加载缓存并发起网络请求', async () => {
    (AsyncStorage.getItem as jest.Mock).mockResolvedValueOnce(null);
    weatherApi.getForecast.mockResolvedValueOnce({
      data: MOCK_WEATHER_DATA,
    });

    await useAgentStore.getState().setCity('宁德', 26.66, 119.53);

    expect(useAgentStore.getState().cityName).toBe('宁德');
    expect(AsyncStorage.getItem).toHaveBeenCalledWith('weather_cache_宁德');
    expect(weatherApi.getForecast).toHaveBeenCalledTimes(1);
  });
});
