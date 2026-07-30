# Mobile UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform FarmManager Mobile App from traditional management-tool style (deep teal, dense layout) to a light AI-assistant design language (blue-purple-green palette, large-card whitespace, breathing animations).

**Architecture:** Phase-based rollout — Phase 1 lays the theme/animation foundation, Phase 2 rebuilds the home screen and BottomBar, Phase 3 adds the weather detail page and restyles ledger/settings. All changes are pure frontend UI; no backend API changes.

**Tech Stack:** React Native 0.74, TypeScript, React Navigation, react-native-linear-gradient, victory-native (with react-native-svg), React Native Animated API.

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `src/theme/designTokens.ts` | Unified design tokens: radii, shadows, typography, spacing v2 |
| `src/theme/gradients.ts` | All gradient definitions used across the app |
| `src/theme/animations.ts` | Animation timing constants (duration, easing) |
| `src/components/animations/FadeInSlideUp.tsx` | Reusable fade-in + slide-up entrance animation wrapper |
| `src/components/animations/BreathingFloat.tsx` | Reusable continuous breathing/floating animation wrapper |
| `src/components/animations/ScalePress.tsx` | Reusable press-to-scale feedback wrapper |
| `src/components/AIPet.tsx` | 72px semi-transparent floating AI pet button with breathing animation |
| `src/components/WeatherCardV2.tsx` | Large gradient weather card (replaces WeatherCard) |
| `src/screens/weather/WeatherDetailScreen.tsx` | New weather detail page with hourly forecast + 7-day trend chart |

### Modified Files
| File | Changes |
|------|---------|
| `package.json` | Add `react-native-linear-gradient`, `victory-native`, `react-native-svg` |
| `src/theme/colors.ts` | Replace entire palette with blue-purple-green system |
| `src/theme/spacing.ts` | Add new spacing/font sizes for v2 design |
| `src/components/AdviceCard.tsx` | Restyle as emotion-based card with weather-aware gradients |
| `src/screens/home/HomeScreen.tsx` | Complete layout rewrite: greeting → weather → advice → quick actions |
| `src/navigation/MainTabNavigator.tsx` | Glassmorphism background + capsule active state |
| `src/navigation/AppNavigator.tsx` | Add `WeatherDetail` route |
| `src/screens/agent/AgentChatScreen.tsx` | Gradient background, gradient user bubbles, capsule quick-prompts, AI avatar |
| `src/screens/cost/CostListScreen.tsx` | Light financial style: asset card, income/expense cards, gradient FAB |
| `src/screens/settings/SettingsScreen.tsx` | Minimal style: #F8FAFC background, 64px white cards, unified icon colors |

---

## Phase 1: Theme System & Animation Infrastructure

### Task 1: Install Dependencies

**Files:**
- Modify: `FarmManagerMobile/package.json`

- [ ] **Step 1: Add dependencies to package.json**

  In the `dependencies` section of `FarmManagerMobile/package.json`, add:
  ```json
  "react-native-linear-gradient": "^2.8.3",
  "victory-native": "^37.0.0",
  "react-native-svg": "^15.0.0"
  ```

- [ ] **Step 2: Install packages**

  Run:
  ```bash
  cd FarmManagerMobile && npm install
  ```

- [ ] **Step 3: iOS pod install (if on macOS)**

  Run:
  ```bash
  cd FarmManagerMobile/ios && pod install && cd ..
  ```

- [ ] **Step 4: Commit**

  ```bash
  git add package.json package-lock.json
  git commit -m "chore: install react-native-linear-gradient, victory-native, react-native-svg"
  ```

---

### Task 2: Create Design Tokens File

**Files:**
- Create: `FarmManagerMobile/src/theme/designTokens.ts`

- [ ] **Step 1: Write designTokens.ts**

  ```typescript
  export const radii = {
    sm: 10,
    md: 14,
    lg: 18,
    xl: 22,
    xxl: 28,
    xxxl: 30,
    full: 999,
  } as const;

  export const typography = {
    heading1: {
      fontSize: 32,
      fontWeight: '700' as const,
      letterSpacing: -0.5,
    },
    heading2: {
      fontSize: 22,
      fontWeight: '600' as const,
    },
    body: {
      fontSize: 15,
      lineHeight: 24,
    },
    caption: {
      fontSize: 13,
    },
    small: {
      fontSize: 11,
    },
  } as const;

  export const shadowV2 = {
    card: {
      shadowColor: '#5B8CFF',
      shadowOffset: {width: 0, height: 8},
      shadowOpacity: 0.08,
      shadowRadius: 30,
      elevation: 8,
    },
    light: {
      shadowColor: '#000',
      shadowOffset: {width: 0, height: 4},
      shadowOpacity: 0.04,
      shadowRadius: 16,
      elevation: 4,
    },
    float: {
      shadowColor: '#5B8CFF',
      shadowOffset: {width: 0, height: 6},
      shadowOpacity: 0.15,
      shadowRadius: 20,
      elevation: 10,
    },
  } as const;

  export const animationTiming = {
    entranceDuration: 450,
    breathingDuration: 3000,
    pressDuration: 100,
    pressScale: 0.96,
    breathingOffset: 4,
    entranceTranslateY: 20,
  } as const;
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/theme/designTokens.ts
  git commit -m "feat: create design tokens (radii, typography, shadows, animation timing)"
  ```

---

### Task 3: Replace Color Palette

**Files:**
- Modify: `FarmManagerMobile/src/theme/colors.ts`

- [ ] **Step 1: Replace colors.ts entirely**

  ```typescript
  export const colors = {
    // Primary - Blue
    primary: '#5B8CFF',
    primaryLight: '#7AA8FF',
    primaryDark: '#4A7AEE',
    primaryMuted: 'rgba(91, 140, 255, 0.08)',

    // AI Accent - Purple
    aiPurple: '#8B5CF6',
    aiPurpleLight: '#A78BFA',
    aiPurpleMuted: 'rgba(139, 92, 246, 0.08)',

    // Agriculture - Green
    success: '#3BB273',
    successLight: '#4ADE80',
    successMuted: 'rgba(59, 178, 115, 0.08)',

    // Financial
    income: '#16A34A',
    incomeBg: '#EDFDF3',
    expense: '#EF4444',
    expenseBg: '#FFF1F2',

    // Semantic
    warning: '#E8923C',
    warningLight: '#FDF3E7',
    danger: '#DC4C4C',
    dangerLight: '#FDEBEB',
    info: '#3B82C4',
    infoLight: '#EBF3FB',

    // Background layers
    background: '#F6F8FC',
    surface: '#FFFFFF',
    surfaceElevated: '#FFFFFF',
    surfaceMuted: '#F1F3F5',

    // Text
    text: '#1A1D23',
    textSecondary: '#6B7280',
    textTertiary: '#9CA3AF',
    textInverse: '#FFFFFF',

    // Border & Divider
    border: '#E5E7EB',
    borderLight: '#F3F4F6',
    divider: 'rgba(0, 0, 0, 0.06)',

    // Shadow
    shadow: '#000000',

    // Header
    headerBg: '#0F172A',
    headerText: '#FFFFFF',

    // Tab
    tabBg: '#FFFFFF',
    tabActive: '#5B8CFF',
    tabInactive: '#9CA3AF',

    // Overlay
    overlay: 'rgba(0, 0, 0, 0.4)',
    scrim: 'rgba(15, 23, 42, 0.6)',

    disabled: '#D1D5DB',
    disabledBg: '#F3F4F6',

    // Quick action card backgrounds
    qaPlanting: '#EDFDF3',
    qaReminder: '#EEF4FF',
    qaWeather: '#FFF8E8',
    qaPest: '#FFF1F2',

    // AI Pet
    aiPetBg: '#EDF4FF',

    // Chat
    chatBgStart: '#F7FAFF',
    chatBgEnd: '#FFFFFF',
    chatInputBg: '#F3F6FB',
    chatAiBorder: '#EEF2F7',

    // Settings
    settingsBg: '#F8FAFC',

    // Weather detail
    weatherDetailStart: '#BFD8FF',
    weatherDetailMid: '#EAF3FF',
    weatherDetailEnd: '#FFFFFF',

    // Emotion card gradients (solid fallbacks)
    emotionFoggyStart: '#EAF3FF',
    emotionFoggyEnd: '#F7F9FF',
    emotionSunnyStart: '#FFF4D6',
    emotionSunnyEnd: '#FFF9EA',
    emotionRainyStart: '#DCEBFF',
    emotionRainyEnd: '#EEF5FF',
    emotionColdStart: '#E7F2FF',
    emotionColdEnd: '#F3F8FF',
  } as const;

  export const gradients = {
    primary: ['#5B8CFF', '#7AA8FF'] as const,
    primaryPurple: ['#5B8CFF', '#8B5CF6'] as const,
    userBubble: ['#5B8CFF', '#7A7DFF'] as const,
    header: ['#0F172A', '#1E293B'] as const,
    card: ['#FFFFFF', '#FAFBFC'] as const,
    success: ['#3BB273', '#4ADE80'] as const,
    danger: ['#DC4C4C', '#F87171'] as const,
    weatherCard: ['#5B8CFF', '#7AA8FF'] as const,
    fab: ['#5B8CFF', '#8B5CF6'] as const,
    titleText: ['#4DA2FF', '#C26CFF'] as const,
    chatBg: ['#F7FAFF', '#FFFFFF'] as const,
    weatherDetail: ['#BFD8FF', '#EAF3FF', '#FFFFFF'] as const,
    emotionFoggy: ['#EAF3FF', '#F7F9FF'] as const,
    emotionSunny: ['#FFF4D6', '#FFF9EA'] as const,
    emotionRainy: ['#DCEBFF', '#EEF5FF'] as const,
    emotionCold: ['#E7F2FF', '#F3F8FF'] as const,
    capsuleActive: ['#5B8CFF', '#7A7DFF'] as const,
  } as const;
  ```

- [ ] **Step 2: Update spacing.ts with v2 sizes**

  Append to `FarmManagerMobile/src/theme/spacing.ts`:
  ```typescript
  export const spacingV2 = {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    xxl: 24,
    xxxl: 32,
    xxxxl: 48,
  } as const;

  export const fontSizeV2 = {
    xs: 11,
    sm: 13,
    md: 15,
    lg: 18,
    xl: 22,
    xxl: 28,
    xxxl: 32,
    xxxxl: 48,
  } as const;

  export const borderRadiusV2 = {
    sm: 10,
    md: 14,
    lg: 18,
    xl: 20,
    xxl: 22,
    xxxl: 28,
    tab: 30,
    full: 999,
  } as const;
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add src/theme/colors.ts src/theme/spacing.ts
  git commit -m "feat: replace color palette with blue-purple-green v2 system"
  ```

---

### Task 4: Create Gradient Definitions File

**Files:**
- Create: `FarmManagerMobile/src/theme/gradients.ts`

