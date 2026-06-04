import React, { useMemo, useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import {
  useNavigation,
  useRoute,
  type RouteProp,
} from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { plantingApi } from "../../api/client";
import { BigButton } from "../../components/BigButton";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors } from "../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../theme/spacing";
import { showAlert } from "../../utils/alert";

type RouteParams = RouteProp<RootStackParamList, "WorkerCreate">;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const PAY_TYPES = [
  { key: "daily", label: "日工", hint: "按天结算" },
  { key: "hourly", label: "小时工", hint: "按小时结算" },
  { key: "piece", label: "计件", hint: "按数量结算" },
];

export const WorkerCreateScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const route = useRoute<RouteParams>();
  const [name, setName] = useState(route.params?.workerName || "");
  const [phone, setPhone] = useState("");
  const [payType, setPayType] = useState("daily");
  const [unitPrice, setUnitPrice] = useState("200");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const selectedPayType = useMemo(
    () => PAY_TYPES.find((item) => item.key === payType) || PAY_TYPES[0],
    [payType]
  );

  const submit = async () => {
    const workerName = name.trim();
    if (!workerName) {
      showAlert("提示", "请填写工人姓名");
      return;
    }
    if (unitPrice.trim() && Number(unitPrice) < 0) {
      showAlert("提示", "默认工价不能小于 0");
      return;
    }

    setSubmitting(true);
    try {
      await plantingApi.createWorker({
        name: workerName,
        phone: phone.trim() || undefined,
        default_pay_type: payType,
        default_unit_price: unitPrice.trim() || undefined,
        note: note.trim() || undefined,
      });
      navigation.goBack();
    } catch (err: any) {
      showAlert("保存失败", err.message || "请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.headerCard}>
        <View style={styles.headerIcon}>
          <Icon name="account-hard-hat" size={24} color={colors.success} />
        </View>
        <View style={styles.headerInfo}>
          <Text style={styles.headerTitle}>全场工人档案</Text>
          <Text style={styles.headerText}>
            工人不绑定某一个茬口，后续记工资时再选择西瓜、豆角等具体茬口。
          </Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>基本信息</Text>
        <View style={styles.inputRow}>
          <Icon name="account-outline" size={18} color={colors.primary} />
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder="工人姓名，例如 老王"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
        <View style={styles.inputRow}>
          <Icon name="phone-outline" size={18} color={colors.textSecondary} />
          <TextInput
            style={styles.input}
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            placeholder="手机号，可不填"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>默认工资</Text>
        <View style={styles.payTypeRow}>
          {PAY_TYPES.map((item) => {
            const active = item.key === payType;
            return (
              <TouchableOpacity
                key={item.key}
                style={[styles.payTypeCard, active && styles.payTypeCardActive]}
                onPress={() => setPayType(item.key)}
                activeOpacity={0.75}
              >
                <Text
                  style={[
                    styles.payTypeLabel,
                    active && styles.payTypeLabelActive,
                  ]}
                >
                  {item.label}
                </Text>
                <Text
                  style={[
                    styles.payTypeHint,
                    active && styles.payTypeHintActive,
                  ]}
                >
                  {item.hint}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
        <View style={styles.inputRow}>
          <Icon name="cash" size={18} color={colors.success} />
          <TextInput
            style={styles.input}
            value={unitPrice}
            onChangeText={setUnitPrice}
            keyboardType="decimal-pad"
            placeholder={`${selectedPayType.label}默认单价`}
            placeholderTextColor={colors.textTertiary}
          />
          <Text style={styles.unitText}>元</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>备注</Text>
        <TextInput
          style={styles.textArea}
          value={note}
          onChangeText={setNote}
          placeholder="例如常做授粉、采摘，或班组说明"
          placeholderTextColor={colors.textTertiary}
          multiline
        />
      </View>

      <BigButton
        title={submitting ? "保存中..." : "保存工人"}
        icon="content-save-outline"
        onPress={submit}
        disabled={submitting}
        style={styles.submitButton}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacingV2.lg, paddingBottom: spacingV2.xxxxl },
  headerCard: {
    flexDirection: "row",
    gap: spacingV2.md,
    padding: spacingV2.lg,
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    marginBottom: spacingV2.lg,
  },
  headerIcon: {
    width: 48,
    height: 48,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.successMuted,
  },
  headerInfo: { flex: 1, minWidth: 0 },
  headerTitle: {
    fontSize: fontSizeV2.lg,
    color: colors.text,
    fontWeight: "900",
  },
  headerText: {
    marginTop: spacingV2.xs,
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 19,
  },
  section: {
    marginBottom: spacingV2.lg,
    padding: spacingV2.lg,
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  sectionTitle: {
    marginBottom: spacingV2.md,
    fontSize: fontSizeV2.lg,
    color: colors.text,
    fontWeight: "900",
  },
  inputRow: {
    minHeight: 48,
    marginTop: spacingV2.sm,
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  input: {
    flex: 1,
    minWidth: 0,
    paddingVertical: spacingV2.sm,
    fontSize: fontSizeV2.md,
    color: colors.text,
  },
  unitText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  payTypeRow: {
    flexDirection: "row",
    gap: spacingV2.sm,
    marginBottom: spacingV2.sm,
  },
  payTypeCard: {
    flex: 1,
    minHeight: 72,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.surfaceMuted,
    padding: spacingV2.md,
    justifyContent: "center",
  },
  payTypeCardActive: { backgroundColor: colors.headerBg },
  payTypeLabel: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "900",
  },
  payTypeLabelActive: { color: colors.textInverse },
  payTypeHint: {
    marginTop: 3,
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  payTypeHintActive: { color: "rgba(255,255,255,0.68)" },
  textArea: {
    minHeight: 104,
    paddingHorizontal: spacingV2.md,
    paddingTop: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
    fontSize: fontSizeV2.md,
    color: colors.text,
    textAlignVertical: "top",
  },
  submitButton: { minHeight: 52 },
});
