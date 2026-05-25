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
  ScrollView,
} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import {useNavigation} from '@react-navigation/native';
import {useAgentStore} from '../../stores/agentStore';
import type {ChatMessage, ReportListItem} from '../../api/types';
import {MarkdownText} from '../../components/MarkdownText';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

const QUICK_PROMPTS = [
  {icon: 'weather-partly-cloudy', text: '今日天气对作物有什么影响？'},
  {icon: 'sprout', text: '给我一些种植建议'},
  {icon: 'bug', text: '常见的病虫害怎么防治？'},
  {icon: 'file-document', text: '生成本周种植报告'},
];

const ReportListView: React.FC<{
  reports: ReportListItem[];
  onGenerate: () => void;
}> = ({reports, onGenerate}) => (
  <ScrollView style={styles.reportList} contentContainerStyle={styles.reportListContent}>
    <TouchableOpacity style={styles.generateBtn} onPress={onGenerate} activeOpacity={0.7}>
      <Icon name="plus" size={20} color="#FFFFFF" />
      <Text style={styles.generateBtnText}>生成新报告</Text>
    </TouchableOpacity>
    {reports.length === 0 ? (
      <View style={styles.emptyReports}>
        <Icon name="file-document-outline" size={48} color={colors.textTertiary} />
        <Text style={styles.emptyReportsText}>暂无报告</Text>
        <Text style={styles.emptyReportsSub}>点击上方按钮生成第一份报告</Text>
      </View>
    ) : (
      reports.map(r => (
        <TouchableOpacity
          key={r.id}
          style={styles.reportItem}
          activeOpacity={0.7}
          onPress={() => {}}>
          <View style={styles.reportItemHeader}>
            <Text style={styles.reportItemType}>{r.report_type === 'weekly' ? '周报' : '月报'}</Text>
            <Text style={styles.reportItemDate}>
              {new Date(r.created_at).toLocaleDateString('zh-CN')}
            </Text>
          </View>
          <Text style={styles.reportItemPreview} numberOfLines={2}>{r.content}</Text>
        </TouchableOpacity>
      ))
    )}
  </ScrollView>
);

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
    return (
      <View
        style={[
          styles.messageRow,
          isUser ? styles.userRow : styles.agentRow,
        ]}>
        {!isUser && (
          <View style={styles.agentAvatar}>
            <Icon name="robot-excited" size={18} color={colors.primary} />
          </View>
        )}
        <View
          style={[
            styles.messageBubble,
            isUser ? styles.userBubble : styles.agentBubble,
          ]}>
          {isUser ? (
            <Text style={styles.userText}>{item.content}</Text>
          ) : (
            <MarkdownText text={item.content} baseStyle={styles.agentText} />
          )}
        </View>
      </View>
    );
  };

  const renderWelcome = () => (
    <View style={styles.welcomeContainer}>
      <View style={styles.welcomeAvatar}>
        <Icon name="robot-happy" size={48} color={colors.primary} />
      </View>
      <Text style={styles.welcomeTitle}>你好呀，我是 AI 农事助手</Text>
      <Text style={styles.welcomeSubtitle}>
        可以帮你分析天气、提供种植建议、生成报告
      </Text>

      <View style={styles.quickPromptsContainer}>
        {QUICK_PROMPTS.map((prompt, index) => (
          <TouchableOpacity
            key={index}
            style={styles.quickPrompt}
            onPress={() => handleSend(prompt.text)}
            activeOpacity={0.7}
            disabled={isLoading}>
            <Icon name={prompt.icon} size={18} color={colors.primary} />
            <Text style={styles.quickPromptText}>{prompt.text}</Text>
          </TouchableOpacity>
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
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerAvatar}>
          <Icon name="sprout" size={20} color={colors.primary} />
        </View>
        <View>
          <Text style={styles.headerTitle}>AI 农事顾问</Text>
          <View style={styles.statusRow}>
            <View style={styles.statusDot} />
            <Text style={styles.headerSubtitle}>在线</Text>
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
              contentContainerStyle={[
                styles.listContent,
                !hasMessages && {flexGrow: 1},
              ]}
              ListHeaderComponent={ListHeaderComponent}
              onContentSizeChange={() =>
                flatListRef.current?.scrollToEnd({animated: true})
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
                  activeOpacity={0.7}>
                  <Icon
                    name="send"
                    size={18}
                    color={
                      !inputText.trim() || isLoading
                        ? colors.textTertiary
                        : '#FFFFFF'
                    }
                  />
                </TouchableOpacity>
              </View>
            </View>
          </>
        ) : (
          <ReportListView
            reports={reports}
            onGenerate={() => navigation.navigate('AgentReport' as never)}
          />
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  headerAvatar: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  headerTitle: {
    fontSize: fontSize.md,
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
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  segmentRow: {
    flexDirection: 'row',
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
    backgroundColor: colors.background,
    borderRadius: borderRadius.lg,
    padding: 3,
  },
  segBtn: {
    flex: 1,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    borderRadius: borderRadius.md,
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
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  segTextActive: {
    color: colors.text,
  },
  listContent: {
    padding: spacing.md,
    paddingBottom: spacing.sm,
  },
  welcomeContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.lg,
  },
  welcomeAvatar: {
    width: 80,
    height: 80,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  welcomeTitle: {
    fontSize: fontSize.xl,
    fontWeight: '800',
    color: colors.text,
    marginBottom: spacing.xs,
    textAlign: 'center',
  },
  welcomeSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.xl,
    textAlign: 'center',
  },
  quickPromptsContainer: {
    width: '100%',
    gap: spacing.sm,
  },
  quickPrompt: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: spacing.sm,
  },
  quickPromptText: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: '500',
    flex: 1,
  },
  messageRow: {
    flexDirection: 'row',
    marginBottom: spacing.md,
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
    borderRadius: borderRadius.md,
    backgroundColor: colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.sm,
  },
  messageBubble: {
    maxWidth: '92%',
    padding: spacing.md,
  },
  userBubble: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    borderBottomRightRadius: 4,
  },
  agentBubble: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  userText: {
    fontSize: fontSize.md,
    color: colors.textInverse,
    lineHeight: 22,
  },
  agentText: {
    fontSize: fontSize.md,
    color: colors.text,
    lineHeight: 22,
  },
  typingRow: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
    alignItems: 'flex-start',
  },
  typingBubble: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderBottomLeftRadius: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.borderLight,
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
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: colors.background,
    borderRadius: borderRadius.xl,
    paddingLeft: spacing.md,
    paddingRight: 4,
    paddingVertical: 4,
  },
  input: {
    flex: 1,
    maxHeight: 100,
    fontSize: fontSize.md,
    color: colors.text,
    paddingVertical: spacing.sm,
    paddingRight: spacing.sm,
  },
  sendBtn: {
    width: 36,
    height: 36,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: colors.disabledBg,
  },
  reportList: {
    flex: 1,
  },
  reportListContent: {
    padding: spacing.md,
  },
  generateBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  generateBtnText: {
    color: '#FFFFFF',
    fontSize: fontSize.md,
    fontWeight: '700',
  },
  emptyReports: {
    alignItems: 'center',
    paddingVertical: spacing.xxl,
  },
  emptyReportsText: {
    fontSize: fontSize.lg,
    color: colors.textSecondary,
    marginTop: spacing.md,
    fontWeight: '600',
  },
  emptyReportsSub: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
    marginTop: spacing.xs,
  },
  reportItem: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  reportItemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  reportItemType: {
    fontSize: fontSize.sm,
    fontWeight: '700',
    color: colors.primary,
  },
  reportItemDate: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
  },
  reportItemPreview: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
});