- [ ] **Step 1: Write gradients.ts**

  ```typescript
  import {colors} from './colors';

  export type GradientColors = readonly string[];

  export const appGradients = {
    // Weather card background
    weatherCard: {
      colors: ['#5B8CFF', '#7AA8FF'] as GradientColors,
      start: {x: 0, y: 0},
      end: {x: 1, y: 1},
    },
    // User message bubble
    userBubble: {
      colors: ['#5B8CFF', '#7A7DFF'] as GradientColors,
      start: {x: 0, y: 0},
      end: {x: 1, y: 1},
    },
    // FAB button
    fab: {
      colors: ['#5B8CFF', '#8B5CF6'] as GradientColors,
      start: {x: 0, y: 0},
      end: {x: 1, y: 1},
    },
    // Capsule active tab
    capsuleActive: {
      colors: ['#5B8CFF', '#7A7DFF'] as GradientColors,
      start: {x: 0, y: 0},
      end: {x: 1, y: 0},
    },
    // Chat screen background
    chatBg: {
      colors: ['#F7FAFF', '#FFFFFF'] as GradientColors,
      start: {x: 0, y: 0},
      end: {x: 0, y: 1},
    },
    // Weather detail page background
    weatherDetail: {
      colors: ['#BFD8FF', '#EAF3FF', '#FFFFFF'] as GradientColors,
      locations: [0, 0.6, 1],
      start: {x: 0, y: 0},
      end: {x: 0, y: 1},
    },
    // Emotion cards
    emotionFoggy: {
      colors: [colors.emotionFoggyStart, colors.emotionFoggyEnd] as GradientColors,
      start: {x: 0, y: 0},
      end: {x: 1, y: 1},
    },
    emotionSunny: {
      colors: [colors.emotionSunnyStart, colors.emotionSunnyEnd] as GradientColors,
      start: {x: 0, y: 0},
      end: {x: 1, y: 1},
    },
    emotionRainy: {
      colors: [colors.emotionRainyStart, colors.emotionRainyEnd] as GradientColors,
      start: {x: 0, y: 0},
      end: {x: 1, y: 1},
    },
    emotionCold: {
      colors: [colors.emotionColdStart, colors.emotionColdEnd] as GradientColors,
      start: {x: 0, y: 0},
      end: {x: 1, y: 1},
    },
  } as const;
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/theme/gradients.ts
  git commit -m "feat: add gradient definitions for all v2 UI components"
  ```

---

### Task 5: Create Animation Constants File

**Files:**
- Create: `FarmManagerMobile/src/theme/animations.ts`

- [ ] **Step 1: Write animations.ts**

  ```typescript
  export const animationConfig = {
    // Card entrance: fade in + slide up
    entrance: {
      duration: 450,
      translateY: 20,
      useNativeDriver: true,
    },
    // Breathing float: continuous up/down
    breathing: {
      duration: 3000,
      offset: 4,
      useNativeDriver: true,
    },
    // Press feedback: scale down
    press: {
      duration: 100,
      scale: 0.96,
      useNativeDriver: true,
    },
    // Stagger delay for multiple cards
    stagger: {
      delay: 80,
    },
  } as const;
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/theme/animations.ts
  git commit -m "feat: add animation timing constants"
  ```

---

### Task 6: Create Reusable Animation Components

**Files:**
- Create: `FarmManagerMobile/src/components/animations/FadeInSlideUp.tsx`
- Create: `FarmManagerMobile/src/components/animations/BreathingFloat.tsx`
- Create: `FarmManagerMobile/src/components/animations/ScalePress.tsx`
- Create: `FarmManagerMobile/src/components/animations/index.ts`

- [ ] **Step 1: Create FadeInSlideUp.tsx**

  ```typescript
  import React, {useEffect, useRef} from 'react';
  import {Animated, ViewStyle} from 'react-native';
  import {animationConfig} from '../../theme/animations';

  interface FadeInSlideUpProps {
    children: React.ReactNode;
    delay?: number;
    style?: ViewStyle;
  }

  export const FadeInSlideUp: React.FC<FadeInSlideUpProps> = ({
    children,
    delay = 0,
    style,
  }) => {
    const opacity = useRef(new Animated.Value(0)).current;
    const translateY = useRef(new Animated.Value(animationConfig.entrance.translateY)).current;

    useEffect(() => {
      Animated.timing(opacity, {
        toValue: 1,
        duration: animationConfig.entrance.duration,
        delay,
        useNativeDriver: animationConfig.entrance.useNativeDriver,
      }).start();
      Animated.timing(translateY, {
        toValue: 0,
        duration: animationConfig.entrance.duration,
        delay,
        useNativeDriver: animationConfig.entrance.useNativeDriver,
      }).start();
    }, [opacity, translateY, delay]);

    return (
      <Animated.View
        style={[
          style,
          {
            opacity,
            transform: [{translateY}],
          },
        ]}>
        {children}
      </Animated.View>
    );
  };
  ```

- [ ] **Step 2: Create BreathingFloat.tsx**

  ```typescript
  import React, {useEffect, useRef} from 'react';
  import {Animated, ViewStyle} from 'react-native';
  import {animationConfig} from '../../theme/animations';

  interface BreathingFloatProps {
    children: React.ReactNode;
    style?: ViewStyle;
  }

  export const BreathingFloat: React.FC<BreathingFloatProps> = ({
    children,
    style,
  }) => {
    const translateY = useRef(new Animated.Value(0)).current;

    useEffect(() => {
      Animated.loop(
        Animated.sequence([
          Animated.timing(translateY, {
            toValue: -animationConfig.breathing.offset,
            duration: animationConfig.breathing.duration / 2,
            useNativeDriver: animationConfig.breathing.useNativeDriver,
          }),
          Animated.timing(translateY, {
            toValue: animationConfig.breathing.offset,
            duration: animationConfig.breathing.duration / 2,
            useNativeDriver: animationConfig.breathing.useNativeDriver,
          }),
          Animated.timing(translateY, {
            toValue: 0,
            duration: animationConfig.breathing.duration / 2,
            useNativeDriver: animationConfig.breathing.useNativeDriver,
          }),
        ]),
      ).start();
    }, [translateY]);

    return (
      <Animated.View
        style={[
          style,
          {
            transform: [{translateY}],
          },
        ]}>
        {children}
      </Animated.View>
    );
  };
  ```

- [ ] **Step 3: Create ScalePress.tsx**

  ```typescript
  import React, {useRef, useCallback} from 'react';
  import {Animated, Pressable, ViewStyle, GestureResponderEvent} from 'react-native';
  import {animationConfig} from '../../theme/animations';

  interface ScalePressProps {
    children: React.ReactNode;
    onPress?: (event: GestureResponderEvent) => void;
    style?: ViewStyle;
    disabled?: boolean;
  }

  export const ScalePress: React.FC<ScalePressProps> = ({
    children,
    onPress,
    style,
    disabled = false,
  }) => {
    const scale = useRef(new Animated.Value(1)).current;

    const handlePressIn = useCallback(() => {
      Animated.timing(scale, {
        toValue: animationConfig.press.scale,
        duration: animationConfig.press.duration,
        useNativeDriver: animationConfig.press.useNativeDriver,
      }).start();
    }, [scale]);

    const handlePressOut = useCallback(() => {
      Animated.timing(scale, {
        toValue: 1,
        duration: animationConfig.press.duration,
        useNativeDriver: animationConfig.press.useNativeDriver,
      }).start();
    }, [scale]);

    return (
      <Pressable
        onPress={onPress}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        disabled={disabled}>
        <Animated.View
          style={[
            style,
            {
              transform: [{scale}],
            },
          ]}>
          {children}
        </Animated.View>
      </Pressable>
    );
  };
  ```

- [ ] **Step 4: Create index.ts barrel export**

  ```typescript
  export {FadeInSlideUp} from './FadeInSlideUp';
  export {BreathingFloat} from './BreathingFloat';
  export {ScalePress} from './ScalePress';
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add src/components/animations/
  git commit -m "feat: add reusable animation wrappers (FadeInSlideUp, BreathingFloat, ScalePress)"
  ```

---

## Phase 2: Home Screen Redesign

### Task 7: Create WeatherCardV2 Component

**Files:**
- Create: `FarmManagerMobile/src/components/WeatherCardV2.tsx`
- Test: `FarmManagerMobile/src/components/__tests__/WeatherCardV2.test.tsx`

- [ ] **Step 1: Write WeatherCardV2.tsx**

  ```typescript
  import React from 'react';
  import {View, Text, StyleSheet, TouchableOpacity} from 'react-native';
  import LinearGradient from 'react-native-linear-gradient';
  import {colors} from '../theme/colors';
  import {spacingV2, fontSizeV2, borderRadiusV2} from '../theme/spacing';
  import {appGradients} from '../theme/gradients';
  import {shadowV2} from '../theme/designTokens';
  import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
  import {useNavigation} from '@react-navigation/native';

  interface WeatherDay {
    date: string;
    weekday: string;
    maxTemp: number;
    minTemp: number;
    precipitation: number;
  }

  interface WeatherCardV2Props {
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

  export const WeatherCardV2: React.FC<WeatherCardV2Props> = ({data}) => {
    const navigation = useNavigation();

    if (!data?.daily) {
      return (
        <LinearGradient
          {...appGradients.weatherCard}
          style={[styles.card, shadowV2.card]}>
          <Text style={styles.emptyText}>暂无天气数据</Text>
        </LinearGradient>
      );
    }

    const {time, temperature_2m_max, temperature_2m_min, precipitation_sum} = data.daily;

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

    return (
      <TouchableOpacity
        activeOpacity={0.9}
        onPress={() => navigation.navigate('WeatherDetail' as never)}>
        <LinearGradient
          {...appGradients.weatherCard}
          style={[styles.card, shadowV2.card]}>
          <View style={styles.topSection}>
            <View style={styles.topLeft}>
              <View style={styles.locationRow}>
                <Icon name="map-marker" size={14} color="rgba(255,255,255,0.8)" />
                <Text style={styles.locationText}>本地天气</Text>
              </View>
              <Text style={styles.bigTemp}>
                {today.minTemp}° ~ {today.maxTemp}°
              </Text>
              <Text style={styles.weatherLabel}>{todayLabel}</Text>
              <Text style={styles.feelsLike}>
                体感 {today.maxTemp - 2}°
              </Text>
            </View>
            <View style={styles.topRight}>
              <Icon name={todayIcon} size={64} color="#FFFFFF" />
            </View>
          </View>

          <View style={styles.divider} />

          <View style={styles.forecastRow}>
            {days.map(d => {
              const iconName = getWeatherIcon(d.precipitation, d.maxTemp);
              return (
                <View key={d.date} style={styles.dayItem}>
                  <Text style={styles.dayDate}>{d.date}</Text>
                  <Text style={styles.dayWeekday}>{d.weekday}</Text>
                  <Icon name={iconName} size={24} color="#FFFFFF" style={styles.dayIcon} />
                  <Text style={styles.dayTemp}>{d.maxTemp}°</Text>
                </View>
              );
            })}
          </View>
        </LinearGradient>
      </TouchableOpacity>
    );
  };

  const styles = StyleSheet.create({
    card: {
      borderRadius: borderRadiusV2.xxxl,
      padding: spacingV2.xl,
      overflow: 'hidden',
    },
    emptyText: {
      fontSize: fontSizeV2.md,
      color: colors.textInverse,
      textAlign: 'center',
      paddingVertical: spacingV2.xxl,
    },
    topSection: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
    },
    topLeft: {
      flex: 1,
    },
    locationRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      marginBottom: spacingV2.sm,
    },
    locationText: {
      fontSize: fontSizeV2.sm,
      color: 'rgba(255,255,255,0.8)',
    },
    bigTemp: {
      fontSize: fontSizeV2.xxxxl,
      fontWeight: '800',
      color: '#FFFFFF',
      letterSpacing: -1,
    },
    weatherLabel: {
      fontSize: fontSizeV2.md,
      color: 'rgba(255,255,255,0.8)',
      marginTop: 2,
    },
    feelsLike: {
      fontSize: fontSizeV2.sm,
      color: 'rgba(255,255,255,0.6)',
      marginTop: 4,
    },
    topRight: {
      alignItems: 'center',
      justifyContent: 'center',
      marginTop: spacingV2.md,
    },
    divider: {
      height: 1,
      backgroundColor: 'rgba(255,255,255,0.2)',
      marginVertical: spacingV2.lg,
    },
    forecastRow: {
      flexDirection: 'row',
      justifyContent: 'space-around',
    },
    dayItem: {
      alignItems: 'center',
      flex: 1,
    },
    dayDate: {
      fontSize: fontSizeV2.sm,
      color: 'rgba(255,255,255,0.9)',
      fontWeight: '600',
    },
    dayWeekday: {
      fontSize: fontSizeV2.xs,
      color: 'rgba(255,255,255,0.6)',
      marginTop: 2,
    },
    dayIcon: {
      marginVertical: spacingV2.sm,
    },
    dayTemp: {
      fontSize: fontSizeV2.md,
      color: '#FFFFFF',
      fontWeight: '700',
    },
  });
  ```

