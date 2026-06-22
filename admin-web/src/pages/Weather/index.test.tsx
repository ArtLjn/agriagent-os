import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getForecast, searchLocations } from '../../api/weather';
import Weather from './index';

vi.mock('../../api/weather', () => ({
  getForecast: vi.fn(),
  searchLocations: vi.fn(),
}));

const mockedGetForecast = vi.mocked(getForecast);
const mockedSearchLocations = vi.mocked(searchLocations);

describe('Weather 页面', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedSearchLocations.mockResolvedValue([]);
  });

  it('长官方预警独立展示，不占用农事摘要标题', async () => {
    mockedGetForecast.mockResolvedValue({
      location: '苏州市虎丘区',
      provider: 'qweather',
      days: [
        {
          date: '2026-06-22',
          max_temp: 26,
          min_temp: 22,
          precipitation: 18.7,
          wind_speed: 3,
          weather_text: '雨',
        },
      ],
      warnings: [
        '吴江区气象台发布暴雨黄色预警[Ⅲ级/较重]: 吴江区气象台2026年6月22日15时35分升级发布暴雨黄色预警信号：预计今天下午到夜里我区大部分街道（镇）将出现1小时50毫米及以上的强降水。',
        '吴中区气象台发布暴雨黄色预警[Ⅲ级/较重]: 吴中区气象台2026年06月22日15时17分升级发布暴雨黄色预警信号：预计未来2小时我区强降雨仍将持续。',
        '吴江区气象台发布强对流黄色预警[Ⅲ级/较重]: 预计未来6小时我区大部分街道（镇）将出现雷电活动。',
        '苏州市气象台发布大风蓝色预警[Ⅳ级/一般]: 预计今天下午到上半夜我市大部分街道（镇）将出现阵风。',
      ],
    });

    render(<Weather />);

    await waitFor(() => {
      expect(screen.getByText(/6\/22 雨/)).toBeInTheDocument();
    });

    expect(screen.getByLabelText('官方天气预警')).toBeInTheDocument();
    expect(screen.getByText(/吴江区气象台发布暴雨黄色预警/)).toBeInTheDocument();
    expect(screen.getByText('另有 1 条官方预警')).toBeInTheDocument();
    expect(screen.queryByText(/苏州市气象台发布大风蓝色预警/)).not.toBeInTheDocument();
  });
});
