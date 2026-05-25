import React, {useState, useRef, useCallback} from 'react';
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
import {SafeAreaView} from 'react-native-safe-area-context';
import {useAgentStore} from '../../stores/agentStore';
import type {ChatMessage} from '../../api/types';
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

export const AgentChatScreen: React.FC = () => {
  const {messages, sendMessage, loading: isLoading} = useAgentStore();
  const [inputText, setInputText] = useState('');
  const flatListRef = useRef<FlatList>(null);

  const hasMessages = messages.length > 0;

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

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}>
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
});