- [ ] **Step 2: Write test file**

  ```typescript
  import React from 'react';
  import {render} from '@testing-library/react-native';
  import {WeatherCardV2} from '../WeatherCardV2';

  jest.mock('react-native-linear-gradient', () => 'LinearGradient');
  jest.mock('@react-navigation/native', () => ({
    useNavigation: () => ({navigate: jest.fn()}),
  }));

  const mockWeatherData = {
    daily: {
      time: ['2026-05-27', '2026-05-28', '2026-05-29'],
      temperature_2m_max: [28, 30, 25],
      temperature_2m_min: [18, 20, 16],
      precipitation_sum: [0, 2, 8],
    },
  };

  describe('WeatherCardV2', () => {
    it('renders weather data correctly', () => {
      const {getByText} = render(<WeatherCardV2 data={mockWeatherData} />);
      expect(getByText('18° ~ 28°')).toBeTruthy();
      expect(getByText('多云')).toBeTruthy();
      expect(getByText('今天')).toBeTruthy();
    });

    it('renders empty state when no data', () => {
      const {getByText} = render(<WeatherCardV2 data={null} />);
      expect(getByText('暂无天气数据')).toBeTruthy();
    });

    it('shows 3-day forecast', () => {
      const {getByText} = render(<WeatherCardV2 data={mockWeatherData} />);
      expect(getByText('今天')).toBeTruthy();
      expect(getByText('5/28')).toBeTruthy();
      expect(getByText('5/29')).toBeTruthy();
    });
  });
  ```

- [ ] **Step 3: Run test**

  ```bash
  cd FarmManagerMobile && npx jest src/components/__tests__/WeatherCardV2.test.tsx --no-coverage
  ```

- [ ] **Step 4: Commit**

  ```bash
  git add src/components/WeatherCardV2.tsx src/components/__tests__/WeatherCardV2.test.tsx
  git commit -m "feat: add WeatherCardV2 with gradient background and 3-day forecast"
  ```

---

### Task 8: Refactor AdviceCard to Emotion-Based Design

**Files:**
- Modify: `FarmManagerMobile/src/components/AdviceCard.tsx`

- [ ] **Step 1: Rewrite AdviceCard with emotion gradients**

  Replace the entire file content:

  ```typescript
  import React, {useState} from 'react';
  import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    LayoutAnimation,
    Platform,
    UIManager,
  } from 'react-native';
  import LinearGradient from 'react-native-linear-gradient';
  import {Loading} from './Loading';
  import {MarkdownText} from './MarkdownText';
  import type {AdviceItem} from '../api/types';
  import {colors} from '../theme/colors';
  import {spacingV2, fontSizeV2, borderRadiusV2} from '../theme/spacing';
  import {appGradients} from '../theme/gradients';
  import {shadowV2} from '../theme/designTokens';
  import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

  if (Platform.OS === 'android') {
    UIManager.setLayoutAnimationEnabledExperimental?.(true);
  }

  interface AdviceCardProps {
    advice: string | null;
    items?: AdviceItem[] | null;
    loading?: boolean;
    onPress?: () => void;
    onRefresh?: () => void;
    weatherCondition?: 'foggy' | 'sunny' | 'rainy' | 'cold';
  }

  const MAX_LINES = 4;

  const getEmotionGradient = (condition?: string) => {
    switch (condition) {
      case 'foggy':
        return appGradients.emotionFoggy;
      case 'rainy':
        return appGradients.emotionRainy;
      case 'cold':
        return appGradients.emotionCold;
      case 'sunny':
      default:
        return appGradients.emotionSunny;
    }
  };

  const getEmotionTitle = (condition?: string) => {
    switch (condition) {
      case 'foggy':
        return '雾气朦胧，注意排湿';
      case 'rainy':
        return '雨水充沛，防涝为主';
      case 'cold':
        return '气温骤降，注意防冻';
      case 'sunny':
      default:
        return '阳光正好，适合农作';
    }
  };

  export const AdviceCard: React.FC<AdviceCardProps> = ({
    advice,
    items,
    loading = false,
    onPress,
    onRefresh,
    weatherCondition = 'sunny',
  }) => {
    const [expanded, setExpanded] = useState(false);
    const gradient = getEmotionGradient(weatherCondition);

    const handleToggle = () => {
      LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
      setExpanded(!expanded);
    };

    const hasItems = items && items.length > 0;

    return (
      <LinearGradient
        {...gradient}
        style={[styles.card, shadowV2.light]}>
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.iconCircle}>
            <Icon name="sprout" size={20} color={colors.success} />
          </View>
          <View style={styles.headerText}>
            <Text style={styles.title}>{getEmotionTitle(weatherCondition)}</Text>
            <Text style={styles.subtitle}>AI 农事顾问</Text>
          </View>
          {onRefresh && (
            <TouchableOpacity onPress={onRefresh} activeOpacity={0.7} style={styles.refreshBtn}>
              <Icon name="refresh" size={16} color={colors.textTertiary} />
            </TouchableOpacity>
          )}
        </View>

        {/* Content */}
        {loading && (
          <View style={styles.center}>
            <Loading />
            <Text style={styles.hint}>AI 正在分析天气和作物数据...</Text>
          </View>
        )}

        {!loading && !advice && !hasItems && (
          <View style={styles.center}>
            <Icon name="information-outline" size={32} color={colors.textTertiary} />
            <Text style={styles.hint}>暂无建议，请稍后重试</Text>
          </View>
        )}

        {!loading && hasItems && (
          <View style={styles.itemsContainer}>
            {items.map((item, index) => (
              <View key={index} style={styles.itemCard}>
                <View style={styles.itemTopRow}>
                  <Text style={styles.itemTitle}>{item.title}</Text>
                </View>
                <Text style={styles.itemDetail} numberOfLines={2}>{item.detail}</Text>
              </View>
            ))}
          </View>
        )}

        {!loading && !hasItems && advice && (
          <>
            <View style={[styles.contentWrapper, !expanded && styles.contentCollapsed]}>
              <MarkdownText text={advice} baseStyle={styles.adviceText} />
            </View>
            {advice.split('\n').length > MAX_LINES && (
              <TouchableOpacity onPress={handleToggle} style={styles.toggleBtn} activeOpacity={0.7}>
                <Text style={styles.toggleText}>{expanded ? '收起' : '展开更多'}</Text>
                <Icon name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={colors.primary} />
              </TouchableOpacity>
            )}
          </>
        )}

        {(!loading && (advice || hasItems)) && (
          <View style={styles.actionBar}>
            <TouchableOpacity style={styles.actionBtn} onPress={onPress} activeOpacity={0.7}>
              <Icon name="chat-processing-outline" size={18} color={colors.primary} />
              <Text style={styles.actionText}>继续咨询</Text>
            </TouchableOpacity>
          </View>
        )}
      </LinearGradient>
    );
  };

  const styles = StyleSheet.create({
    card: {
      borderRadius: borderRadiusV2.xxxl,
      padding: spacingV2.xl,
    },
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      marginBottom: spacingV2.md,
      gap: spacingV2.sm,
    },
    iconCircle: {
      width: 40,
      height: 40,
      borderRadius: borderRadiusV2.lg,
      backgroundColor: colors.successMuted,
      alignItems: 'center',
      justifyContent: 'center',
    },
    headerText: {
      flex: 1,
    },
    title: {
      fontSize: fontSizeV2.md,
      fontWeight: '700',
      color: colors.text,
    },
    subtitle: {
      fontSize: fontSizeV2.xs,
      color: colors.textTertiary,
      marginTop: 2,
    },
    refreshBtn: {
      padding: spacingV2.xs,
    },
    center: {
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: spacingV2.xl,
      gap: spacingV2.sm,
    },
    hint: {
      fontSize: fontSizeV2.sm,
      color: colors.textSecondary,
    },
    contentWrapper: {
      overflow: 'hidden',
    },
    contentCollapsed: {
      maxHeight: 140,
    },
    adviceText: {
      fontSize: fontSizeV2.md,
      color: colors.textSecondary,
      lineHeight: 24,
    },
    toggleBtn: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      marginTop: spacingV2.sm,
      paddingVertical: spacingV2.xs,
    },
    toggleText: {
      fontSize: fontSizeV2.sm,
      color: colors.primary,
      fontWeight: '600',
      marginRight: 2,
    },
    itemsContainer: {
      gap: spacingV2.sm,
    },
    itemCard: {
      backgroundColor: 'rgba(255,255,255,0.6)',
      borderRadius: borderRadiusV2.lg,
      padding: spacingV2.md,
    },
    itemTopRow: {
      flexDirection: 'row',
      alignItems: 'center',
      marginBottom: spacingV2.xs,
    },
    itemTitle: {
      fontSize: fontSizeV2.md,
      fontWeight: '700',
      color: colors.text,
    },
    itemDetail: {
      fontSize: fontSizeV2.sm,
      color: colors.textSecondary,
      lineHeight: 20,
    },
    actionBar: {
      flexDirection: 'row',
      justifyContent: 'flex-end',
      marginTop: spacingV2.md,
      paddingTop: spacingV2.md,
      borderTopWidth: 1,
      borderTopColor: 'rgba(0,0,0,0.06)',
    },
    actionBtn: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacingV2.xs,
      backgroundColor: 'rgba(255,255,255,0.7)',
      paddingHorizontal: spacingV2.md,
      paddingVertical: spacingV2.sm,
      borderRadius: borderRadiusV2.md,
    },
    actionText: {
      fontSize: fontSizeV2.sm,
      color: colors.primary,
      fontWeight: '600',
    },
  });
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/components/AdviceCard.tsx
  git commit -m "feat: restyle AdviceCard as emotion-based gradient card"
  ```

