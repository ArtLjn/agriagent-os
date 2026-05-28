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
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../../theme/spacing";

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
  themeColor?: string;
  themeMuted?: string;
}

export const AIHelper: React.FC<AIHelperProps> = ({
  aiInput,
  aiLoading,
  onInputChange,
  onParse,
  themeColor = colors.primary,
  themeMuted = colors.primaryMuted,
}) => (
  <View style={styles.card}>
    <View style={styles.header}>
      <Icon name="text-recognition" size={20} color={colors.primary} />
      <Text style={styles.title}>智能记账</Text>
    </View>
    <Text style={styles.subtitle}>说一句话，自动识别类型和金额</Text>
    <View style={styles.inputRow}>
      <TextInput
        style={styles.input}
        placeholder="例如：买了50斤化肥花了120块"
        placeholderTextColor={colors.textTertiary}
        value={aiInput}
        onChangeText={onInputChange}
        multiline={false}
        returnKeyType="send"
        onSubmitEditing={onParse}
      />
      <TouchableOpacity
        style={styles.button}
        onPress={onParse}
        disabled={aiLoading}
      >
        {aiLoading ? (
          <ActivityIndicator size="small" color={colors.textInverse} />
        ) : (
          <Icon name="arrow-right" size={20} color={colors.textInverse} />
        )}
      </TouchableOpacity>
    </View>
    <View style={styles.examplesRow}>
      {AI_EXAMPLES.map((example, index) => (
        <TouchableOpacity
          key={index}
          style={styles.exampleChip}
          onPress={() => onInputChange(example)}
        >
          <Text style={styles.exampleText}>{example}</Text>
        </TouchableOpacity>
      ))}
    </View>
  </View>
);

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.md,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.xs,
    gap: spacingV2.sm,
  },
  title: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.text,
  },
  subtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginBottom: spacingV2.md,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.md,
    gap: spacingV2.sm,
  },
  input: {
    flex: 1,
    borderRadius: borderRadiusV2.lg,
    padding: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.surfaceMuted,
  },
  button: {
    width: 44,
    height: 44,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
  },
  examplesRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.xs,
  },
  exampleChip: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 6,
  },
  exampleText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
});
