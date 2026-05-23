import React from 'react';
import {View, Text, StyleSheet} from 'react-native';
import {Card} from './Card';
import {colors} from '../theme/colors';
import {spacing, fontSize} from '../theme/spacing';

interface WeatherDay {
  date: string;
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

export const WeatherCard: React.FC<WeatherCardProps> = ({data}) => {
  if (!data?.daily) {
    return (
      <Card>
        <Text style={styles.title}>天气</Text>
        <Text style={styles.empty}>暂无天气数据</Text>
      </Card>
    );
  }

  const {time, temperature_2m_max, temperature_2m_min, precipitation_sum} =
    data.daily;
  const days: WeatherDay[] = time.slice(0, 3).map((t, i) => ({
    date: t.slice(5),
    maxTemp: temperature_2m_max[i],
    minTemp: temperature_2m_min[i],
    precipitation: precipitation_sum[i],
  }));

  return (
    <Card>
      <Text style={styles.title}>未来3天天气</Text>
      <View style={styles.row}>
        {days.map(d => (
          <View key={d.date} style={styles.dayItem}>
            <Text style={styles.dayDate}>{d.date}</Text>
            <Text style={styles.dayTemp}>
              {d.minTemp}° ~ {d.maxTemp}°
            </Text>
            {d.precipitation > 0 && (
              <Text style={styles.dayRain}>雨 {d.precipitation}mm</Text>
            )}
          </View>
        ))}
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  title: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  empty: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  dayItem: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  dayDate: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  dayTemp: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
  },
  dayRain: {
    fontSize: fontSize.sm,
    color: colors.info,
    marginTop: spacing.xs,
  },
});