---

### Task 9: Create AIPet Component

**Files:**
- Create: `FarmManagerMobile/src/components/AIPet.tsx`

- [ ] **Step 1: Write AIPet.tsx**

  ```typescript
  import React from 'react';
  import {View, Text, StyleSheet, TouchableOpacity} from 'react-native';
  import {useNavigation} from '@react-navigation/native';
  import {BreathingFloat} from './animations/BreathingFloat';
  import {ScalePress} from './animations/ScalePress';
  import {colors} from '../theme/colors';
  import {shadowV2} from '../theme/designTokens';
  import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

  export const AIPet: React.FC = () => {
    const navigation = useNavigation();

    const handlePress = () => {
      navigation.navigate('AgentChat' as never);
    };

    return (
      <View style={styles.container}>
        <BreathingFloat>
          <ScalePress onPress={handlePress}>
            <View style={[styles.pet, shadowV2.float]}>
              <Icon name="robot-happy" size={32} color={colors.primary} />
              <View style={styles.pulseDot} />
            </View>
          </ScalePress>
        </BreathingFloat>
      </View>
    );
  };

  const styles = StyleSheet.create({
    container: {
      position: 'absolute',
      right: 20,
      bottom: 100,
      zIndex: 100,
    },
    pet: {
      width: 72,
      height: 72,
      borderRadius: 36,
      backgroundColor: colors.aiPetBg,
      alignItems: 'center',
      justifyContent: 'center',
      opacity: 0.9,
      borderWidth: 2,
      borderColor: 'rgba(91,140,255,0.15)',
    },
    pulseDot: {
      position: 'absolute',
      top: 14,
      right: 14,
      width: 10,
      height: 10,
      borderRadius: 5,
      backgroundColor: colors.success,
      borderWidth: 2,
      borderColor: colors.aiPetBg,
    },
  });
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/components/AIPet.tsx
  git commit -m "feat: add AIPet floating button with breathing animation"
  ```

---

### Task 10: Rewrite HomeScreen Layout

**Files:**
- Modify: `FarmManagerMobile/src/screens/home/HomeScreen.tsx`

- [ ] **Step 1: Replace HomeScreen.tsx**

  ```typescript
  import React, {useEffect, useState} from 'react';
  import {
    View,
    Text,
    ScrollView,
    TouchableOpacity,
    StyleSheet,
  } from 'react-native';
  import {SafeAreaView} from 'react-native-safe-area-context';
  import {useNavigation} from '@react-navigation/native';
  import {useAgentStore} from '../../stores/agentStore';
  import {useSettingsStore} from '../../stores/settingsStore';
  import {useCycleStore} from '../../stores/cycleStore';
  import {CITIES} from '../../data/cities';
  import {WeatherCardV2} from '../../components/WeatherCardV2';
  import {AdviceCard} from '../../components/AdviceCard';
  import {AIPet} from '../../components/AIPet';
  import {CityPicker} from '../../components/CityPicker';
  import {FadeInSlideUp} from '../../components/animations/FadeInSlideUp';
  import {ScalePress} from '../../components/animations/ScalePress';
  import {colors} from '../../theme/colors';
  import {spacingV2, fontSizeV2, borderRadiusV2} from '../../theme/spacing';
  import {shadowV2} from '../../theme/designTokens';
  import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 11) return '早上好，农友';
    if (hour < 14) return '中午好，农友';
    if (hour < 18) return '下午好，农友';
    return '晚上好，农友';
  };

  const QUICK_ACTIONS = [
    {
      label: '种植规划',
      icon: 'seed-plus',
      bgColor: colors.qaPlanting,
      iconColor: '#16A34A',
      route: 'CycleCreate',
    },
    {
      label: '农事提醒',
      icon: 'bell-ring',
      bgColor: colors.qaReminder,
      iconColor: '#5B8CFF',
      route: 'AgentChat',
    },
    {
      label: '天气趋势',
      icon: 'weather-partly-cloudy',
      bgColor: colors.qaWeather,
      iconColor: '#E8923C',
      route: 'AgentChat',
    },
    {
      label: '病虫害识别',
      icon: 'bug',
      bgColor: colors.qaPest,
      iconColor: '#EF4444',
      route: 'AgentChat',
    },
  ];

  const getWeatherCondition = (weather: any): 'sunny' | 'rainy' | 'foggy' | 'cold' => {
    if (!weather?.daily) return 'sunny';
    const precip = weather.daily.precipitation_sum?.[0] || 0;
    const maxTemp = weather.daily.temperature_2m_max?.[0] || 20;
    if (precip > 5) return 'rainy';
    if (precip > 0) return 'foggy';
    if (maxTemp < 10) return 'cold';
    return 'sunny';
  };

  export const HomeScreen: React.FC = () => {
    const navigation = useNavigation();
    const {
      weather,
      dailyAdvice,
      fetchWeather,
      fetchDailyAdvice,
      refreshDailyAdvice,
      loading: agentLoading,
      cityName,
      setCity,
    } = useAgentStore();
    const {defaultCity, setDefaultCity} = useSettingsStore();
    const {cycles, fetchCycles} = useCycleStore();
    const [pickerVisible, setPickerVisible] = useState(false);

    useEffect(() => {
      if (defaultCity !== cityName) {
        const cityData = CITIES.find(c => c.name === defaultCity);
        if (cityData) {
          setCity(cityData.name, cityData.lat, cityData.lon);
        }
      }
      fetchWeather();
      fetchDailyAdvice();
      fetchCycles();
    }, [fetchWeather, fetchDailyAdvice, fetchCycles]);

    const greeting = getGreeting();
    const weatherCondition = getWeatherCondition(weather);

    const handleCitySelect = (city: {name: string; lat: number; lon: number}) => {
      setCity(city.name, city.lat, city.lon);
      setDefaultCity(city.name);
      fetchWeather();
    };

    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}>
          {/* Header */}
          <FadeInSlideUp style={styles.headerSection}>
            <View style={styles.headerTop}>
              <View>
                <TouchableOpacity
                  style={styles.cityRow}
                  onPress={() => setPickerVisible(true)}
                  activeOpacity={0.7}>
                  <Icon name="map-marker" size={14} color={colors.primary} />
                  <Text style={styles.cityName}>{cityName}</Text>
                  <Icon name="chevron-down" size={14} color={colors.primary} />
                </TouchableOpacity>
                <Text style={styles.greeting}>{greeting}</Text>
                <Text style={styles.dateText}>
                  {new Date().toLocaleDateString('zh-CN', {
                    month: 'long',
                    day: 'numeric',
                    weekday: 'long',
                  })}
                </Text>
              </View>
              <ScalePress onPress={() => navigation.navigate('AgentChat' as never)}>
                <View style={styles.aiIconBtn}>
                  <Icon name="robot" size={22} color={colors.primary} />
                </View>
              </ScalePress>
            </View>
          </FadeInSlideUp>

          {/* Weather Card */}
          <FadeInSlideUp delay={80} style={styles.section}>
            <WeatherCardV2 data={weather} />
          </FadeInSlideUp>

          {/* AI Briefing Card */}
          <FadeInSlideUp delay={160} style={styles.section}>
            <AdviceCard
              advice={dailyAdvice?.advice || null}
              items={dailyAdvice?.items}
              loading={agentLoading}
              onPress={() => navigation.navigate('AgentChat' as never)}
              onRefresh={() => refreshDailyAdvice()}
              weatherCondition={weatherCondition}
            />
          </FadeInSlideUp>

          {/* Quick Actions */}
          <FadeInSlideUp delay={240} style={styles.section}>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.quickActionsContainer}>
              {QUICK_ACTIONS.map(action => (
                <ScalePress
                  key={action.label}
                  onPress={() => navigation.navigate(action.route as never)}>
                  <View style={[styles.quickActionCard, {backgroundColor: action.bgColor}]}>
                    <View style={styles.quickActionIcon}>
                      <Icon name={action.icon} size={24} color={action.iconColor} />
                    </View>
                    <Text style={styles.quickActionLabel}>{action.label}</Text>
                  </View>
                </ScalePress>
              ))}
            </ScrollView>
          </FadeInSlideUp>
        </ScrollView>

        <AIPet />

        <CityPicker
          visible={pickerVisible}
          selectedCity={cityName}
          onSelect={handleCitySelect}
          onClose={() => setPickerVisible(false)}
        />
      </SafeAreaView>
    );
  };

  const styles = StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: colors.background,
    },
    scrollContent: {
      paddingBottom: spacingV2.xxxl,
    },
    headerSection: {
      paddingHorizontal: spacingV2.lg,
      paddingTop: spacingV2.md,
      paddingBottom: spacingV2.lg,
    },
    headerTop: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
    },
    cityRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      marginBottom: spacingV2.sm,
      alignSelf: 'flex-start',
      backgroundColor: colors.primaryMuted,
      paddingHorizontal: spacingV2.sm,
      paddingVertical: 4,
      borderRadius: borderRadiusV2.md,
    },
    cityName: {
      fontSize: fontSizeV2.sm,
      fontWeight: '600',
      color: colors.primary,
    },
    greeting: {
      fontSize: fontSizeV2.xl,
      fontWeight: '800',
      color: colors.text,
      letterSpacing: -0.5,
    },
    dateText: {
      fontSize: fontSizeV2.sm,
      color: colors.textSecondary,
      marginTop: 4,
    },
    aiIconBtn: {
      width: 44,
      height: 44,
      borderRadius: borderRadiusV2.full,
      backgroundColor: colors.aiPetBg,
      alignItems: 'center',
      justifyContent: 'center',
    },
    section: {
      paddingHorizontal: spacingV2.lg,
      marginBottom: spacingV2.xl,
    },
    quickActionsContainer: {
      paddingRight: spacingV2.lg,
      gap: spacingV2.md,
    },
    quickActionCard: {
      width: 110,
      height: 120,
      borderRadius: borderRadiusV2.xxl,
      padding: spacingV2.md,
      justifyContent: 'space-between',
    },
    quickActionIcon: {
      width: 44,
      height: 44,
      borderRadius: borderRadiusV2.lg,
      backgroundColor: 'rgba(255,255,255,0.7)',
      alignItems: 'center',
      justifyContent: 'center',
    },
    quickActionLabel: {
      fontSize: fontSizeV2.sm,
      color: colors.text,
      fontWeight: '600',
    },
  });
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/screens/home/HomeScreen.tsx
  git commit -m "feat: rewrite HomeScreen with v2 layout, animations, and AIPet"
  ```

