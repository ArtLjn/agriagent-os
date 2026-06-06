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
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import { appGradients } from "../../theme/gradients";
import { touchOpacity } from "../../theme/animations";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

type PromptTone = "sky" | "leaf" | "amber" | "slate";

const QUICK_PROMPTS: Array<{
  text: string;
  prompt: string;
  icon: string;
  tone: PromptTone;
}> = [
  {
    text: "天气判断",
    prompt: "今日天气对作物有什么影响？",
    icon: "weather-partly-cloudy",
    tone: "sky",
  },
  {
    text: "种植建议",
    prompt: "给我一些种植建议",
    icon: "sprout",
    tone: "leaf",
  },
  {
    text: "病虫害",
    prompt: "常见的病虫害怎么防治？",
    icon: "bug-outline",
    tone: "amber",
  },
  {
    text: "本周报告",
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
        <View style={styles.heroBlock}>
          <LinearGradient
            colors={["rgba(59, 178, 115, 0.14)", "rgba(74, 123, 247, 0.08)"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.heroIcon}
          >
            <Icon name="sprout" size={24} color={colors.success} />
          </LinearGradient>
          <View style={styles.heroCopy}>
            <Text style={styles.welcomeEyebrow}>
              {greeting}，{nickname}
            </Text>
            <Text style={styles.welcomeTitle}>今天要处理什么？</Text>
            <Text style={styles.welcomeSubtitle}>
              可以直接问，也可以点一个场景开始。
            </Text>
          </View>
        </View>

        <View style={styles.promptSection}>
          <Text style={styles.promptTitle}>常用场景</Text>
          <View style={styles.promptCards}>
            {QUICK_PROMPTS.map((prompt, index) => (
              <TouchableOpacity
                key={index}
                style={styles.promptPill}
                onPress={() => handleSend(prompt.prompt)}
                activeOpacity={touchOpacity.card}
              >
                <View
                  style={[
                    styles.promptIconBox,
                    { backgroundColor: PROMPT_TONES[prompt.tone].bg },
                  ]}
                >
                  <Icon
                    name={prompt.icon as any}
                    size={16}
                    color={PROMPT_TONES[prompt.tone].icon}
                  />
                </View>
                <Text style={styles.promptPillText}>{prompt.text}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
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
    const drawerWidth = Math.min(Dimensions.get("window").width * 0.78, 320);
    const drawerTranslateX = drawerProgress.interpolate({
      inputRange: [0, 1],
      outputRange: [-drawerWidth, 0],
    });
    const scrimOpacity = drawerProgress.interpolate({
      inputRange: [0, 1],
      outputRange: [0, 1],
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
                transform: [{ translateX: drawerTranslateX }],
              },
            ]}
          >
            <View style={styles.drawerTop}>
              <TouchableOpacity
                style={styles.drawerIconBtn}
                onPress={() => setDrawerVisible(false)}
                activeOpacity={touchOpacity.icon}
              >
                <Icon name="menu" size={24} color={colors.text} />
              </TouchableOpacity>
              <View style={styles.drawerActionRow}>
                <TouchableOpacity
                  style={styles.drawerIconBtn}
                  activeOpacity={touchOpacity.icon}
                >
                  <Icon name="magnify" size={22} color={colors.text} />
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.drawerIconBtn}
                  onPress={handleStartNewSession}
                  activeOpacity={touchOpacity.icon}
                >
                  <Icon
                    name="message-plus-outline"
                    size={22}
                    color={colors.text}
                  />
                </TouchableOpacity>
              </View>
            </View>

            <TouchableOpacity
              style={styles.newSessionCard}
              onPress={handleStartNewSession}
              activeOpacity={touchOpacity.card}
            >
              <View style={styles.newSessionIcon}>
                <Icon
                  name="layers-triple-outline"
                  size={22}
                  color={colors.success}
                />
              </View>
              <Text style={styles.newSessionText}>新对话</Text>
              <Icon
                name="chevron-right"
                size={22}
                color={colors.textTertiary}
              />
            </TouchableOpacity>

            <View style={styles.drawerHeading}>
              <Text style={styles.drawerTitle}>会话列表</Text>
              <View style={styles.drawerFilter}>
                <Text style={styles.drawerFilterText}>农事对话</Text>
                <Icon
                  name="filter-variant"
                  size={18}
                  color={colors.textSecondary}
                />
              </View>
            </View>

            <ScrollView
              style={styles.sessionList}
              showsVerticalScrollIndicator={false}
            >
              {orderedSessions.map((session) => {
                const period = formatSessionPeriod(session.updatedAt);
                const shouldShowPeriod = !renderedPeriods.has(period);
                renderedPeriods.add(period);
                const isActive = session.id === sessionId;
                return (
                  <View key={session.id}>
                    {shouldShowPeriod && (
                      <Text style={styles.sessionPeriod}>{period}</Text>
                    )}
                    <TouchableOpacity
                      style={[
                        styles.sessionItem,
                        isActive && styles.sessionItemActive,
                      ]}
                      onPress={() => handleSwitchSession(session.id)}
                      activeOpacity={touchOpacity.card}
                    >
                      <Text
                        style={[
                          styles.sessionTitle,
                          isActive && styles.sessionTitleActive,
                        ]}
                        numberOfLines={1}
                      >
                        {session.title}
                      </Text>
                      <View style={styles.sessionMetaRow}>
                        <Text style={styles.sessionTag}>
                          {session.category}
                        </Text>
                        <Text style={styles.sessionTime}>
                          {formatSessionTime(session.updatedAt)}
                        </Text>
                      </View>
                    </TouchableOpacity>
                  </View>
                );
              })}
            </ScrollView>

            <View style={styles.drawerFooter}>
              <View style={styles.drawerUser}>
                <LinearGradient
                  colors={[colors.success, colors.primary]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                  style={styles.drawerUserAvatar}
                >
                  <Text style={styles.drawerUserAvatarText}>农</Text>
                </LinearGradient>
                <Text style={styles.drawerUserName} numberOfLines={1}>
                  {user?.nickname || "系统管理员"}
                </Text>
              </View>
              <TouchableOpacity
                style={styles.drawerIconBtn}
                activeOpacity={touchOpacity.icon}
              >
                <Icon name="cog-outline" size={23} color={colors.text} />
              </TouchableOpacity>
            </View>
          </Animated.View>
        </View>
      </Modal>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <LinearGradient
        {...appGradients.chatBg}
        style={StyleSheet.absoluteFill}
      />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.headerMenuBtn}
          onPress={() => setDrawerVisible(true)}
          activeOpacity={touchOpacity.icon}
        >
          <Icon name="menu" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={styles.headerLeft}>
          <View style={styles.headerAvatar}>
            <Icon name="sprout" size={18} color={colors.success} />
          </View>
          <View>
            <Text style={styles.headerTitle}>芽芽</Text>
            <View style={styles.statusRow}>
              <View style={styles.statusDot} />
              <Text style={styles.headerSubtitle}>在线</Text>
            </View>
          </View>
        </View>
        <TouchableOpacity
          style={styles.headerNewBtn}
          onPress={handleStartNewSession}
          activeOpacity={touchOpacity.icon}
        >
          <Icon name="plus" size={22} color={colors.text} />
        </TouchableOpacity>
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
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.sm,
    backgroundColor: "transparent",
  },
  headerMenuBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255, 255, 255, 0.76)",
    borderWidth: 1,
    borderColor: "rgba(226, 232, 240, 0.7)",
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
    marginLeft: spacingV2.md,
    minWidth: 0,
  },
  headerAvatar: {
    width: 40,
    height: 40,
    borderRadius: 15,
    backgroundColor: colors.successMuted,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.md,
  },
  headerTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
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
  },
  headerNewBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255, 255, 255, 0.76)",
    borderWidth: 1,
    borderColor: "rgba(226, 232, 240, 0.7)",
  },

  // ─── Segment ───
  segmentRow: {
    flexDirection: "row",
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.sm,
    backgroundColor: "rgba(235, 240, 247, 0.72)",
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
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 2,
    elevation: 1,
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
    justifyContent: "center",
  },
  welcomeContainer: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.lg,
    paddingBottom: spacingV2.lg,
  },
  heroBlock: {
    minHeight: 148,
    justifyContent: "flex-end",
    marginBottom: spacingV2.lg,
  },
  heroIcon: {
    width: 56,
    height: 56,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacingV2.lg,
  },
  heroCopy: {
    maxWidth: 360,
  },
  welcomeEyebrow: {
    fontSize: fontSizeV2.sm,
    color: colors.success,
    fontWeight: "700",
    marginBottom: spacingV2.sm,
  },
  welcomeTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "700",
    color: colors.text,
    lineHeight: 30,
    marginBottom: spacingV2.sm,
  },
  welcomeSubtitle: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    lineHeight: 24,
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
  promptPill: {
    width: "47%",
    minHeight: 72,
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    padding: spacingV2.md,
    gap: spacingV2.md,
    borderWidth: 1,
    borderColor: "rgba(226, 232, 240, 0.9)",
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
    fontWeight: "600",
    lineHeight: 20,
    flex: 1,
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
    backgroundColor: colors.successMuted,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.sm,
  },
  agentAvatarSmall: {
    width: 24,
    height: 24,
    borderRadius: 8,
    backgroundColor: colors.primaryMuted,
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
    backgroundColor: colors.primary,
    borderRadius: borderRadiusV2.xxl,
    borderBottomRightRadius: 8,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
  },
  agentBubble: {
    alignSelf: "flex-start",
  },
  agentBubbleInner: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    borderBottomLeftRadius: 8,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    borderWidth: 1,
    borderColor: colors.chatAiBorder,
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
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.lg,
    borderBottomLeftRadius: 4,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: 4,
  },
  typingDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: colors.textTertiary,
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
    backgroundColor: "rgba(255, 255, 255, 0.9)",
    borderTopWidth: 1,
    borderTopColor: "rgba(226, 232, 240, 0.76)",
  },
  inputWrapper: {
    flexDirection: "row",
    alignItems: "flex-end",
    backgroundColor: "#F1F5F9",
    borderRadius: borderRadiusV2.xxxl,
    paddingLeft: spacingV2.lg,
    paddingRight: spacingV2.sm,
    paddingVertical: spacingV2.sm,
    borderWidth: 1,
    borderColor: "rgba(226, 232, 240, 0.9)",
  },
  input: {
    flex: 1,
    maxHeight: 100,
    fontSize: fontSizeV2.md,
    color: colors.text,
    paddingVertical: spacingV2.sm,
    paddingRight: spacingV2.sm,
    minHeight: 38,
  },
  sendBtn: {
    width: 38,
    height: 38,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.text,
  },
  sendBtnDisabled: {
    backgroundColor: "rgba(226, 232, 240, 0.88)",
  },

  // ─── Context box ───
  contextBox: {
    marginTop: spacingV2.sm,
    padding: spacingV2.md,
    backgroundColor: colors.successMuted,
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
    backgroundColor: colors.primary,
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
    backgroundColor: colors.disabledBg,
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
    backgroundColor: "#F8FBFF",
    paddingTop: Platform.OS === "ios" ? 52 : spacingV2.xl,
    paddingHorizontal: spacingV2.lg,
    paddingBottom: spacingV2.lg,
    borderRightWidth: 1,
    borderRightColor: "rgba(226, 232, 240, 0.96)",
    shadowColor: "#0F172A",
    shadowOffset: { width: 16, height: 0 },
    shadowOpacity: 0.14,
    shadowRadius: 28,
    elevation: 12,
  },
  drawerTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.lg,
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
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "rgba(226, 232, 240, 0.94)",
  },
  newSessionCard: {
    minHeight: 62,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "rgba(226, 232, 240, 0.94)",
    marginBottom: spacingV2.xl,
  },
  newSessionIcon: {
    width: 40,
    height: 40,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.successMuted,
  },
  newSessionText: {
    flex: 1,
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "700",
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
    fontWeight: "800",
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
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    marginBottom: spacingV2.xs,
    borderWidth: 1,
    borderColor: "transparent",
  },
  sessionItemActive: {
    backgroundColor: "#EEF8F3",
    borderColor: "rgba(59, 178, 115, 0.24)",
  },
  sessionTitle: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "700",
    lineHeight: 20,
  },
  sessionTitleActive: {
    color: "#147A4C",
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
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "rgba(59, 178, 115, 0.18)",
    color: colors.success,
    fontSize: 11,
    fontWeight: "700",
  },
  sessionTime: {
    flex: 1,
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
  },
  drawerFooter: {
    minHeight: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingV2.md,
    borderTopWidth: 1,
    borderTopColor: "rgba(226, 232, 240, 0.96)",
    paddingTop: spacingV2.md,
  },
  drawerUser: {
    flex: 1,
    minWidth: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
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
    flex: 1,
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "800",
  },
});
