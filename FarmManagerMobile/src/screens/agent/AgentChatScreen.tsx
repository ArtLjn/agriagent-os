import React, { useState, useRef, useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";
import LinearGradient from "react-native-linear-gradient";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import { useAgentStore } from "../../stores/agentStore";
import { useAuthStore } from "../../stores/authStore";
import type { ChatMessage } from "../../api/types";
import { MarkdownText } from "../../components/MarkdownText";
import { ReportListView } from "../../components/ReportListView";
import { ScalePress } from "../../components/animations/ScalePress";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import { appGradients } from "../../theme/gradients";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const QUICK_PROMPTS = [
  { text: "今日天气对作物有什么影响？", icon: "weather-partly-cloudy" },
  { text: "给我一些种植建议", icon: "sprout" },
  { text: "常见的病虫害怎么防治？", icon: "bug-outline" },
  { text: "生成本周种植报告", icon: "file-document-outline" },
];

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

  const renderWelcome = () => {
    const nickname = user?.nickname || "农友";
    const greeting = getGreeting();

    return (
      <View style={styles.welcomeContainer}>
        <View style={styles.welcomeHeader}>
          <View style={styles.welcomeAvatar}>
            <Icon name="sprout" size={20} color={colors.success} />
          </View>
          <View style={styles.welcomeTextBlock}>
            <Text style={styles.welcomeTitle}>
              {greeting}，{nickname}
            </Text>
            <Text style={styles.welcomeSubtitle}>
              可以帮你分析天气、提供种植建议、生成报告
            </Text>
          </View>
        </View>

        <View style={styles.promptSection}>
          <View style={styles.promptCards}>
            {QUICK_PROMPTS.map((prompt, index) => (
              <ScalePress key={index} onPress={() => handleSend(prompt.text)}>
                <View style={styles.promptPill}>
                  <Icon name={prompt.icon as any} size={13} color="#5B6370" />
                  <Text style={styles.promptPillText}>{prompt.text}</Text>
                </View>
              </ScalePress>
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
            <Text style={styles.headerTitle}>农事助手</Text>
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
        <>
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

            {isLoading && hasMessages && (
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
                <Icon
                  name="send"
                  size={18}
                  color={
                    !inputText.trim() || isLoading ? "#B0B8C1" : "#FFFFFF"
                  }
                />
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
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: colors.primaryMuted,
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
    backgroundColor: "rgba(241,243,245,0.8)",
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
    padding: spacingV2.md,
    paddingBottom: spacingV2.sm,
  },

  // ─── Welcome — left-aligned ───
  welcomeScrollContent: {
    flexGrow: 1,
    justifyContent: "center",
  },
  welcomeContainer: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.xl,
    paddingBottom: spacingV2.xxxl,
  },
  welcomeHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.xxl,
  },
  welcomeAvatar: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.md,
  },
  welcomeTextBlock: {
    flex: 1,
  },
  welcomeTitle: {
    fontSize: 22,
    fontWeight: "700",
    color: colors.text,
    marginBottom: 4,
  },
  welcomeSubtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },

  // ─── Prompt pills ───
  promptSection: {
    marginTop: spacingV2.sm,
  },
  promptCards: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.sm,
  },
  promptPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 10,
    gap: 6,
  },
  promptPillText: {
    fontSize: fontSizeV2.xs,
    color: colors.text,
    fontWeight: "500",
  },

  // ─── Messages ───
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
    width: 28,
    height: 28,
    borderRadius: 10,
    backgroundColor: colors.primaryMuted,
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
    maxWidth: "88%",
  },
  userBubble: {
    alignSelf: "flex-end",
  },
  userBubbleInner: {
    backgroundColor: colors.primary,
    borderRadius: borderRadiusV2.lg,
    borderBottomRightRadius: 4,
    padding: spacingV2.md,
  },
  agentBubble: {
    alignSelf: "flex-start",
  },
  agentBubbleInner: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.lg,
    borderBottomLeftRadius: 4,
    padding: spacingV2.md,
  },
  userText: {
    fontSize: fontSizeV2.md,
    color: "#FFFFFF",
    lineHeight: 22,
  },
  agentText: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    lineHeight: 22,
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
    paddingHorizontal: spacingV2.md,
    paddingTop: spacingV2.sm,
    paddingBottom: spacingV2.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F3F4F6",
    borderRadius: borderRadiusV2.full,
    paddingLeft: spacingV2.lg,
    paddingRight: spacingV2.md,
    paddingVertical: 2,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  input: {
    flex: 1,
    maxHeight: 100,
    fontSize: fontSizeV2.md,
    color: colors.text,
    paddingVertical: spacingV2.md,
    paddingRight: spacingV2.sm,
  },
  sendBtn: {
    width: 36,
    height: 36,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
  },
  sendBtnDisabled: {
    backgroundColor: colors.disabledBg,
  },

  // ─── Confirm bar ───
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
    backgroundColor: colors.primary,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.md,
  },
  confirmBtnText: {
    color: "#FFFFFF",
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