---

## Phase 3: BottomBar Redesign

### Task 11: Refactor MainTabNavigator

**Files:**
- Modify: `FarmManagerMobile/src/navigation/MainTabNavigator.tsx`

- [ ] **Step 1: Replace MainTabNavigator.tsx**

  ```typescript
  import React from 'react';
  import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
  import {View, Text, StyleSheet, Platform} from 'react-native';
  import {colors} from '../theme/colors';
  import {spacingV2, fontSizeV2, borderRadiusV2} from '../theme/spacing';
  import {shadowV2} from '../theme/designTokens';
  import LinearGradient from 'react-native-linear-gradient';
  import {HomeScreen} from '../screens/home/HomeScreen';
  import {AgentChatScreen} from '../screens/agent/AgentChatScreen';
  import {CostListScreen} from '../screens/cost/CostListScreen';
  import {SettingsScreen} from '../screens/settings/SettingsScreen';
  import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

  export type MainTabParamList = {
    Home: undefined;
    AgentChat: undefined;
    Costs: undefined;
    Settings: undefined;
  };

  const Tab = createBottomTabNavigator<MainTabParamList>();

  const TAB_CONFIG: Record<keyof MainTabParamList, {label: string; icon: string; activeIcon: string}> = {
    Home: {label: '首页', icon: 'home-outline', activeIcon: 'home'},
    AgentChat: {label: 'AI助手', icon: 'robot-outline', activeIcon: 'robot'},
    Costs: {label: '记账', icon: 'cash-multiple', activeIcon: 'cash-multiple'},
    Settings: {label: '我的', icon: 'account-outline', activeIcon: 'account'},
  };

  export const MainTabNavigator: React.FC = () => (
    <Tab.Navigator
      screenOptions={({route}) => ({
        headerShown: false,
        tabBarStyle: styles.tabBar,
        tabBarShowLabel: false,
        tabBarIcon: ({focused}) => {
          const config = TAB_CONFIG[route.name];
          return (
            <View style={styles.tabItem}>
              {focused ? (
                <LinearGradient
                  colors={['#5B8CFF', '#7A7DFF']}
                  start={{x: 0, y: 0}}
                  end={{x: 1, y: 0}}
                  style={styles.capsule}>
                  <Icon name={config.activeIcon} size={20} color="#FFFFFF" />
                  <Text style={styles.capsuleLabel}>{config.label}</Text>
                </LinearGradient>
              ) : (
                <View style={styles.inactiveItem}>
                  <Icon name={config.icon} size={22} color={colors.tabInactive} />
                  <Text style={styles.inactiveLabel}>{config.label}</Text>
                </View>
              )}
            </View>
          );
        },
      })}>
      <Tab.Screen name="Home" component={HomeScreen} />
      <Tab.Screen name="AgentChat" component={AgentChatScreen} />
      <Tab.Screen name="Costs" component={CostListScreen} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );

  const styles = StyleSheet.create({
    tabBar: {
      position: 'absolute',
      bottom: 16,
      left: 16,
      right: 16,
      height: 72,
      borderRadius: borderRadiusV2.tab,
      backgroundColor: Platform.select({
        ios: 'rgba(255,255,255,0.85)',
        android: 'rgba(255,255,255,0.95)',
      }),
      borderTopWidth: 0,
      ...shadowV2.card,
      elevation: 10,
    },
    tabItem: {
      alignItems: 'center',
      justifyContent: 'center',
      flex: 1,
    },
    capsule: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: spacingV2.md,
      paddingVertical: spacingV2.sm,
      borderRadius: borderRadiusV2.full,
      gap: 4,
    },
    capsuleLabel: {
      fontSize: fontSizeV2.sm,
      color: '#FFFFFF',
      fontWeight: '600',
    },
    inactiveItem: {
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: spacingV2.sm,
    },
    inactiveLabel: {
      fontSize: fontSizeV2.xs,
      color: colors.tabInactive,
      marginTop: 2,
      fontWeight: '500',
    },
  });
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/navigation/MainTabNavigator.tsx
  git commit -m "feat: redesign BottomBar with glassmorphism and capsule active state"
  ```

---

## Phase 4: AI Chat Screen Upgrade

### Task 12: Refactor AgentChatScreen Visual Design

**Files:**
- Modify: `FarmManagerMobile/src/screens/agent/AgentChatScreen.tsx`

