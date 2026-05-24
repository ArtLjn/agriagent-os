import React from 'react';
import {View, Text, StyleSheet} from 'react-native';
import {Card} from './Card';
import {colors} from '../theme/colors';
import {spacing, fontSize, borderRadius} from '../theme/spacing';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

interface WeatherDay {
  date: string;
  weekday: string;
  maxTemp: number;
  minTemp: number;
  precipitation: number;
}

interface WeatherCardProps {
  data: {
    daily: {
      time: string[];
      temperature_2m_max: number[];
      temperature_2m_min: number[];
      precipitation_sum: number[];
    };
  } | null;
}

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

const getWeatherIcon = (precipitation: number, maxTemp: number) => {
  if (precipitation > 5) return 'weather-pouring';
  if (precipitation > 0) return 'weather-rainy';
  if (maxTemp > 30) return 'weather-sunny';
  if (maxTemp < 10) return 'weather-snowy';
  return 'weather-partly-cloudy';
};

const getWeatherLabel = (precipitation: number, maxTemp: number) => {
  if (precipitation > 10) return '大雨';
  if (precipitation > 5) return '中雨';
  if (precipitation > 0) return '小雨';
  if (maxTemp > 32) return '炎热';
  if (maxTemp > 28) return '晴热';
  if (maxTemp < 5) return '寒冷';
  if (maxTemp < 12) return '凉爽';
  return '多云';
};

const getWeatherColor = (precipitation: number) => {
  if (precipitation > 5) return '#60A5FA';
  if (precipitation > 0) return '#93C5FD';
  return '#FBBF24';
};

export const WeatherCard: React.FC<WeatherCardProps> = ({data}) => {
  if (!data?.daily) {
    return (
      <Card>
        <View style={styles.header}>
          <Icon name="weather-partly-cloudy" size={20} color={colors.primary} />
          <Text style={styles.headerTitle}>天气</Text>
        </View>
        <Text style={styles.empty}>暂无天气数据</Text>
      </Card>
    );
  }

  const {time, temperature_2m_max, temperature_2m_min, precipitation_sum} =
    data.daily;

  const days: WeatherDay[] = time.slice(0, 3).map((t, i) => {
    const d = new Date(t);
    const isToday = i === 0;
    return {
      date: isToday ? '今天' : `${d.getMonth() + 1}/${d.getDate()}`,
      weekday: isToday ? '今天' : WEEKDAYS[d.getDay()],
      maxTemp: Math.round(temperature_2m_max[i]),
      minTemp: Math.round(temperature_2m_min[i]),
      precipitation: precipitation_sum[i],
    };
  });

  const today = days[0];
  const todayIcon = getWeatherIcon(today.precipitation, today.maxTemp);
  const todayLabel = getWeatherLabel(today.precipitation, today.maxTemp);
  const todayIconColor = getWeatherColor(today.precipitation);

  return (
    <Card padding="none" elevated={true} style={styles.cardOverride}>
      {/* Top section - current weather */}
      <View style={styles.topSection}>
        {/* Decorative circles */}
        <View style={[styles.decoCircle, styles.decoCircle1]} />
        <View style={[styles.decoCircle, styles.decoCircle2]} />

        <View style={styles.topContent}>
          <View style={styles.topLeft}>
            <View style={styles.locationRow}>
              <Icon name="map-marker" size={14} color="rgba(255,255,255,0.8)" />
              <Text style={styles.locationText}>本地天气</Text>
            </View>
            <Text style={styles.bigTemp}>
              {today.minTemp}° ~ {today.maxTemp}°
            </Text>
            <Text style={styles.weatherLabel}>{todayLabel}</Text>
          </View>
          <View style={styles.topRight}>
            <Icon name={todayIcon} size={56} color={todayIconColor} />
          </View>
        </View>
      </View>

      {/* Bottom section - forecast */}
      <View style={styles.bottomSection}>
        {days.map(d => {
          const iconName = getWeatherIcon(d.precipitation, d.maxTemp);
          const iconColor = getWeatherColor(d.precipitation);
          return (
            <View key={d.date} style={styles.dayItem}>
              <Text style={styles.dayDate}>{d.date}</Text>
              <Text style={styles.dayWeekday}>{d.weekday}</Text>
              <Icon
                name={iconName}
                size={24}
                color={iconColor}
                style={styles.dayIcon}
              />
              <View style={styles.tempRow}>
                <Text style={styles.tempMax}>{d.maxTemp}°</Text>
                <Text style={styles.tempMin}>{d.minTemp}°</Text>
              </View>
              {d.precipitation > 0 && (
                <View style={styles.rainBadge}>
                  <Icon name="water" size={10} color={colors.info} />
                  <Text style={styles.rainText}>{d.precipitation}mm</Text>
                </View>
              )}
            </View>
          );
        })}
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  cardOverride: {
    overflow: 'hidden',
  },
  topSection: {
    backgroundColor: '#1E3A5F',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xl,
    position: 'relative',
    overflow: 'hidden',
  },
  decoCircle: {
    position: 'absolute',
    borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.04)',
  },
  decoCircle1: {
    width: 180,
    height: 180,
    top: -60,
    right: -40,
  },
  decoCircle2: {
    width: 120,
    height: 120,
    bottom: -30,
    left: -20,
  },
  topContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  topLeft: {
    flex: 1,
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: spacing.sm,
  },
  locationText: {
    fontSize: fontSize.sm,
    color: 'rgba(255,255,255,0.8)',
  },
  bigTemp: {
    fontSize: fontSize.xxxl,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: -1,
  },
  weatherLabel: {
    fontSize: fontSize.md,
    color: 'rgba(255,255,255,0.7)',
    marginTop: 2,
  },
  topRight: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  bottomSection: {
    flexDirection: 'row',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.surface,
  },
  dayItem: {
    flex: 1,
    alignItems: 'center',
  },
  dayDate: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  dayWeekday: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    marginTop: 1,
  },
  dayIcon: {
    marginVertical: spacing.sm,
  },
  tempRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  tempMax: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
  },
  tempMin: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
  },
  rainBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
    backgroundColor: colors.infoLight,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
    gap: 2,
  },
  rainText: {
    fontSize: fontSize.xs,
    color: colors.info,
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  headerTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
  },
  empty: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    textAlign: 'center',
    paddingVertical: spacing.lg,
  },
});
