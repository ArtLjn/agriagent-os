import React, { useState, useRef, useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Modal,
  Pressable,
  Dimensions,
  Animated,
  Easing,
} from "react-native";
import LinearGradient from "react-native-linear-gradient";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import { useAgentStore } from "../../stores/agentStore";
import { useAuthStore } from "../../stores/authStore";
import type { ChatMessage } from "../../api/types";
import { MarkdownText } from "../../components/MarkdownText";
import { ReportListView } from "../../components/ReportListView";
import { BreathingFloat } from "../../components/animations/BreathingFloat";
import { FadeInSlideUp } from "../../components/animations/FadeInSlideUp";
import { ScalePress } from "../../components/animations/ScalePress";
import { colors } from "../../theme/colors";
import { farmTheme } from "../../theme/farmTheme";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import { touchOpacity } from "../../theme/animations";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

type PromptTone = "sky" | "leaf" | "amber" | "slate";

const QUICK_PROMPTS: Array<{
  text: string;
  hint: string;
  prompt: string;
  icon: string;
  tone: PromptTone;
}> = [
  {
    text: "天气判断",
    hint: "看能不能打药",
    prompt: "今日天气对作物有什么影响？",
    icon: "weather-partly-cloudy",
    tone: "sky",
  },
  {
    text: "种植建议",
    hint: "按茬口阶段整理",
    prompt: "给我一些种植建议",
    icon: "sprout",
    tone: "leaf",
  },
  {
    text: "病虫害",
    hint: "先判断再处理",
    prompt: "常见的病虫害怎么防治？",
    icon: "bug-outline",
    tone: "amber",
  },
  {
    text: "本周报告",
    hint: "汇总农事和账本",
    prompt: "生成本周种植报告",
    icon: "file-document-outline",
    tone: "slate",
  },
];

const PROMPT_TONES = {
  sky: { bg: "#EEF6FF", icon: "#3D7BD9" },
  leaf: { bg: "#ECFDF3", icon: "#21965F" },
  amber: { bg: "#FFF7E8", icon: "#B7791F" },
  slate: { bg: "#F1F5F9", icon: "#64748B" },
} as const;

const DRAWER_ENTER_MS = 300;
const DRAWER_EXIT_MS = 200;
const DRAWER_EASING = Easing.bezier(0.32, 0.72, 0, 1);

const SESSION_CATEGORY_META: Record<
  string,
  { icon: string; color: string; bg: string }
> = {
  天气: { icon: "weather-partly-cloudy", color: "#3D7BD9", bg: "#EEF6FF" },
  病虫害: { icon: "bug-outline", color: "#B7791F", bg: "#FFF7E8" },
  报告: { icon: "file-document-outline", color: "#64748B", bg: "#F1F5F9" },
  记账: { icon: "cash-plus", color: "#B7791F", bg: "#FFF3E4" },
  种植: { icon: "sprout", color: farmTheme.colors.leaf, bg: "#ECFDF3" },
  对话: {
    icon: "message-text-outline",
    color: farmTheme.colors.leaf,
    bg: farmTheme.colors.leafSoft,
  },
};

const getSessionMeta = (category?: string) =>
  SESSION_CATEGORY_META[category || ""] || SESSION_CATEGORY_META.对话;

const getGreeting = () => {
  const hour = new Date().getHours();
  if (hour < 6) {
    return "夜深了，早点休息";
  }
  if (hour < 12) {
    return "早上好";
  }
  if (hour < 14) {
    return "中午好";
  }
  if (hour < 19) {
    return "下午好";
  }
  return "晚上好";
};

