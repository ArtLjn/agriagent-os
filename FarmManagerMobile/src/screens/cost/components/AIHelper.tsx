import React from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
} from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { colors } from "../../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../../theme/spacing";

const AI_EXAMPLES = ["化肥120块", "卖瓜3000元", "地租5000"];

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
      <View style={[styles.iconBadge, { backgroundColor: themeMuted }]}>
        <Icon name="auto-fix" size={18} color={themeColor} />
      </View>
      <View style={styles.headerText}>
        <Text style={styles.title}>一句话快速记账</Text>
        <Text style={styles.subtitle}>
          输入"买化肥120块"，自动识别类型、金额和分类
        </Text>
      </View>
    </View>
    <View style={styles.inputRow}>
      <TextInput
        style={styles.input}
        placeholder="例如：浇水工资100"
        placeholderTextColor={colors.textTertiary}
        value={aiInput}
        onChangeText={onInputChange}
        multiline={false}
        returnKeyType="send"
        onSubmitEditing={onParse}
      />
      <TouchableOpacity
        style={[styles.button, { backgroundColor: themeColor }]}
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
    <View style={styles.examplesRail}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.examplesRow}
      >
        {AI_EXAMPLES.map((example, index) => (
          <TouchableOpacity
            key={index}
            style={styles.exampleChip}
            onPress={() => onInputChange(example)}
          >
            <Text style={styles.exampleText} numberOfLines={1}>
              {example}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  </View>
);

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.sm,
    borderWidth: 1,
    borderColor: "#EDF0F5",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.md,
    gap: spacingV2.sm,
  },
  iconBadge: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  headerText: {
    flex: 1,
    minWidth: 0,
  },
  title: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: -0.2,
  },
  subtitle: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginTop: 2,
    fontWeight: "500",
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    marginBottom: spacingV2.sm,
  },
  input: {
    flex: 1,
    borderRadius: borderRadiusV2.lg,
    paddingHorizontal: spacingV2.md,
    paddingVertical: 10,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.surfaceMuted,
    fontWeight: "500",
  },
  button: {
    width: 44,
    height: 44,
    borderRadius: borderRadiusV2.lg,
    justifyContent: "center",
    alignItems: "center",
  },
  examplesRail: {
    height: 36,
    justifyContent: "center",
    overflow: "visible",
  },
  examplesRow: {
    flexDirection: "row",
    gap: spacingV2.xs,
    paddingRight: spacingV2.md,
    alignItems: "center",
  },
  exampleChip: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.md,
    height: 32,
    justifyContent: "center",
    maxWidth: 220,
  },
  exampleText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
});
