import React, { useState, useRef, useCallback, useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
} from "react-native";
import LinearGradient from "react-native-linear-gradient";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import { useAgentStore } from "../../stores/agentStore";
import type { ChatMessage } from "../../api/types";
import { MarkdownText } from "../../components/MarkdownText";
import { ReportListView } from "../../components/ReportListView";
import { ScalePress } from "../../components/animations/ScalePress";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import { appGradients } from "../../theme/gradients";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const RECOMMENDED_QUESTIONS = [
  "帮我规划秋种",
  "今天适合施肥吗",
  "未来一周天气",
];

const QUICK_PROMPTS = [
  { icon: "weather-partly-cloudy", text: "今日天气对作物有什么影响？" },
  { icon: "sprout", text: "给我一些种植建议" },
  { icon: "bug", text: "常见的病虫害怎么防治？" },
  { icon: "file-document", text: "生成本周种植报告" },
];

export const AgentChatScreen: React.FC = () => {
  const navigation = useNavigation();
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
  }, [activeTab]);

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
    return (
      <View
        style={[styles.messageRow, isUser ? styles.userRow : styles.agentRow]}
      >
        {!isUser && (
          <View style={styles.agentAvatar}>
            <View style={styles.aiFace}>
              <View style={styles.aiEye} />
              <View style={styles.aiEye} />
            </View>
          </View>
        )}
        <View
          style={[
            styles.messageBubble,
            isUser ? styles.userBubble : styles.agentBubble,
          ]}
        >
          {isUser ? (
            <LinearGradient
              {...appGradients.userBubble}
              style={styles.userBubbleInner}
            >
              <Text style={styles.userText}>{item.content}</Text>
            </LinearGradient>
          ) : (
            <View style={styles.agentBubbleInner}>
              <MarkdownText text={item.content} baseStyle={styles.agentText} />
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
                <Text style={styles.confirmBtnText}>确认</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => handleSend("取消")}
                activeOpacity={0.7}
                disabled={isLoading}
              >
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
      <Text style={styles.welcomeSubtitle}>
        可以帮你分析天气、提供种植建议、生成报告
      </Text>

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
    if (hasMessages) {
      return null;
    }
    return renderWelcome();
  }, [hasMessages]);

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <LinearGradient
        {...appGradients.chatBg}
        style={StyleSheet.absoluteFill}
      />

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

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
      >
        {activeTab === "chat" ? (
          <>
            <FlatList
              ref={flatListRef}
              data={messages}
              keyExtractor={(_, index) => String(index)}
              renderItem={renderMessage}
              contentContainerStyle={[
                styles.listContent,
                !hasMessages && { flexGrow: 1 },
              ]}
              ListHeaderComponent={ListHeaderComponent}
              onContentSizeChange={() =>
                flatListRef.current?.scrollToEnd({ animated: true })
              }
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
                  style={[
                    styles.sendBtn,
                    (!inputText.trim() || isLoading) && styles.sendBtnDisabled,
                  ]}
                  onPress={handleInputSend}
                  disabled={!inputText.trim() || isLoading}
                  activeOpacity={0.7}
                >
                  <LinearGradient
                    {...appGradients.userBubble}
                    style={[
                      styles.sendBtnGradient,
                      (!inputText.trim() || isLoading) &&
                        styles.sendBtnDisabled,
                    ]}
                  >
                    <Icon
                      name="send"
                      size={18}
                      color={
                        !inputText.trim() || isLoading
                          ? colors.textTertiary
                          : "#FFFFFF"
                      }
                    />
                  </LinearGradient>
                </TouchableOpacity>
              </View>
            </View>
          </>
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
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    backgroundColor: "transparent",
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
  },
  headerAvatar: {
    width: 40,
    height: 40,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.md,
  },
  aiFace: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "#1A1D23",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },
  aiEye: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#FFFFFF",
  },
  aiFaceSmall: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#1A1D23",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },
  aiEyeSmall: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: "#FFFFFF",
  },
  aiFaceLarge: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#1A1D23",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  aiEyeLarge: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#FFFFFF",
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
  segmentRow: {
    flexDirection: "row",
    marginHorizontal: spacingV2.lg,
    marginTop: spacingV2.sm,
    marginBottom: spacingV2.sm,
    backgroundColor: "rgba(255,255,255,0.7)",
    borderRadius: borderRadiusV2.lg,
    padding: 3,
  },
  segBtn: {
    flex: 1,
    paddingVertical: spacingV2.sm,
    alignItems: "center",
    borderRadius: borderRadiusV2.md,
  },
  segBtnActive: {
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
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
    padding: spacingV2.md,
    paddingBottom: spacingV2.sm,
  },
  welcomeContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacingV2.xxl,
    paddingHorizontal: spacingV2.lg,
  },
  welcomeAvatar: {
    width: 80,
    height: 80,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacingV2.lg,
  },
  welcomeTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    color: colors.text,
    marginBottom: spacingV2.xs,
    textAlign: "center",
  },
  welcomeSubtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginBottom: spacingV2.xl,
    textAlign: "center",
  },
  capsulesContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
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
    fontWeight: "500",
  },
  quickPromptsContainer: {
    width: "100%",
    gap: spacingV2.sm,
  },
  quickPrompt: {
    flexDirection: "row",
    alignItems: "center",
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
    fontWeight: "500",
    flex: 1,
  },
  messageRow: {
    flexDirection: "row",
    marginBottom: spacingV2.md,
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
    borderRadius: borderRadiusV2.md,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.sm,
  },
  messageBubble: {
    maxWidth: "92%",
  },
  userBubble: {
    alignSelf: "flex-end",
  },
  userBubbleInner: {
    borderRadius: borderRadiusV2.lg,
    borderBottomRightRadius: 4,
    padding: spacingV2.md,
  },
  agentBubble: {
    alignSelf: "flex-start",
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
    alignItems: "flex-start",
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
    flexDirection: "row",
    alignItems: "flex-end",
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
    overflow: "hidden",
  },
  sendBtnGradient: {
    width: 36,
    height: 36,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
    justifyContent: "center",
  },
  sendBtnDisabled: {
    backgroundColor: colors.disabledBg,
  },
  confirmBar: {
    flexDirection: "row",
    justifyContent: "flex-end",
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
    fontWeight: "600",
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
    fontWeight: "600",
  },
});
