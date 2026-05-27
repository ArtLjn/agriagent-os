import React from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { colors } from "../../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../../theme/spacing";

const AI_EXAMPLES = [
  "买了50斤化肥花了120块",
  "今天卖西瓜收入3000元",
  "大棚租金5000",
];

interface AIHelperProps {
  aiInput: string;
  aiLoading: boolean;
  onInputChange: (text: string) => void;
  onParse: () => void;
}

export const AIHelper: React.FC<AIHelperProps> = ({
  aiInput,
  aiLoading,
  onInputChange,
  onParse,
}) => (
  <View style={styles.aiCard}>
    <View style={styles.aiHeader}>
      <Icon name="robot-outline" size={20} color={colors.primary} />
      <Text style={styles.aiTitle}>AI 帮记</Text>
    </View>
    <Text style={styles.aiSubtitle}>用一句话描述，AI 自动识别类型和金额</Text>
    <View style={styles.aiInputRow}>
      <TextInput
        style={styles.aiInput}
        placeholder="例如：买了50斤化肥花了120块"
        placeholderTextColor={colors.textTertiary}
        value={aiInput}
        onChangeText={onInputChange}
        multiline={false}
        returnKeyType="send"
        onSubmitEditing={onParse}
      />
      <TouchableOpacity
        style={styles.aiButton}
        onPress={onParse}
        disabled={aiLoading}
      >
        {aiLoading ? (
          <ActivityIndicator size="small" color={colors.textInverse} />
        ) : (
          <Icon name="lightning-bolt" size={20} color={colors.textInverse} />
        )}
      </TouchableOpacity>
    </View>
    <View style={styles.aiExamplesRow}>
      {AI_EXAMPLES.map((example, index) => (
        <TouchableOpacity
          key={index}
          style={styles.aiExampleChip}
          onPress={() => onInputChange(example)}
        >
          <Text style={styles.aiExampleText}>{example}</Text>
        </TouchableOpacity>
      ))}
    </View>
  </View>
);

const styles = StyleSheet.create({
  aiCard: {
    backgroundColor: colors.primaryMuted,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  aiHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  aiTitle: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.primary,
    marginLeft: spacing.sm,
  },
  aiSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  aiInputRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  aiInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    backgroundColor: colors.surface,
    marginRight: spacing.sm,
  },
  aiButton: {
    width: 44,
    height: 44,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
  },
  aiExamplesRow: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  aiExampleChip: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginRight: spacing.sm,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  aiExampleText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});