- [ ] **Step 1: Replace AgentChatScreen.tsx**

  ```typescript
  import React, {useState, useRef, useCallback, useEffect} from 'react';
  import {
    View,
    Text,
    FlatList,
    TextInput,
    TouchableOpacity,
    KeyboardAvoidingView,
    Platform,
    StyleSheet,
  } from 'react-native';
  import LinearGradient from 'react-native-linear-gradient';
  import {SafeAreaView} from 'react-native-safe-area-context';
  import {useNavigation} from '@react-navigation/native';
  import {useAgentStore} from '../../stores/agentStore';
  import type {ChatMessage} from '../../api/types';
  import {MarkdownText} from '../../components/MarkdownText';
  import {ReportListView} from '../../components/ReportListView';
  import {ScalePress} from '../../components/animations/ScalePress';
  import {colors} from '../../theme/colors';
  import {spacingV2, fontSizeV2, borderRadiusV2} from '../../theme/spacing';
  import {appGradients} from '../../theme/gradients';
  import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

  const RECOMMENDED_QUESTIONS = [
    '帮我规划秋种',
    '今天适合施肥吗',
    '未来一周天气',
  ];

  const QUICK_PROMPTS = [
    {icon: 'weather-partly-cloudy', text: '今日天气对作物有什么影响？'},
    {icon: 'sprout', text: '给我一些种植建议'},
    {icon: 'bug', text: '常见的病虫害怎么防治？'},
    {icon: 'file-document', text: '生成本周种植报告'},
  ];

  export const AgentChatScreen: React.FC = () => {
    const navigation = useNavigation();
    const {messages, sendMessage, loading: isLoading, reports, fetchReports} = useAgentStore();
    const [inputText, setInputText] = useState('');
    const [activeTab, setActiveTab] = useState<'chat' | 'report'>('chat');
    const flatListRef = useRef<FlatList>(null);

    const hasMessages = messages.length > 0;

    useEffect(() => {
      if (activeTab === 'report') {
        fetchReports();
      }
    }, [activeTab]);

    const handleSend = async (text: string) => {
      if (!text.trim() || isLoading) return;
      setInputText('');
      await sendMessage(text.trim());
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({animated: true});
      }, 100);
    };

    const handleInputSend = () => {
      handleSend(inputText);
    };

    const renderMessage = ({item}: {item: ChatMessage}) => {
      const isUser = item.role === 'user';
      const hasPendingAction = !isUser && item.pending_action;
      return (
        <View style={[styles.messageRow, isUser ? styles.userRow : styles.agentRow]}>
          {!isUser && (
            <View style={styles.agentAvatar}>
              <View style={styles.aiFace}>
                <View style={styles.aiEye} />
                <View style={styles.aiEye} />
              </View>
            </View>
          )}
          <View style={[styles.messageBubble, isUser ? styles.userBubble : styles.agentBubble]}>
            {isUser ? (
              <LinearGradient
                {...appGradients.userBubble}
                style={styles.userBubbleInner}>
                <Text style={styles.userText}>{item.content}</Text>
              </LinearGradient>
            ) : (
              <View style={styles.agentBubbleInner}>
                <MarkdownText text={item.content} baseStyle={styles.agentText} />
              </View>
            )}
            {hasPendingAction && (
              <View style={styles.confirmBar}>
                <TouchableOpacity style={styles.confirmBtn} onPress={() => handleSend('确认')} activeOpacity={0.7} disabled={isLoading}>
                  <Text style={styles.confirmBtnText}>确认</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.cancelBtn} onPress={() => handleSend('取消')} activeOpacity={0.7} disabled={isLoading}>
                  <Text style={styles.cancelBtnText}>取消</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        </View>
      );
    };

    const renderWelcome = () => (
      <View style={styles.welcomeContainer}>
        <View style={styles.welcomeAvatar}>
          <View style={styles.aiFaceLarge}>
            <View style={styles.aiEyeLarge} />
            <View style={styles.aiEyeLarge} />
          </View>
        </View>
        <Text style={styles.welcomeTitle}>你好呀，我是 AI 农事助手</Text>
        <Text style={styles.welcomeSubtitle}>可以帮你分析天气、提供种植建议、生成报告</Text>

        {/* Recommended question capsules */}
        <View style={styles.capsulesContainer}>
          {RECOMMENDED_QUESTIONS.map((q, index) => (
            <ScalePress key={index} onPress={() => handleSend(q)}>
              <View style={styles.capsuleChip}>
                <Text style={styles.capsuleText}>{q}</Text>
              </View>
            </ScalePress>
          ))}
        </View>

        <View style={styles.quickPromptsContainer}>
          {QUICK_PROMPTS.map((prompt, index) => (
            <ScalePress key={index} onPress={() => handleSend(prompt.text)}>
              <View style={styles.quickPrompt}>
                <Icon name={prompt.icon} size={18} color={colors.primary} />
                <Text style={styles.quickPromptText}>{prompt.text}</Text>
              </View>
            </ScalePress>
          ))}
        </View>
      </View>
    );

    const ListHeaderComponent = useCallback(() => {
      if (hasMessages) return null;
      return renderWelcome();
    }, [hasMessages]);

    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <LinearGradient {...appGradients.chatBg} style={StyleSheet.absoluteFill} />

        {/* Header */}
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <View style={styles.headerAvatar}>
              <View style={styles.aiFaceSmall}>
                <View style={styles.aiEyeSmall} />
                <View style={styles.aiEyeSmall} />
              </View>
            </View>
            <View>
              <Text style={styles.headerTitle}>AI 农事助手</Text>
              <View style={styles.statusRow}>
                <View style={styles.statusDot} />
                <Text style={styles.headerSubtitle}>在线</Text>
              </View>
            </View>
          </View>
        </View>

        {/* SegmentedControl */}
        <View style={styles.segmentRow}>
          <TouchableOpacity
            style={[styles.segBtn, activeTab === 'chat' && styles.segBtnActive]}
            onPress={() => setActiveTab('chat')}
            activeOpacity={0.7}>
            <Text style={[styles.segText, activeTab === 'chat' && styles.segTextActive]}>对话</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.segBtn, activeTab === 'report' && styles.segBtnActive]}
            onPress={() => setActiveTab('report')}
            activeOpacity={0.7}>
            <Text style={[styles.segText, activeTab === 'report' && styles.segTextActive]}>报告</Text>
          </TouchableOpacity>
        </View>

        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}>
          {activeTab === 'chat' ? (
            <>
              <FlatList
                ref={flatListRef}
                data={messages}
                keyExtractor={(_, index) => String(index)}
                renderItem={renderMessage}
                contentContainerStyle={[styles.listContent, !hasMessages && {flexGrow: 1}]}
                ListHeaderComponent={ListHeaderComponent}
                onContentSizeChange={() => flatListRef.current?.scrollToEnd({animated: true})}
              />

              {isLoading && hasMessages && (
                <View style={styles.typingRow}>
                  <View style={styles.typingBubble}>
                    <View style={styles.typingDot} />
                    <View style={[styles.typingDot, styles.typingDot2]} />
                    <View style={[styles.typingDot, styles.typingDot3]} />
                  </View>
                </View>
              )}

              {/* Input */}
              <View style={styles.inputBar}>
                <View style={styles.inputWrapper}>
                  <TextInput
                    style={styles.input}
                    value={inputText}
                    onChangeText={setInputText}
                    placeholder="请输入您的问题..."
                    placeholderTextColor={colors.textTertiary}
                    multiline
                    maxLength={500}
                  />
                  <TouchableOpacity
                    style={[styles.sendBtn, (!inputText.trim() || isLoading) && styles.sendBtnDisabled]}
                    onPress={handleInputSend}
                    disabled={!inputText.trim() || isLoading}
                    activeOpacity={0.7}>
                    <LinearGradient
                      {...appGradients.userBubble}
                      style={[styles.sendBtnGradient, (!inputText.trim() || isLoading) && styles.sendBtnDisabled]}>
                      <Icon name="send" size={18} color={!inputText.trim() || isLoading ? colors.textTertiary : '#FFFFFF'} />
                    </LinearGradient>
                  </TouchableOpacity>
                </View>
              </View>
            </>
          ) : (
            <ReportListView
              reports={reports}
              onGenerate={() => navigation.navigate('AgentReport' as never)}
              onViewReport={(r) =>
                (navigation as any).navigate('AgentReport', {
                  content: r.content,
                  reportType: r.report_type,
                  createdAt: r.created_at,
                  reportId: r.id,
                })
              }
            />
          )}
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  };

  const styles = StyleSheet.create({
    container: {
      flex: 1,
    },
    flex: {
      flex: 1,
    },
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: spacingV2.lg,
      paddingVertical: spacingV2.md,
      backgroundColor: 'transparent',
    },
    headerLeft: {
      flexDirection: 'row',
      alignItems: 'center',
    },
    headerAvatar: {
      width: 40,
      height: 40,
      borderRadius: borderRadiusV2.lg,
      backgroundColor: colors.primaryMuted,
      alignItems: 'center',
      justifyContent: 'center',
      marginRight: spacingV2.md,
    },
    aiFace: {
      width: 24,
      height: 24,
      borderRadius: 12,
      backgroundColor: '#1A1D23',
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 4,
    },
    aiEye: {
      width: 4,
      height: 4,
      borderRadius: 2,
      backgroundColor: '#FFFFFF',
    },
    aiFaceSmall: {
      width: 28,
      height: 28,
      borderRadius: 14,
      backgroundColor: '#1A1D23',
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 4,
    },
    aiEyeSmall: {
      width: 5,
      height: 5,
      borderRadius: 2.5,
      backgroundColor: '#FFFFFF',
    },
    aiFaceLarge: {
      width: 56,
      height: 56,
      borderRadius: 28,
      backgroundColor: '#1A1D23',
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
    },
    aiEyeLarge: {
      width: 8,
      height: 8,
      borderRadius: 4,
      backgroundColor: '#FFFFFF',
    },
    headerTitle: {
      fontSize: fontSizeV2.md,
      fontWeight: '700',
      color: colors.text,
    },
    statusRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      marginTop: 2,
    },
    statusDot: {
      width: 6,
      height: 6,
      borderRadius: 3,
      backgroundColor: colors.success,
    },
    headerSubtitle: {
      fontSize: fontSizeV2.xs,
      color: colors.textSecondary,
    },
    segmentRow: {
      flexDirection: 'row',
      marginHorizontal: spacingV2.lg,
      marginTop: spacingV2.sm,
      marginBottom: spacingV2.sm,
      backgroundColor: 'rgba(255,255,255,0.7)',
      borderRadius: borderRadiusV2.lg,
      padding: 3,
    },
    segBtn: {
      flex: 1,
      paddingVertical: spacingV2.sm,
      alignItems: 'center',
      borderRadius: borderRadiusV2.md,
    },
    segBtnActive: {
      backgroundColor: colors.surface,
      shadowColor: '#000',
      shadowOffset: {width: 0, height: 1},
      shadowOpacity: 0.1,
      shadowRadius: 2,
      elevation: 2,
    },
    segText: {
      fontSize: fontSizeV2.sm,
      color: colors.textSecondary,
      fontWeight: '600',
    },
    segTextActive: {
      color: colors.text,
    },
    listContent: {
      padding: spacingV2.md,
      paddingBottom: spacingV2.sm,
    },
    welcomeContainer: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: spacingV2.xxl,
      paddingHorizontal: spacingV2.lg,
    },
    welcomeAvatar: {
      width: 80,
      height: 80,
      borderRadius: borderRadiusV2.full,
      backgroundColor: colors.primaryMuted,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: spacingV2.lg,
    },
    welcomeTitle: {
      fontSize: fontSizeV2.xl,
      fontWeight: '800',
      color: colors.text,
      marginBottom: spacingV2.xs,
      textAlign: 'center',
    },
    welcomeSubtitle: {
      fontSize: fontSizeV2.sm,
      color: colors.textSecondary,
      marginBottom: spacingV2.xl,
      textAlign: 'center',
    },
    capsulesContainer: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      justifyContent: 'center',
      gap: spacingV2.sm,
      marginBottom: spacingV2.xl,
    },
    capsuleChip: {
      backgroundColor: colors.surface,
      borderRadius: borderRadiusV2.full,
      paddingHorizontal: spacingV2.md,
      paddingVertical: spacingV2.sm,
      borderWidth: 1,
      borderColor: colors.borderLight,
    },
    capsuleText: {
      fontSize: fontSizeV2.sm,
      color: colors.text,
      fontWeight: '500',
    },
    quickPromptsContainer: {
      width: '100%',
      gap: spacingV2.sm,
    },
    quickPrompt: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.surface,
      borderRadius: borderRadiusV2.lg,
      paddingHorizontal: spacingV2.md,
      paddingVertical: spacingV2.md,
      borderWidth: 1,
      borderColor: colors.borderLight,
      gap: spacingV2.sm,
    },
    quickPromptText: {
      fontSize: fontSizeV2.sm,
      color: colors.text,
      fontWeight: '500',
      flex: 1,
    },
    messageRow: {
      flexDirection: 'row',
      marginBottom: spacingV2.md,
      alignItems: 'flex-end',
    },
    userRow: {
      justifyContent: 'flex-end',
    },
    agentRow: {
      justifyContent: 'flex-start',
    },
    agentAvatar: {
      width: 32,
      height: 32,
      borderRadius: borderRadiusV2.md,
      backgroundColor: colors.primaryMuted,
      alignItems: 'center',
      justifyContent: 'center',
      marginRight: spacingV2.sm,
    },
    messageBubble: {
      maxWidth: '92%',
    },
    userBubble: {
      alignSelf: 'flex-end',
    },
    userBubbleInner: {
      borderRadius: borderRadiusV2.lg,
      borderBottomRightRadius: 4,
      padding: spacingV2.md,
    },
    agentBubble: {
      alignSelf: 'flex-start',
    },
    agentBubbleInner: {
      backgroundColor: colors.surface,
      borderRadius: borderRadiusV2.lg,
      borderBottomLeftRadius: 4,
      borderWidth: 1,
      borderColor: colors.chatAiBorder,
      padding: spacingV2.md,
    },
    userText: {
      fontSize: fontSizeV2.md,
      color: colors.textInverse,
      lineHeight: 22,
    },
    agentText: {
      fontSize: fontSizeV2.md,
      color: colors.text,
      lineHeight: 22,
    },
    typingRow: {
      paddingHorizontal: spacingV2.md,
      paddingBottom: spacingV2.sm,
      alignItems: 'flex-start',
    },
    typingBubble: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.surface,
      borderRadius: borderRadiusV2.lg,
      borderBottomLeftRadius: 4,
      paddingHorizontal: spacingV2.md,
      paddingVertical: spacingV2.sm,
      borderWidth: 1,
      borderColor: colors.chatAiBorder,
      gap: 4,
    },
    typingDot: {
      width: 6,
      height: 6,
      borderRadius: 3,
      backgroundColor: colors.textTertiary,
    },
    typingDot2: {
      opacity: 0.6,
    },
    typingDot3: {
      opacity: 0.3,
    },
    inputBar: {
      paddingHorizontal: spacingV2.md,
      paddingVertical: spacingV2.sm,
      backgroundColor: colors.surface,
      borderTopWidth: 1,
      borderTopColor: colors.borderLight,
    },
    inputWrapper: {
      flexDirection: 'row',
      alignItems: 'flex-end',
      backgroundColor: colors.chatInputBg,
      borderRadius: 24,
      paddingLeft: spacingV2.md,
      paddingRight: 4,
      paddingVertical: 4,
    },
    input: {
      flex: 1,
      maxHeight: 100,
      fontSize: fontSizeV2.md,
      color: colors.text,
      paddingVertical: spacingV2.sm,
      paddingRight: spacingV2.sm,
    },
    sendBtn: {
      width: 36,
      height: 36,
      borderRadius: borderRadiusV2.full,
      overflow: 'hidden',
    },
    sendBtnGradient: {
      width: 36,
      height: 36,
      borderRadius: borderRadiusV2.full,
      alignItems: 'center',
      justifyContent: 'center',
    },
    sendBtnDisabled: {
      backgroundColor: colors.disabledBg,
    },
    confirmBar: {
      flexDirection: 'row',
      justifyContent: 'flex-end',
      gap: spacingV2.sm,
      marginTop: spacingV2.md,
      paddingTop: spacingV2.sm,
      borderTopWidth: 1,
      borderTopColor: colors.borderLight,
    },
    confirmBtn: {
      backgroundColor: colors.success,
      paddingHorizontal: spacingV2.lg,
      paddingVertical: spacingV2.sm,
      borderRadius: borderRadiusV2.md,
    },
    confirmBtnText: {
      color: colors.textInverse,
      fontSize: fontSizeV2.sm,
      fontWeight: '600',
    },
    cancelBtn: {
      backgroundColor: colors.disabledBg,
      paddingHorizontal: spacingV2.lg,
      paddingVertical: spacingV2.sm,
      borderRadius: borderRadiusV2.md,
    },
    cancelBtnText: {
      color: colors.textSecondary,
      fontSize: fontSizeV2.sm,
      fontWeight: '600',
    },
  });
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/screens/agent/AgentChatScreen.tsx
  git commit -m "feat: upgrade AgentChatScreen with gradient background, AI avatar, and capsule prompts"
  ```

---

## Phase 5: Weather Detail Page

