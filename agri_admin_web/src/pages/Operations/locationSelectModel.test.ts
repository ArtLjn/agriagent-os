import { describe, expect, it } from 'vitest';

import {
  buildCurrentLocationOption,
  buildLocationSelectOptions,
  buildSettingsLocationFields,
} from './locationSelectModel';
import type { LocationOption } from '../../api/locations';

const huqiu: LocationOption = {
  province: '江苏省',
  city: '苏州市',
  district: '虎丘区',
  display_name: '苏州市虎丘区',
  lat: 31.3296,
  lon: 120.4342,
};

describe('locationSelectModel', () => {
  it('把位置搜索结果转换成可搜索下拉选项', () => {
    const options = buildLocationSelectOptions([huqiu]);

    expect(options).toEqual([
      {
        label: '苏州市虎丘区 · 江苏省 / 苏州市',
        value: '苏州市虎丘区',
        location: huqiu,
      },
    ]);
  });

  it('选择城市后生成默认城市和经纬度表单字段', () => {
    expect(buildSettingsLocationFields(huqiu)).toEqual({
      default_city: '苏州市虎丘区',
      default_lat: 31.3296,
      default_lon: 120.4342,
    });
  });

  it('用当前设置补齐初始选项，避免已保存城市不在搜索结果中时丢失展示', () => {
    expect(
      buildCurrentLocationOption({
        default_city: '苏州市虎丘区',
        default_lat: 31.3296,
        default_lon: 120.4342,
      }),
    ).toEqual({
      display_name: '苏州市虎丘区',
      lat: 31.3296,
      lon: 120.4342,
    });
  });
});