export const AgentChatScreen: React.FC = () => {
  const navigation = useNavigation();
  const { user } = useAuthStore();
  const {
    messages,
    sessions,
    sessionId,
    sendMessage,
    startNewChatSession,
    switchChatSession,
    fetchChatSessions,
    loading: isLoading,
    reports,
    fetchReports,
    deleteReports,
    markPendingActionHandled,
  } = useAgentStore();
  const [inputText, setInputText] = useState("");
  const [activeTab, setActiveTab] = useState<"chat" | "report">("chat");
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [drawerMounted, setDrawerMounted] = useState(false);
  const flatListRef = useRef<FlatList>(null);
  const drawerProgress = useRef(new Animated.Value(0)).current;
  const drawerEnterFrameRef = useRef<number | null>(null);

  const hasMessages = messages.length > 0;

  useEffect(() => {
    if (drawerVisible) {
      drawerProgress.stopAnimation();
      drawerProgress.setValue(0);
      setDrawerMounted(true);
      return;
    }

    if (!drawerMounted) {
      return;
    }

    if (drawerEnterFrameRef.current !== null) {
      cancelAnimationFrame(drawerEnterFrameRef.current);
      drawerEnterFrameRef.current = null;
    }
    drawerProgress.stopAnimation();
    Animated.timing(drawerProgress, {
      toValue: 0,
      duration: DRAWER_EXIT_MS,
      easing: DRAWER_EASING,
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (finished) {
        setDrawerMounted(false);
      }
    });
  }, [drawerMounted, drawerProgress, drawerVisible]);

  useEffect(() => {
    if (!drawerMounted || !drawerVisible) {
      return;
    }

    drawerEnterFrameRef.current = requestAnimationFrame(() => {
      drawerEnterFrameRef.current = null;
      Animated.timing(drawerProgress, {
        toValue: 1,
        duration: DRAWER_ENTER_MS,
        easing: DRAWER_EASING,
        useNativeDriver: true,
      }).start();
    });

    return () => {
      if (drawerEnterFrameRef.current !== null) {
        cancelAnimationFrame(drawerEnterFrameRef.current);
        drawerEnterFrameRef.current = null;
      }
    };
  }, [drawerMounted, drawerProgress, drawerVisible]);

  useEffect(() => {
    if (activeTab === "report") {
      fetchReports();
    }
  }, [activeTab, fetchReports]);

  useEffect(() => {
    fetchChatSessions();
  }, [fetchChatSessions]);

  const handleSend = async (text: string) => {
    if (!text.trim() || isLoading) {
      return;
    }
    setInputText("");
    await sendMessage(text.trim());
    setTimeout(() => {
      flatListRef.current?.scrollToEnd({ animated: true });
    }, 100);
  };

  const handleInputSend = () => {
    handleSend(inputText);
  };

  const handleStartNewSession = () => {
    startNewChatSession();
    setActiveTab("chat");
    setDrawerVisible(false);
  };

  const handleSwitchSession = (nextSessionId: string) => {
    switchChatSession(nextSessionId);
    setActiveTab("chat");
    setDrawerVisible(false);
  };

  const handlePendingAction = (item: ChatMessage, text: "确认" | "取消") => {
    const actionId = item.pending_action?.action_id;
    if (!actionId || item.pending_action_handled || isLoading) {
      return;
    }
    markPendingActionHandled(actionId);
    handleSend(text);
  };

  const renderMessage = ({ item }: { item: ChatMessage }) => {
    const isUser = item.role === "user";
    const hasPendingAction = !isUser && item.pending_action;
    const pendingActionDisabled = Boolean(
      item.pending_action_handled || isLoading
    );
    const showStreamingHint = !isUser && item.is_streaming && !item.content;
    return (
      <View
        style={[styles.messageRow, isUser ? styles.userRow : styles.agentRow]}
      >
        {!isUser && (
          <View style={styles.agentAvatar}>
            <Icon name="sprout" size={14} color={colors.success} />
          </View>
        )}
        <View
          style={[
            styles.messageBubble,
            isUser ? styles.userBubble : styles.agentBubble,
          ]}
        >
          {isUser ? (
            <View style={styles.userBubbleInner}>
              <Text style={styles.userText}>{item.content}</Text>
            </View>
          ) : (
            <View style={styles.agentBubbleInner}>
              {showStreamingHint ? (
                <View style={styles.inlineTyping}>
                  <Text style={styles.inlineTypingText}>正在整理建议</Text>
                  <View style={styles.typingDot} />
                  <View style={[styles.typingDot, styles.typingDot2]} />
                  <View style={[styles.typingDot, styles.typingDot3]} />
                </View>
              ) : (
                <MarkdownText
                  text={item.content}
                  baseStyle={styles.agentText}
                />
              )}
            </View>
          )}
          {hasPendingAction && item.pending_action?.context && (
            <View style={styles.contextBox}>
              {item.pending_action.context.original_input ? (
                <Text style={styles.contextText}>
                  已理解为：{item.pending_action.context.original_input}
                </Text>
              ) : null}
              {item.pending_action.context.notes?.map((note, i) => (
                <Text key={i} style={styles.contextText}>
                  {note}
                </Text>
              ))}
            </View>
          )}
          {hasPendingAction && (
            <View style={styles.confirmBar}>
              <TouchableOpacity
                style={[
                  styles.confirmBtn,
                  pendingActionDisabled && styles.actionBtnDisabled,
                ]}
                onPress={() => handlePendingAction(item, "确认")}
                activeOpacity={touchOpacity.primary}
                disabled={pendingActionDisabled}
              >
                <Icon
                  name="check"
                  size={16}
                  color={pendingActionDisabled ? "#D7DEE7" : "#FFFFFF"}
                />
                <Text style={styles.confirmBtnText}>确认执行</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.cancelBtn,
                  pendingActionDisabled && styles.actionBtnDisabled,
                ]}
                onPress={() => handlePendingAction(item, "取消")}
                activeOpacity={touchOpacity.secondary}
                disabled={pendingActionDisabled}
              >
                <Icon
                  name="close"
                  size={16}
                  color={
                    pendingActionDisabled
                      ? colors.textTertiary
                      : colors.textSecondary
                  }
                />
                <Text style={styles.cancelBtnText}>取消</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </View>
    );
  };

  const renderWelcome = () => {
    const nickname = user?.nickname || "农友";
    const greeting = getGreeting();

    return (
      <View style={styles.welcomeContainer}>
        <FadeInSlideUp delay={40}>
          <View style={styles.heroBlock}>
            <View style={styles.heroTopRow}>
              <View style={styles.heroCopy}>
                <Text style={styles.welcomeEyebrow}>
                  {greeting}，{nickname}
                </Text>
                <Text style={styles.welcomeTitle}>今天要处理什么？</Text>
                <Text style={styles.welcomeSubtitle}>
                  我可以把天气、农事、账本和报告串起来，先帮你理出下一步。
                </Text>
              </View>
              <BreathingFloat>
                <LinearGradient
                  colors={["#F4F9E9", "#FFFFFF"]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                  style={styles.heroIcon}
                >
                  <Icon name="sprout" size={28} color={farmTheme.colors.leaf} />
                </LinearGradient>
              </BreathingFloat>
            </View>
            <View style={styles.heroHintCard}>
              <View style={styles.heroHintIcon}>
                <Icon
                  name="lightbulb-on-outline"
                  size={18}
                  color={farmTheme.colors.soil}
                />
              </View>
              <View style={styles.heroHintCopy}>
                <Text style={styles.heroHintTitle}>你可以直接说一句话</Text>
                <Text style={styles.heroHintText}>
                  比如“昨天买肥料 230 元”或“今天适合巡田吗”
                </Text>
              </View>
            </View>
          </View>
        </FadeInSlideUp>

        <FadeInSlideUp delay={100} style={styles.promptSection}>
          <Text style={styles.promptTitle}>常用场景</Text>
          <View style={styles.promptCards}>
            {QUICK_PROMPTS.map((prompt, index) => (
              <View key={index} style={styles.promptPressable}>
                <ScalePress onPress={() => handleSend(prompt.prompt)}>
                  <View style={styles.promptPill}>
                    <View
                      style={[
                        styles.promptIconBox,
                        { backgroundColor: PROMPT_TONES[prompt.tone].bg },
                      ]}
                    >
                      <Icon
                        name={prompt.icon as any}
                        size={18}
                        color={PROMPT_TONES[prompt.tone].icon}
                      />
                    </View>
                    <View style={styles.promptCopy}>
                      <Text style={styles.promptPillText}>{prompt.text}</Text>
                      <Text style={styles.promptHint} numberOfLines={1}>
                        {prompt.hint}
                      </Text>
                    </View>
                  </View>
                </ScalePress>
              </View>
            ))}
          </View>
        </FadeInSlideUp>
      </View>
    );
  };

  const formatSessionPeriod = (updatedAt: number) => {
    const now = Date.now();
    const diffDays = Math.floor((now - updatedAt) / (24 * 60 * 60 * 1000));
    if (diffDays <= 0) {
      return "今天";
    }
    if (diffDays <= 7) {
      return "7 天内";
    }
    return "30 天内";
  };

  const formatSessionTime = (updatedAt: number) => {
    const date = new Date(updatedAt);
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
      return date.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      });
    }
    return `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
  };

  const renderSessionDrawer = () => {
    if (!drawerMounted) {
      return null;
    }

    const orderedSessions = [...sessions].sort(
      (a, b) => b.updatedAt - a.updatedAt
    );
    const renderedPeriods = new Set<string>();
    const drawerWidth = Math.min(Dimensions.get("window").width * 0.86, 360);
    const drawerTranslateX = drawerProgress.interpolate({
      inputRange: [0, 1],
      outputRange: [-drawerWidth, 0],
    });
    const drawerScale = drawerProgress.interpolate({
      inputRange: [0, 1],
      outputRange: [0.985, 1],
    });
    const scrimOpacity = drawerProgress.interpolate({
      inputRange: [0, 1],
      outputRange: [0, 1],
    });
    const contentTranslateX = drawerProgress.interpolate({
      inputRange: [0, 1],
      outputRange: [-18, 0],
    });
    const contentOpacity = drawerProgress.interpolate({
      inputRange: [0, 0.55, 1],
      outputRange: [0, 0.4, 1],
    });
    const sessionTranslateX = drawerProgress.interpolate({
      inputRange: [0, 1],
      outputRange: [-10, 0],
    });
    const sessionOpacity = drawerProgress.interpolate({
      inputRange: [0, 0.72, 1],
      outputRange: [0, 0.55, 1],
    });

    return (
      <Modal
        visible={drawerMounted}
        transparent
        animationType="none"
        onRequestClose={() => setDrawerVisible(false)}
      >
        <View style={styles.drawerRoot}>
          <Animated.View
            pointerEvents={drawerVisible ? "auto" : "none"}
            style={[styles.drawerScrim, { opacity: scrimOpacity }]}
          >
            <Pressable
              style={StyleSheet.absoluteFill}
              onPress={() => setDrawerVisible(false)}
            />
          </Animated.View>
          <Animated.View
            style={[
              styles.drawerPanel,
              {
                width: drawerWidth,
                transform: [
                  { translateX: drawerTranslateX },
                  { scale: drawerScale },
                ],
              },
            ]}
          >
            <Animated.View
              style={{
                opacity: contentOpacity,
                transform: [{ translateX: contentTranslateX }],
              }}
            >
              <View style={styles.drawerTop}>
                <TouchableOpacity
                  style={styles.drawerIconBtn}
                  onPress={() => setDrawerVisible(false)}
                  activeOpacity={touchOpacity.icon}
                >
                  <Icon
                    name="menu-open"
                    size={24}
                    color={farmTheme.colors.ink}
                  />
                </TouchableOpacity>
                <View style={styles.drawerActionRow}>
                  <TouchableOpacity
                    style={styles.drawerIconBtn}
                    activeOpacity={touchOpacity.icon}
                  >
                    <Icon
                      name="magnify"
                      size={22}
                      color={farmTheme.colors.ink}
                    />
                  </TouchableOpacity>
                </View>
              </View>

              <View style={styles.memoryHero}>
                <View style={styles.memoryHeroGlow} />
                <View style={styles.memoryHeroIcon}>
                  <Icon name="history" size={24} color="#FFFFFF" />
                </View>
                <Text style={styles.memoryHeroEyebrow}>芽芽记忆库</Text>
                <Text style={styles.memoryHeroTitle}>历史农事对话</Text>
                <Text style={styles.memoryHeroMeta}>
                  已沉淀 {orderedSessions.length} 个会话，方便继续追问和补录
                </Text>
              </View>
            </Animated.View>

            <Animated.View
              style={{
                opacity: contentOpacity,
                transform: [{ translateX: contentTranslateX }],
              }}
            >
              <TouchableOpacity
                style={styles.newSessionCard}
                onPress={handleStartNewSession}
                activeOpacity={touchOpacity.card}
              >
                <View style={styles.newSessionIcon}>
                  <Icon
                    name="message-plus-outline"
                    size={22}
                    color={farmTheme.colors.leaf}
                  />
                </View>
                <View style={styles.newSessionCopy}>
                  <Text style={styles.newSessionText}>开启新对话</Text>
                  <Text style={styles.newSessionMeta}>
                    重新问天气、记账或生成报告
                  </Text>
                </View>
                <Icon
                  name="chevron-right"
                  size={22}
                  color={colors.textTertiary}
                />
              </TouchableOpacity>
            </Animated.View>

            <Animated.View
              style={[
                styles.drawerHeading,
                {
                  opacity: contentOpacity,
                  transform: [{ translateX: contentTranslateX }],
                },
              ]}
            >
              <Text style={styles.drawerTitle}>会话列表</Text>
              <View style={styles.drawerFilter}>
                <Text style={styles.drawerFilterText}>农事对话</Text>
                <Icon
                  name="filter-variant"
                  size={18}
                  color={colors.textSecondary}
                />
              </View>
            </Animated.View>

            <Animated.View
              style={[
                styles.sessionListWrap,
                {
                  opacity: contentOpacity,
                  transform: [{ translateX: contentTranslateX }],
                },
              ]}
            >
              <ScrollView
                style={styles.sessionList}
                showsVerticalScrollIndicator={false}
              >
                {orderedSessions.map((session) => {
                  const period = formatSessionPeriod(session.updatedAt);
                  const shouldShowPeriod = !renderedPeriods.has(period);
                  renderedPeriods.add(period);
                  const isActive = session.id === sessionId;
                  const meta = getSessionMeta(session.category);
                  return (
                    <View key={session.id}>
                      {shouldShowPeriod && (
                        <Text style={styles.sessionPeriod}>{period}</Text>
                      )}
                      <Animated.View
                        style={{
                          opacity: sessionOpacity,
                          transform: [{ translateX: sessionTranslateX }],
                        }}
                      >
                        <TouchableOpacity
                          style={[
                            styles.sessionItem,
                            isActive && styles.sessionItemActive,
                          ]}
                          onPress={() => handleSwitchSession(session.id)}
                          activeOpacity={touchOpacity.card}
                        >
                          {isActive && (
                            <View style={styles.sessionActiveRail} />
                          )}
                          <View
                            style={[
                              styles.sessionIcon,
                              { backgroundColor: meta.bg },
                            ]}
                          >
                            <Icon
                              name={meta.icon}
                              size={18}
                              color={meta.color}
                            />
                          </View>
                          <View style={styles.sessionCopy}>
                            <View style={styles.sessionTitleRow}>
                              <Text
                                style={[
                                  styles.sessionTitle,
                                  isActive && styles.sessionTitleActive,
                                ]}
                                numberOfLines={1}
                              >
                                {session.title}
                              </Text>
                              {isActive && (
                                <View style={styles.sessionLiveBadge}>
                                  <Text style={styles.sessionLiveBadgeText}>
                                    当前
                                  </Text>
                                </View>
                              )}
                            </View>
                            <Text
                              style={styles.sessionPreview}
                              numberOfLines={1}
                            >
                              {session.preview || "点击继续这轮农事对话"}
                            </Text>
                            <View style={styles.sessionMetaRow}>
                              <Text style={styles.sessionTag}>
                                {session.category || "对话"}
                              </Text>
                              <Text style={styles.sessionTime}>
                                {formatSessionTime(session.updatedAt)}
                              </Text>
                            </View>
                          </View>
                          <Icon
                            name="chevron-right"
                            size={18}
                            color={
                              isActive
                                ? farmTheme.colors.leaf
                                : colors.textTertiary
                            }
                          />
                        </TouchableOpacity>
                      </Animated.View>
                    </View>
                  );
                })}
                {orderedSessions.length === 0 && (
                  <View style={styles.emptySessionCard}>
                    <Icon
                      name="chat-processing-outline"
                      size={24}
                      color={farmTheme.colors.leaf}
                    />
                    <Text style={styles.emptySessionTitle}>还没有历史对话</Text>
                    <Text style={styles.emptySessionText}>
                      开启一次问答后，会自动保存在这里。
                    </Text>
                  </View>
                )}
              </ScrollView>
            </Animated.View>

            <Animated.View
              style={[
                styles.drawerFooter,
                {
                  opacity: contentOpacity,
                  transform: [{ translateX: contentTranslateX }],
                },
              ]}
            >
              <View style={styles.drawerUser}>
                <LinearGradient
                  colors={[farmTheme.colors.leaf, farmTheme.colors.leafDark]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                  style={styles.drawerUserAvatar}
                >
                  <Text style={styles.drawerUserAvatarText}>农</Text>
                </LinearGradient>
                <View style={styles.drawerUserCopy}>
                  <Text style={styles.drawerUserName} numberOfLines={1}>
                    {user?.nickname || "系统管理员"}
                  </Text>
                  <Text style={styles.drawerUserMeta}>本地农场账号</Text>
                </View>
              </View>
              <TouchableOpacity
                style={styles.drawerIconBtn}
                activeOpacity={touchOpacity.icon}
              >
                <Icon
                  name="cog-outline"
                  size={23}
                  color={farmTheme.colors.ink}
                />
              </TouchableOpacity>
            </Animated.View>
          </Animated.View>
        </View>
      </Modal>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={StyleSheet.absoluteFill} />

      {/* Header */}
      <View style={styles.header}>
        <ScalePress onPress={() => setDrawerVisible(true)}>
          <View style={styles.headerMenuBtn}>
            <Icon name="menu" size={23} color={farmTheme.colors.ink} />
          </View>
        </ScalePress>
        <View style={styles.headerLeft}>
          <View style={styles.headerAvatar}>
            <Icon name="sprout" size={18} color={farmTheme.colors.leaf} />
          </View>
          <View>
            <Text style={styles.headerTitle}>芽芽</Text>
            <View style={styles.statusRow}>
              <View style={styles.statusDot} />
              <Text style={styles.headerSubtitle}>农事顾问 · 正在待命</Text>
            </View>
          </View>
        </View>
        <ScalePress onPress={handleStartNewSession}>
          <View style={styles.headerNewBtn}>
            <Icon name="plus" size={22} color={farmTheme.colors.ink} />
          </View>
        </ScalePress>
      </View>

      {/* SegmentedControl */}
      <View style={styles.segmentRow}>
        <TouchableOpacity
          style={[styles.segBtn, activeTab === "chat" && styles.segBtnActive]}
          onPress={() => setActiveTab("chat")}
          activeOpacity={touchOpacity.primary}
        >
          <Text
            style={[
              styles.segText,
              activeTab === "chat" && styles.segTextActive,
            ]}
          >
            对话
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.segBtn, activeTab === "report" && styles.segBtnActive]}
          onPress={() => setActiveTab("report")}
          activeOpacity={touchOpacity.primary}
        >
          <Text
            style={[
              styles.segText,
              activeTab === "report" && styles.segTextActive,
            ]}
          >
            报告
          </Text>
        </TouchableOpacity>
      </View>

      {activeTab === "chat" ? (
        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          keyboardVerticalOffset={8}
        >
          {/* Messages Area */}
          <View style={styles.flex}>
            {hasMessages ? (
              <FlatList
                ref={flatListRef}
                data={messages}
                keyExtractor={(_, index) => String(index)}
                renderItem={renderMessage}
                contentContainerStyle={styles.listContent}
                onContentSizeChange={() =>
                  flatListRef.current?.scrollToEnd({ animated: true })
                }
              />
            ) : (
              <ScrollView
                contentContainerStyle={styles.welcomeScrollContent}
                showsVerticalScrollIndicator={false}
              >
                {renderWelcome()}
              </ScrollView>
            )}

            {isLoading &&
              hasMessages &&
              !messages[messages.length - 1]?.is_streaming && (
                <View style={styles.typingRow}>
                  <View style={styles.agentAvatarSmall}>
                    <Icon name="sprout" size={10} color={colors.success} />
                  </View>
                  <View style={styles.typingBubble}>
                    <View style={styles.typingDot} />
                    <View style={[styles.typingDot, styles.typingDot2]} />
                    <View style={[styles.typingDot, styles.typingDot3]} />
                  </View>
                </View>
              )}
          </View>

          {/* Input */}
          <View style={styles.inputBar}>
            <View style={styles.inputWrapper}>
              <TouchableOpacity
                style={styles.inputToolBtn}
                activeOpacity={touchOpacity.icon}
              >
                <Icon
                  name="microphone-outline"
                  size={20}
                  color={farmTheme.colors.leaf}
                />
              </TouchableOpacity>
              <TextInput
                style={styles.input}
                value={inputText}
                onChangeText={setInputText}
                placeholder="问农事、记一笔、生成报告..."
                placeholderTextColor={colors.textTertiary}
                multiline
                maxLength={500}
              />
              <TouchableOpacity
                style={[
                  styles.sendBtn,
                  (!inputText.trim() || isLoading) && styles.sendBtnDisabled,
                ]}
                onPress={handleInputSend}
                disabled={!inputText.trim() || isLoading}
                activeOpacity={touchOpacity.primary}
              >
                <Icon
                  name="arrow-up"
                  size={18}
                  color={!inputText.trim() || isLoading ? "#B0B8C1" : "#FFFFFF"}
                />
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      ) : (
        <ReportListView
          reports={reports}
          onGenerate={() => navigation.navigate("AgentReport" as never)}
          onDeleteReports={deleteReports}
          onViewReport={(r) =>
            (navigation as any).navigate("AgentReport", {
              content: r.content,
              reportType: r.report_type,
              createdAt: r.created_at,
              reportId: r.id,
              structuredData: r.structured_data,
            })
          }
        />
      )}
      {renderSessionDrawer()}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: farmTheme.colors.page,
  },
  flex: {
    flex: 1,
  },

  // ─── Header ───
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.lg,
    paddingBottom: spacingV2.md,
    backgroundColor: "transparent",
  },
  headerMenuBtn: {
    width: 42,
    height: 42,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.surface,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
    marginLeft: spacingV2.md,
    minWidth: 0,
  },
  headerAvatar: {
    width: 42,
    height: 42,
    borderRadius: 17,
    backgroundColor: farmTheme.colors.leafSoft,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.md,
  },
  headerTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "900",
    color: colors.text,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
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
    fontWeight: "600",
  },
  headerNewBtn: {
    width: 42,
    height: 42,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.surface,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },

  // ─── Segment ───
  segmentRow: {
    flexDirection: "row",
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.md,
    backgroundColor: farmTheme.colors.surfaceSoft,
    borderRadius: borderRadiusV2.tab,
    padding: 4,
  },
  segBtn: {
    flex: 1,
    minHeight: 42,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: borderRadiusV2.full,
  },
  segBtnActive: {
    backgroundColor: farmTheme.colors.surface,
    ...farmTheme.shadow.card,
  },
  segText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  segTextActive: {
    color: colors.text,
  },
  listContent: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.lg,
    paddingBottom: spacingV2.xxl,
  },

  // ─── Welcome — left-aligned ───
  welcomeScrollContent: {
    flexGrow: 1,
    justifyContent: "flex-start",
  },
  welcomeContainer: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.lg,
  },
  heroBlock: {
    borderRadius: farmTheme.radius.panel,
    backgroundColor: "#254130",
    padding: spacingV2.lg,
    marginBottom: spacingV2.lg,
    overflow: "hidden",
    ...farmTheme.shadow.float,
  },
  heroTopRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacingV2.md,
  },
  heroIcon: {
    width: 58,
    height: 58,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#D8F0BC",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.2,
    shadowRadius: 18,
    elevation: 5,
  },
  heroCopy: {
    flex: 1,
    maxWidth: 360,
  },
  welcomeEyebrow: {
    fontSize: fontSizeV2.sm,
    color: "rgba(228, 242, 214, 0.76)",
    fontWeight: "800",
    marginBottom: spacingV2.sm,
  },
  welcomeTitle: {
    fontSize: 25,
    fontWeight: "900",
    color: "#FFFFFF",
    lineHeight: 31,
    marginBottom: spacingV2.sm,
  },
  welcomeSubtitle: {
    fontSize: fontSizeV2.sm,
    color: "rgba(255, 255, 255, 0.72)",
    lineHeight: 21,
  },
  heroHintCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
    marginTop: spacingV2.lg,
    padding: spacingV2.md,
    borderRadius: 22,
    backgroundColor: "rgba(255, 255, 255, 0.10)",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.10)",
  },
  heroHintIcon: {
    width: 40,
    height: 40,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFF6DC",
  },
  heroHintCopy: {
    flex: 1,
    minWidth: 0,
  },
  heroHintTitle: {
    fontSize: fontSizeV2.sm,
    color: "#FFFFFF",
    fontWeight: "800",
    marginBottom: 2,
  },
  heroHintText: {
    fontSize: fontSizeV2.xs,
    color: "rgba(255, 255, 255, 0.62)",
    fontWeight: "600",
  },

  // ─── Prompt pills ───
  promptSection: {
    marginTop: 0,
  },
  promptTitle: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    fontWeight: "700",
    marginBottom: spacingV2.md,
  },
  promptCards: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.md,
  },
  promptPressable: {
    width: "48%",
  },
  promptPill: {
    width: "100%",
    minHeight: 72,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: farmTheme.colors.surface,
    borderRadius: 24,
    padding: spacingV2.md,
    gap: spacingV2.md,
    ...farmTheme.shadow.card,
  },
  promptIconBox: {
    width: 32,
    height: 32,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  promptPillText: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "900",
    lineHeight: 18,
  },
  promptCopy: {
    flex: 1,
    minWidth: 0,
  },
  promptHint: {
    marginTop: 3,
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    fontWeight: "600",
  },

  // ─── Messages ───
  messageRow: {
    flexDirection: "row",
    marginBottom: spacingV2.lg,
    alignItems: "flex-end",
  },
  userRow: {
    justifyContent: "flex-end",
  },
  agentRow: {
    justifyContent: "flex-start",
  },
  agentAvatar: {
    width: 32,
    height: 32,
    borderRadius: 12,
    backgroundColor: farmTheme.colors.leafSoft,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.sm,
  },
  agentAvatarSmall: {
    width: 24,
    height: 24,
    borderRadius: 8,
    backgroundColor: farmTheme.colors.leafSoft,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.sm,
  },
  messageBubble: {
    maxWidth: "86%",
  },
  userBubble: {
    alignSelf: "flex-end",
  },
  userBubbleInner: {
    backgroundColor: farmTheme.colors.leaf,
    borderRadius: borderRadiusV2.xxl,
    borderBottomRightRadius: 8,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    shadowColor: farmTheme.colors.leaf,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.16,
    shadowRadius: 16,
    elevation: 4,
  },
  agentBubble: {
    alignSelf: "flex-start",
  },
  agentBubbleInner: {
    backgroundColor: farmTheme.colors.surface,
    borderRadius: borderRadiusV2.xxl,
    borderBottomLeftRadius: 8,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  userText: {
    fontSize: fontSizeV2.md,
    color: "#FFFFFF",
    lineHeight: 23,
  },
  agentText: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    lineHeight: 24,
  },
  inlineTyping: {
    minHeight: 24,
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  inlineTypingText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginRight: 2,
  },

  // ─── Typing indicator ───
  typingRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    paddingHorizontal: spacingV2.md,
    paddingBottom: spacingV2.sm,
  },
  typingBubble: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: farmTheme.colors.surface,
    borderRadius: borderRadiusV2.lg,
    borderBottomLeftRadius: 4,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    gap: 4,
  },
  typingDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: farmTheme.colors.leaf,
  },
  typingDot2: {
    opacity: 0.4,
  },
  typingDot3: {
    opacity: 0.2,
  },

  // ─── Input bar ───
  inputBar: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.lg,
    backgroundColor: "rgba(247, 250, 241, 0.96)",
    borderTopWidth: 1,
    borderTopColor: farmTheme.colors.line,
  },
  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: farmTheme.colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingLeft: 6,
    paddingRight: 6,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  inputToolBtn: {
    width: 40,
    height: 40,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.leafSoft,
    marginRight: spacingV2.xs,
  },
  input: {
    flex: 1,
    maxHeight: 100,
    fontSize: fontSizeV2.md,
    color: colors.text,
    paddingTop: Platform.OS === "web" ? 9 : spacingV2.sm,
    paddingBottom: Platform.OS === "web" ? 9 : spacingV2.sm,
    paddingRight: spacingV2.sm,
    minHeight: 40,
    textAlignVertical: "center",
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.leaf,
    shadowColor: farmTheme.colors.leaf,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 14,
    elevation: 4,
  },
  sendBtnDisabled: {
    backgroundColor: "rgba(226, 232, 240, 0.88)",
    shadowOpacity: 0,
  },

  // ─── Context box ───
  contextBox: {
    marginTop: spacingV2.sm,
    padding: spacingV2.md,
    backgroundColor: farmTheme.colors.leafSoft,
    borderRadius: borderRadiusV2.lg,
  },
  contextText: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 20,
  },

  // ─── Confirm bar ───
  confirmBar: {
    flexDirection: "row",
    justifyContent: "flex-start",
    gap: spacingV2.sm,
    marginTop: spacingV2.md,
    paddingTop: spacingV2.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  confirmBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: farmTheme.colors.leaf,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
  },
  confirmBtnText: {
    color: "#FFFFFF",
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
  },
  cancelBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: farmTheme.colors.surfaceSoft,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
  },
  actionBtnDisabled: {
    opacity: 0.52,
  },
  cancelBtnText: {
    color: colors.textSecondary,
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
  },

  // ─── Session drawer ───
  drawerRoot: {
    flex: 1,
    flexDirection: "row",
  },
  drawerScrim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(15, 23, 42, 0.42)",
  },
  drawerPanel: {
    height: "100%",
    backgroundColor: farmTheme.colors.page,
    paddingTop: Platform.OS === "ios" ? 52 : spacingV2.xl,
    paddingHorizontal: spacingV2.lg,
    paddingBottom: spacingV2.lg,
    borderRightWidth: 1,
    borderRightColor: farmTheme.colors.line,
    shadowColor: farmTheme.colors.leaf,
    shadowOffset: { width: 16, height: 0 },
    shadowOpacity: 0.14,
    shadowRadius: 28,
    elevation: 12,
  },
  drawerTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.md,
    gap: spacingV2.sm,
  },
  drawerActionRow: {
    flexDirection: "row",
    gap: spacingV2.sm,
  },
  drawerIconBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.surface,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  memoryHero: {
    minHeight: 154,
    borderRadius: farmTheme.radius.panel,
    backgroundColor: "#254130",
    padding: spacingV2.lg,
    marginBottom: spacingV2.lg,
    overflow: "hidden",
    ...farmTheme.shadow.float,
  },
  memoryHeroGlow: {
    position: "absolute",
    width: 132,
    height: 132,
    borderRadius: 66,
    backgroundColor: "rgba(216, 240, 188, 0.14)",
    right: -36,
    top: -36,
  },
  memoryHeroIcon: {
    width: 48,
    height: 48,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255, 255, 255, 0.14)",
    marginBottom: spacingV2.md,
  },
  memoryHeroEyebrow: {
    fontSize: fontSizeV2.xs,
    color: "rgba(228, 242, 214, 0.72)",
    fontWeight: "800",
    marginBottom: spacingV2.xs,
  },
  memoryHeroTitle: {
    fontSize: 22,
    lineHeight: 28,
    color: "#FFFFFF",
    fontWeight: "900",
  },
  memoryHeroMeta: {
    marginTop: spacingV2.sm,
    fontSize: fontSizeV2.xs,
    lineHeight: 18,
    color: "rgba(255, 255, 255, 0.66)",
    fontWeight: "600",
  },
  newSessionCard: {
    minHeight: 62,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: farmTheme.colors.surface,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    marginBottom: spacingV2.xl,
    ...farmTheme.shadow.card,
  },
  newSessionIcon: {
    width: 40,
    height: 40,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.leafSoft,
  },
  newSessionCopy: {
    flex: 1,
    minWidth: 0,
  },
  newSessionText: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "900",
  },
  newSessionMeta: {
    marginTop: 3,
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  drawerHeading: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.md,
  },
  drawerTitle: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "900",
  },
  drawerFilter: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  drawerFilterText: {
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  sessionListWrap: {
    flex: 1,
    minHeight: 0,
  },
  sessionList: {
    flex: 1,
  },
  sessionPeriod: {
    marginTop: spacingV2.md,
    marginBottom: spacingV2.sm,
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    fontWeight: "700",
  },
  sessionItem: {
    position: "relative",
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
    padding: spacingV2.md,
    borderRadius: 22,
    marginBottom: spacingV2.sm,
    backgroundColor: farmTheme.colors.surface,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    overflow: "hidden",
    ...farmTheme.shadow.card,
  },
  sessionItemActive: {
    backgroundColor: "#EAF7EE",
    borderColor: "rgba(59, 178, 115, 0.24)",
  },
  sessionActiveRail: {
    position: "absolute",
    left: 0,
    top: 14,
    bottom: 14,
    width: 4,
    borderTopRightRadius: 4,
    borderBottomRightRadius: 4,
    backgroundColor: farmTheme.colors.leaf,
  },
  sessionIcon: {
    width: 40,
    height: 40,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  sessionCopy: {
    flex: 1,
    minWidth: 0,
  },
  sessionTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
  },
  sessionTitle: {
    flex: 1,
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "900",
    lineHeight: 20,
  },
  sessionTitleActive: {
    color: "#147A4C",
  },
  sessionLiveBadge: {
    paddingHorizontal: spacingV2.sm,
    paddingVertical: 2,
    borderRadius: borderRadiusV2.full,
    backgroundColor: farmTheme.colors.leaf,
  },
  sessionLiveBadgeText: {
    fontSize: 10,
    color: "#FFFFFF",
    fontWeight: "900",
  },
  sessionPreview: {
    marginTop: 3,
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  sessionMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    marginTop: spacingV2.xs,
  },
  sessionTag: {
    overflow: "hidden",
    paddingHorizontal: spacingV2.sm,
    paddingVertical: 2,
    borderRadius: borderRadiusV2.full,
    backgroundColor: farmTheme.colors.surface,
    borderWidth: 1,
    borderColor: "rgba(59, 178, 115, 0.18)",
    color: farmTheme.colors.leaf,
    fontSize: 11,
    fontWeight: "700",
  },
  sessionTime: {
    flex: 1,
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
  },
  emptySessionCard: {
    alignItems: "center",
    justifyContent: "center",
    padding: spacingV2.xl,
    borderRadius: 24,
    backgroundColor: farmTheme.colors.surface,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  emptySessionTitle: {
    marginTop: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: farmTheme.colors.ink,
    fontWeight: "900",
  },
  emptySessionText: {
    marginTop: spacingV2.xs,
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    lineHeight: 18,
    textAlign: "center",
  },
  drawerFooter: {
    minHeight: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingV2.md,
    borderTopWidth: 1,
    borderTopColor: farmTheme.colors.line,
    paddingTop: spacingV2.md,
  },
  drawerUser: {
    flex: 1,
    minWidth: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  drawerUserCopy: {
    flex: 1,
    minWidth: 0,
  },
  drawerUserAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  drawerUserAvatarText: {
    color: colors.textInverse,
    fontSize: fontSizeV2.sm,
    fontWeight: "800",
  },
  drawerUserName: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "800",
  },
  drawerUserMeta: {
    marginTop: 2,
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
});
