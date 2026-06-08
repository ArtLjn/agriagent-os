import React, { useState, useRef, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  Animated,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import LinearGradient from "react-native-linear-gradient";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const { width: SCREEN_W } = Dimensions.get("window");

interface PageData {
  id: string;
  icon: string;
  title: string;
  description: string;
}

const PAGES: PageData[] = [
  {
    id: "1",
    icon: "sprout",
    title: "智能种植规划",
    description: "科学管理作物茬口，追踪生长全周期，让种植更有条理",
  },
  {
    id: "2",
    icon: "robot-happy",
    title: "AI 农事顾问",
    description: "随时解答种植难题，智能识别病虫害，做您的贴身农技专家",
  },
  {
    id: "3",
    icon: "chart-line",
    title: "成本与收益",
    description: "记账统计、利润分析、精准天气预报，用数据驱动决策",
  },
];

// 装饰漂浮圆
const DecoOrb: React.FC<{
  size: number;
  color: string;
  top?: number;
  left?: number;
  right?: number;
  bottom?: number;
}> = ({ size, color, top, left, right, bottom }) => (
  <View
    style={[
      styles.orb,
      {
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: color,
        position: "absolute",
        top,
        left,
        right,
        bottom,
      },
    ]}
  />
);

const OnboardingPage: React.FC<{ page: PageData; index: number }> = ({
  page,
  index,
}) => {
  return (
    <View style={[styles.page, { width: SCREEN_W }]}>
      <View style={styles.pageContent}>
        {/* 图标容器 */}
        <View style={styles.iconWrap}>
          <View style={styles.iconGlow} />
          <View style={styles.iconBox}>
            <Icon name={page.icon} size={48} color="#FFFFFF" />
          </View>
        </View>

        {/* 文字 */}
        <Text style={styles.pageTitle}>{page.title}</Text>
        <Text style={styles.pageDesc}>{page.description}</Text>
      </View>
    </View>
  );
};

export const OnboardingScreen: React.FC<{
  onNavigateToLogin: () => void;
  onNavigateToRegister: () => void;
}> = ({ onNavigateToLogin, onNavigateToRegister }) => {
  const [currentPage, setCurrentPage] = useState(0);
  const scrollX = useRef(new Animated.Value(0)).current;
  const scrollRef = useRef<ScrollView>(null);

  const handleScroll = useCallback(
    Animated.event(
      [{ nativeEvent: { contentOffset: { x: scrollX } } }],
      { useNativeDriver: false }
    ),
    []
  );

  const handleMomentumScrollEnd = useCallback(
    (e: any) => {
      const page = Math.round(e.nativeEvent.contentOffset.x / SCREEN_W);
      setCurrentPage(page);
    },
    []
  );

  const goToNext = useCallback(() => {
    if (currentPage < PAGES.length - 1) {
      scrollRef.current?.scrollTo({
        x: (currentPage + 1) * SCREEN_W,
        animated: true,
      });
    }
  }, [currentPage]);

  const isLastPage = currentPage === PAGES.length - 1;

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      <LinearGradient
        colors={["#051024", "#0C2247", "#1A4A78"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.gradient}
      >
        {/* 装饰圆 */}
        <DecoOrb
          size={320}
          color="rgba(91,140,255,0.05)"
          top={-100}
          left={-120}
        />
        <DecoOrb
          size={220}
          color="rgba(107,154,255,0.06)"
          top={60}
          right={-80}
        />
        <DecoOrb
          size={160}
          color="rgba(91,140,255,0.04)"
          bottom={200}
          left={-40}
        />

        {/* 跳过按钮 */}
        <TouchableOpacity
          style={styles.skipBtn}
          onPress={onNavigateToLogin}
          activeOpacity={0.7}
        >
          <Text style={styles.skipText}>跳过</Text>
        </TouchableOpacity>

        {/* 轮播内容 */}
        <ScrollView
          ref={scrollRef}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          onScroll={handleScroll}
          onMomentumScrollEnd={handleMomentumScrollEnd}
          scrollEventThrottle={16}
          bounces={false}
        >
          {PAGES.map((page, index) => (
            <OnboardingPage key={page.id} page={page} index={index} />
          ))}
        </ScrollView>

        {/* 底部区域 */}
        <View style={styles.bottomArea}>
          {/* 分页指示器 */}
          <View style={styles.dotsRow}>
            {PAGES.map((_, index) => {
              const inputRange = [
                (index - 1) * SCREEN_W,
                index * SCREEN_W,
                (index + 1) * SCREEN_W,
              ];
              const scale = scrollX.interpolate({
                inputRange,
                outputRange: [0.8, 1.2, 0.8],
                extrapolate: "clamp",
              });
              const opacity = scrollX.interpolate({
                inputRange,
                outputRange: [0.4, 1, 0.4],
                extrapolate: "clamp",
              });
              const width = scrollX.interpolate({
                inputRange,
                outputRange: [8, 24, 8],
                extrapolate: "clamp",
              });

              return (
                <Animated.View
                  key={index}
                  style={[
                    styles.dot,
                    {
                      transform: [{ scale }],
                      opacity,
                      width,
                    },
                  ]}
                />
              );
            })}
          </View>

          {/* 按钮 */}
          {isLastPage ? (
            <View style={styles.finalButtons}>
              <TouchableOpacity
                onPress={onNavigateToRegister}
                activeOpacity={0.9}
              >
                <LinearGradient
                  colors={["#3B6FE0", "#5B9AFF"]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 0 }}
                  style={styles.primaryButton}
                >
                  <Text style={styles.primaryButtonText}>开始使用</Text>
                </LinearGradient>
              </TouchableOpacity>

              <TouchableOpacity
                onPress={onNavigateToLogin}
                activeOpacity={0.7}
                style={styles.secondaryButton}
              >
                <Text style={styles.secondaryButtonText}>
                  已有账号？登录
                </Text>
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity
              onPress={goToNext}
              activeOpacity={0.9}
            >
              <LinearGradient
                colors={["#3B6FE0", "#5B9AFF"]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={styles.nextButton}
              >
                <Text style={styles.nextButtonText}>下一步</Text>
                <Icon
                  name="arrow-right"
                  size={18}
                  color="#FFFFFF"
                  style={{ marginLeft: 6 }}
                />
              </LinearGradient>
            </TouchableOpacity>
          )}
        </View>
      </LinearGradient>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  gradient: {
    flex: 1,
    position: "relative",
    overflow: "hidden",
  },
  orb: {
    position: "absolute",
  },

  // 跳过按钮
  skipBtn: {
    position: "absolute",
    top: 12,
    right: 20,
    zIndex: 10,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  skipText: {
    fontSize: 14,
    color: "rgba(255,255,255,0.6)",
    fontWeight: "500",
  },

  // 页面
  page: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 40,
  },
  pageContent: {
    alignItems: "center",
    marginTop: -80,
  },

  // 图标
  iconWrap: {
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 40,
  },
  iconGlow: {
    position: "absolute",
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: "rgba(91,140,255,0.1)",
  },
  iconBox: {
    width: 96,
    height: 96,
    borderRadius: 32,
    backgroundColor: "rgba(255,255,255,0.1)",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.15)",
  },

  // 文字
  pageTitle: {
    fontSize: 28,
    fontWeight: "700",
    color: "#FFFFFF",
    marginBottom: 16,
    textAlign: "center",
    letterSpacing: 1,
  },
  pageDesc: {
    fontSize: 16,
    color: "rgba(255,255,255,0.65)",
    textAlign: "center",
    lineHeight: 26,
    maxWidth: 280,
  },

  // 底部区域
  bottomArea: {
    paddingHorizontal: 28,
    paddingBottom: 32,
    alignItems: "center",
  },

  // 分页点
  dotsRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 32,
    height: 8,
  },
  dot: {
    height: 8,
    borderRadius: 4,
    backgroundColor: "#FFFFFF",
    marginHorizontal: 4,
  },

  // 按钮
  nextButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    height: 56,
    borderRadius: 16,
    paddingHorizontal: 48,
    shadowColor: "#3B6FE0",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 8,
  },
  nextButtonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: 2,
  },

  finalButtons: {
    width: "100%",
    alignItems: "center",
  },
  primaryButton: {
    height: 56,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
    width: "100%",
    shadowColor: "#3B6FE0",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 8,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: 2,
  },
  secondaryButton: {
    marginTop: 16,
    paddingVertical: 8,
  },
  secondaryButtonText: {
    fontSize: 15,
    color: "rgba(255,255,255,0.7)",
    fontWeight: "500",
  },
});