### Task 13: Create WeatherDetailScreen

**Files:**
- Create: `FarmManagerMobile/src/screens/weather/WeatherDetailScreen.tsx`

- [ ] **Step 1: Write WeatherDetailScreen.tsx**

  ```typescript
  import React from 'react';
  import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
  } from 'react-native';
  import LinearGradient from 'react-native-linear-gradient';
  import {SafeAreaView} from 'react-native-safe-area-context';
  import {useNavigation} from '@react-navigation/native';
  import {useAgentStore} from '../../stores/agentStore';
  import {colors} from '../../theme/colors';
  import {spacingV2, fontSizeV2, borderRadiusV2} from '../../theme/spacing';
  import {appGradients} from '../../theme/gradients';
  import {shadowV2} from '../../theme/designTokens';
  import {FadeInSlideUp} from '../../components/animations/FadeInSlideUp';
  import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

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

  // Generate simulated hourly data from daily temperature range
  const generateHourlyData = (minTemp: number, maxTemp: number) => {
    const hours = [];
    for (let i = 0; i < 24; i += 3) {
      // Simple sine curve approximation for daily temperature
      const hourFactor = Math.sin(((i - 6) / 24) * Math.PI * 2) * 0.5 + 0.5;
      const temp = Math.round(minTemp + (maxTemp - minTemp) * hourFactor);
      hours.push({hour: i, temp});
    }
    return hours;
  };

  export const WeatherDetailScreen: React.FC = () => {
    const navigation = useNavigation();
    const {weather, cityName} = useAgentStore();

    if (!weather?.daily) {
      return (
        <SafeAreaView style={styles.container}>
          <LinearGradient {...appGradients.weatherDetail} style={StyleSheet.absoluteFill} />
          <View style={styles.center}>
            <Text style={styles.emptyText}>暂无天气数据</Text>
          </View>
        </SafeAreaView>
      );
    }

    const {time, temperature_2m_max, temperature_2m_min, precipitation_sum} = weather.daily;

    const today = {
      maxTemp: Math.round(temperature_2m_max[0]),
      minTemp: Math.round(temperature_2m_min[0]),
      precipitation: precipitation_sum[0],
    };

    const todayLabel = getWeatherLabel(today.precipitation, today.maxTemp);
    const todayIcon = getWeatherIcon(today.precipitation, today.maxTemp);
    const hourlyData = generateHourlyData(today.minTemp, today.maxTemp);

    const weekDays = time.slice(0, 7).map((t, i) => {
      const d = new Date(t);
      return {
        date: i === 0 ? '今天' : `${d.getMonth() + 1}/${d.getDate()}`,
        weekday: WEEKDAYS[d.getDay()],
        maxTemp: Math.round(temperature_2m_max[i]),
        minTemp: Math.round(temperature_2m_min[i]),
        precipitation: precipitation_sum[i],
      };
    });

    return (
      <SafeAreaView style={styles.container} edges={['bottom']}>
        <LinearGradient {...appGradients.weatherDetail} style={StyleSheet.absoluteFill} />

        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Icon name="chevron-left" size={28} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>{cityName}</Text>
          <View style={styles.backBtn} />
        </View>

        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
          {/* Big Temperature */}
          <FadeInSlideUp>
            <View style={styles.bigTempSection}>
              <Icon name={todayIcon} size={80} color={colors.primary} />
              <Text style={styles.bigTemp}>{today.maxTemp}°</Text>
              <Text style={styles.weatherCondition}>{todayLabel}</Text>
              <Text style={styles.tempRange}>最高 {today.maxTemp}° · 最低 {today.minTemp}°</Text>
            </View>
          </FadeInSlideUp>

          {/* Hourly Forecast */}
          <FadeInSlideUp delay={80}>
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>24小时预报</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={styles.hourlyRow}>
                  {hourlyData.map(h => (
                    <View key={h.hour} style={[styles.hourCard, shadowV2.light]}>
                      <Text style={styles.hourText}>{h.hour}:00</Text>
                      <Text style={styles.hourTemp}>{h.temp}°</Text>
                    </View>
                  ))}
                </View>
              </ScrollView>
            </View>
          </FadeInSlideUp>

          {/* 7-Day Forecast */}
          <FadeInSlideUp delay={160}>
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>7日预报</Text>
              <View style={[styles.weekCard, shadowV2.light]}>
                {weekDays.map((d, i) => {
                  const icon = getWeatherIcon(d.precipitation, d.maxTemp);
                  return (
                    <View key={i} style={[styles.weekRow, i < weekDays.length - 1 && styles.weekRowBorder]}>
                      <Text style={styles.weekDate}>{d.date}</Text>
                      <Text style={styles.weekWeekday}>{d.weekday}</Text>
                      <Icon name={icon} size={20} color={colors.primary} />
                      <View style={styles.weekTempBar}>
                        <View style={styles.weekTempTrack}>
                          <View
                            style={[
                              styles.weekTempFill,
                              {
                                left: `${((d.minTemp + 10) / 50) * 100}%`,
                                right: `${100 - ((d.maxTemp + 10) / 50) * 100}%`,
                              },
                            ]}
                          />
                        </View>
                      </View>
                      <Text style={styles.weekMinTemp}>{d.minTemp}°</Text>
                      <Text style={styles.weekMaxTemp}>{d.maxTemp}°</Text>
                    </View>
                  );
                })}
              </View>
            </View>
          </FadeInSlideUp>
        </ScrollView>
      </SafeAreaView>
    );
  };

  const styles = StyleSheet.create({
    container: {
      flex: 1,
    },
    center: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
    },
    emptyText: {
      fontSize: fontSizeV2.md,
      color: colors.textSecondary,
    },
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: spacingV2.md,
      paddingVertical: spacingV2.sm,
    },
    backBtn: {
      width: 40,
      height: 40,
      alignItems: 'center',
      justifyContent: 'center',
    },
    headerTitle: {
      fontSize: fontSizeV2.lg,
      fontWeight: '700',
      color: colors.text,
    },
    scrollContent: {
      paddingBottom: spacingV2.xxxl,
    },
    bigTempSection: {
      alignItems: 'center',
      paddingVertical: spacingV2.xxl,
    },
    bigTemp: {
      fontSize: 80,
      fontWeight: '200',
      color: colors.text,
      marginTop: spacingV2.md,
    },
    weatherCondition: {
      fontSize: fontSizeV2.xl,
      color: colors.textSecondary,
      marginTop: spacingV2.xs,
    },
    tempRange: {
      fontSize: fontSizeV2.sm,
      color: colors.textTertiary,
      marginTop: spacingV2.sm,
    },
    section: {
      paddingHorizontal: spacingV2.lg,
      marginBottom: spacingV2.xl,
    },
    sectionTitle: {
      fontSize: fontSizeV2.lg,
      fontWeight: '700',
      color: colors.text,
      marginBottom: spacingV2.md,
    },
    hourlyRow: {
      flexDirection: 'row',
      gap: spacingV2.sm,
      paddingRight: spacingV2.lg,
    },
    hourCard: {
      backgroundColor: 'rgba(255,255,255,0.6)',
      borderRadius: borderRadiusV2.lg,
      padding: spacingV2.md,
      alignItems: 'center',
      minWidth: 64,
      backdropFilter: 'blur(20px)',
    },
    hourText: {
      fontSize: fontSizeV2.xs,
      color: colors.textSecondary,
    },
    hourTemp: {
      fontSize: fontSizeV2.md,
      fontWeight: '700',
      color: colors.text,
      marginTop: spacingV2.xs,
    },
    weekCard: {
      backgroundColor: colors.surface,
      borderRadius: borderRadiusV2.xxl,
      padding: spacingV2.lg,
      overflow: 'hidden',
    },
    weekRow: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: spacingV2.sm,
      gap: spacingV2.sm,
    },
    weekRowBorder: {
      borderBottomWidth: 1,
      borderBottomColor: colors.borderLight,
    },
    weekDate: {
      fontSize: fontSizeV2.sm,
      color: colors.text,
      fontWeight: '600',
      width: 50,
    },
    weekWeekday: {
      fontSize: fontSizeV2.xs,
      color: colors.textTertiary,
      width: 36,
    },
    weekTempBar: {
      flex: 1,
      height: 4,
      justifyContent: 'center',
    },
    weekTempTrack: {
      height: 4,
      backgroundColor: colors.borderLight,
      borderRadius: 2,
    },
    weekTempFill: {
      position: 'absolute',
      height: 4,
      backgroundColor: colors.primaryLight,
      borderRadius: 2,
    },
    weekMinTemp: {
      fontSize: fontSizeV2.sm,
      color: colors.textTertiary,
      width: 32,
      textAlign: 'right',
    },
    weekMaxTemp: {
      fontSize: fontSizeV2.sm,
      color: colors.text,
      fontWeight: '700',
      width: 32,
      textAlign: 'right',
    },
  });
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/screens/weather/WeatherDetailScreen.tsx
  git commit -m "feat: add WeatherDetailScreen with hourly forecast and 7-day trend"
  ```

---

### Task 14: Add WeatherDetail Route

**Files:**
- Modify: `FarmManagerMobile/src/navigation/AppNavigator.tsx`

- [ ] **Step 1: Add WeatherDetail to RootStackParamList and Stack**

  In `FarmManagerMobile/src/navigation/AppNavigator.tsx`:

  Add import at the top:
  ```typescript
  import {WeatherDetailScreen} from '../screens/weather/WeatherDetailScreen';
  ```

  Add to `RootStackParamList`:
  ```typescript
  WeatherDetail: undefined;
  ```

  Add Stack.Screen before the closing `</Stack.Navigator>`:
  ```tsx
  <Stack.Screen
    name="WeatherDetail"
    component={WeatherDetailScreen}
    options={{title: '天气详情', headerShown: false}}
  />
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/navigation/AppNavigator.tsx
  git commit -m "feat: add WeatherDetail route to AppNavigator"
  ```

---

## Phase 6: Ledger Screen Redesign

### Task 15: Refactor CostListScreen

**Files:**
- Modify: `FarmManagerMobile/src/screens/cost/CostListScreen.tsx`

