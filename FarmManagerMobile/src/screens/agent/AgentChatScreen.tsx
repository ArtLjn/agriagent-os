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
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const QUICK_PROMPTS = [
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

const getGreeting = () => {
  const hour = new Date().getHours();
  if (hour < 6) return "夜深了，早点休息";
  if (hour < 12) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 19) return "下午好";
  return "晚上好";
};

export const AgentChatScreen: React.FC = () => {
  const navigation = useNavigation();
  const { user } = useAuthStore();
  const {
    messages,
    sendMessage,
    loading: isLoading,
    reports,
    fetchReports,
  } = useAgentStore();
  const [inputText, setInputText] = useState("");
  const [activeTab, setActiveTab] = useState<"chat" | "report">("chat");
  const flatListRef = useRef<FlatList>(null);

  const hasMessages = messages.length > 0;

  useEffect(() => {
    if (activeTab === "report") {
      fetchReports();
    }
  }, [activeTab, fetchReports]);

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

  const renderMessage = ({ item }: { item: ChatMessage }) => {
    const isUser = item.role === "user";
    const hasPendingAction = !isUser && item.pending_action;
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
                style={styles.confirmBtn}
                onPress={() => handleSend("确认")}
                activeOpacity={0.7}
                disabled={isLoading}
              >
                <Icon name="check" size={16} color="#FFFFFF" />
                <Text style={styles.confirmBtnText}>确认执行</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => handleSend("取消")}
                activeOpacity={0.7}
                disabled={isLoading}
              >
                <Icon name="close" size={16} color={colors.textSecondary} />
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
                activeOpacity={0.78}
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

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <LinearGradient
        {...appGradients.chatBg}
        style={StyleSheet.absoluteFill}
      />

      {/* Header */}
      <View style={styles.header}>
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
      </View>

      {/* SegmentedControl */}
      <View style={styles.segmentRow}>
        <TouchableOpacity
          style={[styles.segBtn, activeTab === "chat" && styles.segBtnActive]}
          onPress={() => setActiveTab("chat")}
          activeOpacity={0.7}
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
          activeOpacity={0.7}
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
                activeOpacity={0.7}
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
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.sm,
    backgroundColor: "transparent",
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
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
  cancelBtnText: {
    color: colors.textSecondary,
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
  },
});
