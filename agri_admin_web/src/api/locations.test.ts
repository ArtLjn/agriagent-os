import { beforeEach, describe, expect, it, vi } from 'vitest';

import apiClient from './client';
import { searchLocations } from './locations';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient, true);

describe('locations api', () => {
  beforeEach(() => {
    mockedApiClient.get.mockReset();
  });

  it('搜索统一位置数据源并返回城市坐标', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            display_name: '苏州市虎丘区',
            lat: 31.3296,
            lon: 120.4342,
          },
        ],
      },
    });

    const result = await searchLocations('虎丘', 50);

    expect(mockedApiClient.get).toHaveBeenCalledWith('/locations/search', {
      params: { keyword: '虎丘', limit: 50 },
    });
    expect(result[0]).toMatchObject({
      display_name: '苏州市虎丘区',
      lat: 31.3296,
      lon: 120.4342,
    });
  });

  it('兼容 agri_backend_v2 返回的 name/full_name 字段，避免下拉显示 undefined', async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            name: '睢宁县',
            full_name: '江苏省徐州市睢宁县',
            province: '江苏省',
            city: '徐州市',
            lat: 33.9126,
            lon: 117.9414,
          },
        ],
      },
    });

    const result = await searchLocations('睢宁');

    expect(result[0].display_name).toBe('睢宁县');
  });
});
