import type { DayWeather } from '../../api/weather';

export type WeatherRiskLevel = 'good' | 'notice' | 'warning';

export interface WeatherViewDay {
  date: string;
  label: string;
  shortDate: string;
  temperatureRange: string;
  precipitationText: string;
  windText: string;
  riskLevel: WeatherRiskLevel;
  riskText: string;
  advice: string;
}

const codeTextMap: Record<number, string> = {
  0: '晴',
  1: '晴间多云',
  2: '多云',
  3: '阴',
  45: '雾',
  48: '雾',
  51: '小雨',
  53: '小雨',
  55: '中雨',
  61: '小雨',
  63: '中雨',
  65: '大雨',
  80: '阵雨',
  81: '阵雨',
  82: '强阵雨',
  95: '雷雨',
  96: '雷雨',
  99: '雷雨',
};

export function getWeatherLabel(day: DayWeather): string {
  if (day.weather_text) return day.weather_text;
  if (typeof day.weather_code === 'number') return codeTextMap[day.weather_code] ?? '多云';
  if (day.precipitation >= 10) return '雨';
  if (day.precipitation >= 1) return '阴';
  return '晴';
}

function getShortDate(date: string): string {
  const parts = date.split('-');
  if (parts.length < 3) return date;
  return `${Number(parts[1])}/${Number(parts[2])}`;
}

function getRisk(day: DayWeather): Pick<WeatherViewDay, 'riskLevel' | 'riskText' | 'advice'> {
  if (day.max_temp >= 35) {
    return {
      riskLevel: 'warning',
      riskText: '高温',
      advice: '避开午间作业，早晚补水并检查棚内通风。',
    };
  }

  if (day.precipitation >= 20) {
    return {
      riskLevel: 'warning',
      riskText: '强降水',
      advice: '提前清沟排水，暂停施肥和露天喷药。',
    };
  }

  if (day.wind_speed >= 17) {
    return {
      riskLevel: 'warning',
      riskText: '大风',
      advice: '加固棚膜、支架和滴灌管线，减少高处作业。',
    };
  }

  if (day.precipitation >= 2) {
    return {
      riskLevel: 'notice',
      riskText: '有雨',
      advice: '减少灌溉量，关注田间积水和病害风险。',
    };
  }

  if (day.max_temp >= 32) {
    return {
      riskLevel: 'notice',
      riskText: '偏热',
      advice: '保持土壤湿润，采收和浇水安排在早晚。',
    };
  }

  if (day.min_temp <= 3) {
    return {
      riskLevel: 'notice',
      riskText: '低温',
      advice: '夜间注意保温，幼苗和新移栽作物重点巡查。',
    };
  }

  return {
    riskLevel: 'good',
    riskText: '适宜',
    advice: '适合巡田、采收和常规田间管理。',
  };
}

export function buildWeatherView(days: DayWeather[]): WeatherViewDay[] {
  return days.map((day) => {
    const risk = getRisk(day);
    return {
      ...risk,
      date: day.date,
      label: getWeatherLabel(day),
      shortDate: getShortDate(day.date),
      temperatureRange: `${day.min_temp}°C / ${day.max_temp}°C`,
      precipitationText: `${day.precipitation} mm`,
      windText: `${day.wind_speed} m/s`,
    };
  });
}

export function buildWeatherSummary(days: DayWeather[], warnings: string[] = []): string {
  const viewDays = buildWeatherView(days);
  const warningDay = viewDays.find((day) => day.riskLevel === 'warning');
  const noticeDay = viewDays.find((day) => day.riskLevel === 'notice');
  const target = warningDay ?? noticeDay ?? viewDays[0];

  if (!target) return '暂无天气数据';
  if (warnings.length > 0) return warnings[0];

  return `${target.shortDate} ${target.label}，${target.temperatureRange}，${target.advice}`;
}