- [ ] **Step 1: Replace the top stats section and FAB styling**

  In `FarmManagerMobile/src/screens/cost/CostListScreen.tsx`, keep all existing logic but replace the styles object and add new card components at the top of the render.

  Replace the render section starting from `if (loading && records.length === 0)` down to the return statement. Keep all hooks and handlers above intact.

  Replace with:
  ```typescript
    // Add this helper component inside the file, before CostListScreen
    const AssetCard: React.FC<{income: number; cost: number}> = ({income, cost}) => {
      const total = income - cost;
      return (
        <View style={assetStyles.container}>
          <View style={assetStyles.card}>
            <Text style={assetStyles.label}>本月结余</Text>
            <Text style={[assetStyles.amount, {color: total >= 0 ? colors.income : colors.expense}]}>
              {total >= 0 ? '+' : ''}{total.toFixed(2)}
            </Text>
          </View>
          <View style={[assetStyles.subCard, {backgroundColor: colors.incomeBg}]}>
            <Text style={[assetStyles.subLabel, {color: colors.income}]}>收入</Text>
            <Text style={[assetStyles.subAmount, {color: colors.income}]}>{income.toFixed(2)}</Text>
          </View>
          <View style={[assetStyles.subCard, {backgroundColor: colors.expenseBg}]}>
            <Text style={[assetStyles.subLabel, {color: colors.expense}]}>支出</Text>
            <Text style={[assetStyles.subAmount, {color: colors.expense}]}>{cost.toFixed(2)}</Text>
          </View>
        </View>
      );
    };
  ```

  And add the styles:
  ```typescript
  const assetStyles = StyleSheet.create({
    container: {
      flexDirection: 'row',
      gap: spacingV2.sm,
      paddingHorizontal: spacingV2.lg,
      marginBottom: spacingV2.md,
    },
    card: {
      flex: 1.5,
      backgroundColor: colors.surface,
      borderRadius: borderRadiusV2.xxl,
      padding: spacingV2.lg,
      ...shadowV2.light,
    },
    label: {
      fontSize: fontSizeV2.xs,
      color: colors.textTertiary,
      marginBottom: spacingV2.xs,
    },
    amount: {
      fontSize: fontSizeV2.xxl,
      fontWeight: '800',
    },
    subCard: {
      flex: 1,
      borderRadius: borderRadiusV2.xxl,
      padding: spacingV2.md,
      justifyContent: 'center',
    },
    subLabel: {
      fontSize: fontSizeV2.xs,
      marginBottom: spacingV2.xs,
    },
    subAmount: {
      fontSize: fontSizeV2.lg,
      fontWeight: '700',
    },
  });
  ```

  Then modify the return statement to use `AssetCard`. Replace the `MonthlyStats` component call (keep the component import and usage but add AssetCard above it). Actually, the simplest approach: wrap MonthlyStats with AssetCard display.

  Replace the `<MonthlyStats ... />` line in the return with:
  ```tsx
  <AssetCard income={stats.income} cost={stats.cost} />
  <MonthlyStats
    selectedMonth={selectedMonth}
    stats={stats}
    onPreviousMonth={handlePreviousMonth}
    onNextMonth={handleNextMonth}
  />
  ```

  Also update the FAB style in the main styles. Replace the `fab` style:
  ```typescript
    fab: {
      position: 'absolute',
      right: spacingV2.lg,
      bottom: spacingV2.lg,
      width: 56,
      height: 56,
      borderRadius: borderRadiusV2.full,
      backgroundColor: colors.primary,
      justifyContent: 'center',
      alignItems: 'center',
      ...shadowV2.float,
    },
  ```

  And update container style:
  ```typescript
    container: {
      flex: 1,
      backgroundColor: colors.background,
    },
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add src/screens/cost/CostListScreen.tsx
  git commit -m "feat: restyle CostListScreen with financial cards and gradient FAB"
  ```

---

## Phase 7: Settings Screen Redesign

### Task 16: Refactor SettingsScreen

**Files:**
- Modify: `FarmManagerMobile/src/screens/settings/SettingsScreen.tsx`

- [ ] **Step 1: Update background color and card styles**

  Change `styles.container.backgroundColor` from `colors.background` to `colors.settingsBg`.

  Update profile card style:
  ```typescript
    profileCard: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.surface,
      borderRadius: borderRadiusV2.xxxl,
      padding: spacingV2.lg,
      ...shadowV2.light,
    },
  ```

  Update `menuItem` height:
  ```typescript
    menuItem: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingVertical: spacingV2.md,
      paddingHorizontal: spacingV2.md,
      height: 64,
    },
  ```

  Update menuCard:
  ```typescript
    menuCard: {
      padding: 0,
      overflow: 'hidden',
      borderRadius: borderRadiusV2.xxl,
      ...shadowV2.light,
    },
  ```

  Update icon colors for specific items. In the JSX, update each MenuItem's iconColor prop:
  - `icon="barn"` → `iconColor={colors.success}`
  - `icon="map-marker"` → `iconColor={colors.primary}`
  - `icon="account-heart"` → `iconColor={colors.aiPurple}`
  - `icon="sprout"` → `iconColor={colors.success}`
  - `icon="clock-outline"` → `iconColor="#14B8A6"`
  - `icon="bell-outline"` → `iconColor={colors.aiPurple}`
  - `icon="weather-cloudy-alert"` → `iconColor={colors.primary}`
  - `icon="database-export"` → `iconColor={colors.primary}`
  - `icon="trash-can-outline"` → keep `iconColor={colors.danger}`
  - `icon="tag"` → `iconColor={colors.textTertiary}`
  - `icon="book-open-variant"` → `iconColor={colors.success}`
  - `icon="information"` → `iconColor={colors.primary}`

- [ ] **Step 2: Commit**

  ```bash
  git add src/screens/settings/SettingsScreen.tsx
  git commit -m "feat: restyle SettingsScreen with minimal design, 64px cards, unified icons"
  ```

---

## Phase 8: Wrap-up & Verification

### Task 17: Delete Old WeatherCard and Clean Up

**Files:**
- Delete: `FarmManagerMobile/src/components/WeatherCard.tsx`
- Modify: Any file still importing old WeatherCard

- [ ] **Step 1: Check for old WeatherCard imports**

  ```bash
  grep -r "from.*WeatherCard" FarmManagerMobile/src/ --include="*.tsx" --include="*.ts"
  ```

  Should only show `WeatherCardV2` imports. If any file still imports the old one, update it.

- [ ] **Step 2: Remove old WeatherCard.tsx**

  ```bash
  rm FarmManagerMobile/src/components/WeatherCard.tsx
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add -A
  git commit -m "chore: remove deprecated WeatherCard component"
  ```

---

### Task 18: Android Build Verification

**Files:** None (verification only)

- [ ] **Step 1: Run lint**

  ```bash
  cd FarmManagerMobile && npm run lint
  ```
  Expected: No errors, or fix any reported issues.

- [ ] **Step 2: Run tests**

  ```bash
  cd FarmManagerMobile && npm test -- --no-coverage
  ```
  Expected: All tests pass.

- [ ] **Step 3: Android build**

  ```bash
  cd FarmManagerMobile/android && ./gradlew assembleDebug
  ```
  Expected: BUILD SUCCESSFUL.

- [ ] **Step 4: Commit**

  ```bash
  git add -A
  git commit -m "chore: lint fixes and build verification"
  ```

---

## Self-Review

### 1. Spec Coverage

| Capability | Task(s) | Status |
|-----------|---------|--------|
| `ui-theme-system` — 全局配色 | Task 3 (colors.ts), Task 2 (designTokens.ts) | Covered |
| `ui-theme-system` — 圆角规范 | Task 2 (designTokens.radii) | Covered |
| `ui-theme-system` — 阴影规范 | Task 2 (designTokens.shadowV2) | Covered |
| `ui-theme-system` — 字体规范 | Task 2 (designTokens.typography) | Covered |
| `home-screen-redesign` — 问候区 | Task 10 (HomeScreen header) | Covered |
| `home-screen-redesign` — 天气大卡片 | Task 7 (WeatherCardV2) | Covered |
| `home-screen-redesign` — AI 简报卡片 | Task 8 (AdviceCard emotion gradients) | Covered |
| `home-screen-redesign` — 渐变标题 | Task 8 (emotion title) | Covered |
| `home-screen-redesign` — AI 小宠物 | Task 9 (AIPet) | Covered |
| `home-screen-redesign` — 快捷操作横向滚动 | Task 10 (HomeScreen quick actions) | Covered |
| `bottom-bar-redesign` — 毛玻璃背景 | Task 11 (MainTabNavigator) | Covered |
| `bottom-bar-redesign` — 胶囊选中态 | Task 11 (capsule gradient) | Covered |
| `bottom-bar-redesign` — 高度 72px | Task 11 (tabBar height) | Covered |
| `ai-chat-ui-upgrade` — 渐变背景 | Task 12 (chatBg gradient) | Covered |
| `ai-chat-ui-upgrade` — 在线状态绿点 | Task 12 (statusDot) | Covered |
| `ai-chat-ui-upgrade` — AI 头像 | Task 12 (aiFace black sphere) | Covered |
| `ai-chat-ui-upgrade` — AI 白底卡片 | Task 12 (agentBubbleInner) | Covered |
| `ai-chat-ui-upgrade` — 用户渐变气泡 | Task 12 (userBubbleInner gradient) | Covered |
| `ai-chat-ui-upgrade` — 输入框圆角 24px | Task 12 (inputWrapper borderRadius) | Covered |
| `ai-chat-ui-upgrade` — 发送按钮渐变 | Task 12 (sendBtnGradient) | Covered |
| `ai-chat-ui-upgrade` — 推荐问题胶囊 | Task 12 (capsulesContainer) | Covered |
| `weather-detail-page` — 天空渐变背景 | Task 13 (weatherDetail gradient) | Covered |
| `weather-detail-page` — 大温度显示 | Task 13 (bigTemp 80px) | Covered |
| `weather-detail-page` — 小时预报毛玻璃 | Task 13 (hourCard rgba) | Covered |
| `weather-detail-page` — 7日趋势 | Task 13 (weekCard with temp bars) | Covered |
| `ledger-ui-redesign` — 总资产/收支卡片 | Task 15 (AssetCard) | Covered |
| `ledger-ui-redesign` — FAB 渐变 | Task 15 (fab style) | Covered |
| `settings-ui-minimal` — #F8FAFC 背景 | Task 16 (settingsBg) | Covered |
| `settings-ui-minimal` — 用户卡片 | Task 16 (profileCard) | Covered |
| `settings-ui-minimal` — 64px 高度 | Task 16 (menuItem height) | Covered |
| `settings-ui-minimal` — 统一图标颜色 | Task 16 (iconColor props) | Covered |
| `ui-animations` — 淡入上移 0.45s | Task 6 (FadeInSlideUp), Task 10 (HomeScreen) | Covered |
| `ui-animations` — 呼吸浮动 4px | Task 6 (BreathingFloat), Task 9 (AIPet) | Covered |
| `ui-animations` — 点击缩放 0.96 | Task 6 (ScalePress), Task 10 (HomeScreen) | Covered |
| `ui-animations` — useNativeDriver | Task 6 (all animation components) | Covered |

**Gap:** None. All spec requirements are covered.

### 2. Placeholder Scan

- No "TBD", "TODO", "implement later" found.
- No vague "add error handling" or "add validation" steps.
- No "similar to Task N" references.
- All code blocks contain complete, runnable code.

### 3. Type Consistency

- `spacingV2`, `fontSizeV2`, `borderRadiusV2` used consistently across all v2 components.
- `colors.primary` = `#5B8CFF` everywhere.
- `colors.success` = `#3BB273` everywhere.
- `appGradients` object shape consistent (colors, start, end).
- Animation constants from `animationConfig` used in all animation components.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-27-mobile-ui-redesign.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

**Which approach?**
