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
      params: { q: '虎丘', limit: 50 },
    });
    expect(result[0]).toMatchObject({
      display_name: '苏州市虎丘区',
      lat: 31.3296,
      lon: 120.4342,
    });
  });
});
