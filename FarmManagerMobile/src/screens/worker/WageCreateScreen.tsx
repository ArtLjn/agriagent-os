import React, { useEffect, useState } from "react";
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
import dayjs from "dayjs";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { plantingApi, cycleApi } from "../../api/client";
import type { CropCycleListItem, OperationType, Worker } from "../../api/types";
import { BigButton } from "../../components/BigButton";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors } from "../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../theme/spacing";
import { showAlert } from "../../utils/alert";

type RouteParams = RouteProp<RootStackParamList, "WageCreate">;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const HOUR_CHIPS = ["4", "8", "10"];
const PRICE_CHIPS = ["100", "120", "150", "180", "200", "220"];
const STANDARD_DAY_HOURS = 8;

function toMoneyNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getRequestId(
  cycleId: number,
  operationType: string,
  workerName: string,
  date: string
) {
  return `${cycleId}-${operationType}-${workerName}-${date}`;
}

export const WageCreateScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const params = route.params || {};
  const today = dayjs().format("YYYY-MM-DD");
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [operationTypes, setOperationTypes] = useState<OperationType[]>([]);
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(
    params.cycleId ?? null
  );
  const [cropName, setCropName] = useState(params.cropName || "");
  const [operationType, setOperationType] = useState(
    params.operationType || ""
  );
  const [selectedWorkerIds, setSelectedWorkerIds] = useState<number[]>(
    params.workerId ? [params.workerId] : []
  );
  const [showWorkerList, setShowWorkerList] = useState(false);
  const [workHours, setWorkHours] = useState("8");
  const [dailyWage, setDailyWage] = useState(params.unitPrice || "200");
  const [paidAmount, setPaidAmount] = useState("");
  const [workDate, setWorkDate] = useState(today);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    Promise.all([
      cycleApi.getCycles(),
      plantingApi.getWorkers(),
      plantingApi.getOperationTypes(params.cropName),
    ])
      .then(([cyclesRes, workersRes, typesRes]) => {
        const cycleItems = (cyclesRes.data as any)?.items ?? cyclesRes.data;
        setCycles(cycleItems);
        setWorkers(workersRes.data);
        setOperationTypes(typesRes.data);
        const defaultWorker =
          workersRes.data.find((worker) => worker.id === params.workerId) ||
          workersRes.data.find((worker) => worker.name === params.workerName);
        if (selectedWorkerIds.length === 0 && defaultWorker) {
          setSelectedWorkerIds([defaultWorker.id]);
          if (defaultWorker.default_unit_price) {
            setDailyWage(defaultWorker.default_unit_price);
          }
        }

        const defaultCycle =
          cycleItems.find(
            (item: CropCycleListItem) => item.id === params.cycleId
          ) ||
          cycleItems.find(
            (item: CropCycleListItem) => item.status === "active"
          ) ||
          cycleItems[0];
        if (!selectedCycleId && defaultCycle) {
          setSelectedCycleId(defaultCycle.id);
          setCropName(defaultCycle.name);
        }
        if (!params.operationType) {
          const defaultOperation = typesRes.data[0]?.name || "";
          setOperationType(defaultOperation);
        }
      })
      .catch((err) => showAlert("加载失败", err.message || "请稍后重试"))
      .finally(() => setLoading(false));
  }, [
    params.cropName,
    params.cycleId,
    params.operationType,
    params.workerId,
    params.workerName,
    selectedCycleId,
    selectedWorkerIds.length,
  ]);

  useEffect(() => {
    const selected = cycles.find((cycle) => cycle.id === selectedCycleId);
    if (!selected) {
      return;
    }
    setCropName(selected.name);
    plantingApi
      .getOperationTypes(selected.name)
      .then((res) => {
        setOperationTypes(res.data);
        if (!operationType && res.data[0]) {
          setOperationType(res.data[0].name);
        }
      })
      .catch(() => {});
  }, [cycles, operationType, selectedCycleId]);

  const selectedWorkers = workers.filter((worker) =>
    selectedWorkerIds.includes(worker.id)
  );
  const selectedCycle = cycles.find((cycle) => cycle.id === selectedCycleId);
  const hoursValue = toMoneyNumber(workHours);
  const dailyWageValue = toMoneyNumber(dailyWage);
  const workDayQuantity = hoursValue / STANDARD_DAY_HOURS;
  const perWorkerPayable = workDayQuantity * dailyWageValue;
  const payable = perWorkerPayable * selectedWorkers.length;
  const perWorkerPaid = toMoneyNumber(paidAmount || "0");
  const unpaid = Math.max(0, payable - perWorkerPaid * selectedWorkers.length);

  const toggleWorker = (worker: Worker) => {
    setSelectedWorkerIds((ids) => {
      if (ids.includes(worker.id)) {
        return ids.filter((id) => id !== worker.id);
      }
      return [...ids, worker.id];
    });
    if (selectedWorkerIds.length === 0 && worker.default_unit_price) {
      setDailyWage(worker.default_unit_price);
    }
  };

  const clearSelectedWorkers = () => {
    setSelectedWorkerIds([]);
  };

  const submit = async () => {
    if (!selectedCycleId) {
      showAlert("提示", "请选择茬口");
      return;
    }
    if (!operationType.trim()) {
      showAlert("提示", "请选择作业");
      return;
    }
    if (selectedWorkers.length === 0) {
      showAlert("提示", "请选择工人");
      return;
    }
    if (hoursValue <= 0 || dailyWageValue <= 0) {
      showAlert("提示", "请填写有效工时和日工资");
      return;
    }

    setSubmitting(true);
    try {
      await Promise.all(
        selectedWorkers.map((worker) =>
          plantingApi.createWage({
            cycle_id: selectedCycleId,
            crop_name: cropName || selectedCycle?.name,
            operation_type: operationType.trim(),
            worker_id: worker.id,
            worker_name: worker.name,
            quantity: workDayQuantity.toFixed(2).replace(/\.00$/, ""),
            unit_price: dailyWage,
            paid_amount: paidAmount || "0",
            work_date: workDate,
            pay_type: "daily",
            note:
              note.trim() ||
              `工时 ${workHours} 小时，按 ${STANDARD_DAY_HOURS} 小时/天折算`,
            client_request_id: getRequestId(
              selectedCycleId,
              operationType.trim(),
              worker.name,
              workDate
            ),
          })
        )
      );
      navigation.goBack();
    } catch (err: any) {
      showAlert("保存失败", err.message || "请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.summaryBar}>
        <View>
          <Text style={styles.summaryLabel}>合计应付</Text>
          <Text style={styles.summaryValue}>{payable.toFixed(0)} 元</Text>
          <Text style={styles.summarySub}>
            {selectedWorkers.length || 0} 人 · 每人{" "}
            {perWorkerPayable.toFixed(0)} 元
          </Text>
        </View>
        <View style={styles.summaryPill}>
          <Text style={styles.summaryPillText}>
            未结 {unpaid.toFixed(0)} 元
          </Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>这笔工资属于哪里</Text>
        <Text style={styles.sectionHint}>
          茬口必须选择，作物和作业用于后续核对账单来源。
        </Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
        >
          {cycles.map((cycle) => {
            const active = selectedCycleId === cycle.id;
            return (
              <TouchableOpacity
                key={cycle.id}
                style={[styles.selectChip, active && styles.selectChipActive]}
                onPress={() => setSelectedCycleId(cycle.id)}
              >
                <Text
                  style={[
                    styles.selectChipText,
                    active && styles.selectChipTextActive,
                  ]}
                >
                  {cycle.name}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
        <View style={styles.inputRow}>
          <Icon name="sprout-outline" size={18} color={colors.success} />
          <TextInput
            style={styles.inlineInput}
            value={cropName}
            onChangeText={setCropName}
            placeholder="作物或安排，例如 8424 西瓜"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
        >
          {operationTypes.map((item) => {
            const active = operationType === item.name;
            return (
              <TouchableOpacity
                key={item.name}
                style={[styles.selectChip, active && styles.selectChipActive]}
                onPress={() => setOperationType(item.name)}
              >
                <Text
                  style={[
                    styles.selectChipText,
                    active && styles.selectChipTextActive,
                  ]}
                >
                  {item.name}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
        <View style={styles.inputRow}>
          <Icon
            name="clipboard-edit-outline"
            size={18}
            color={colors.primary}
          />
          <TextInput
            style={styles.inlineInput}
            value={operationType}
            onChangeText={setOperationType}
            placeholder="也可以手动输入作业类型"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
        <View style={styles.inputRow}>
          <Icon name="calendar" size={18} color={colors.primary} />
          <TextInput
            style={styles.inlineInput}
            value={workDate}
            onChangeText={setWorkDate}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>选择工人</Text>
        <Text style={styles.sectionHint}>
          可同时选择多人，保存后每人一条工资。
        </Text>
        <TouchableOpacity
          style={styles.dropdownField}
          onPress={() => setShowWorkerList((visible) => !visible)}
          activeOpacity={0.75}
        >
          <Icon name="account-hard-hat" size={18} color={colors.primary} />
          <Text
            style={[
              styles.dropdownText,
              selectedWorkers.length === 0 && styles.dropdownPlaceholder,
            ]}
            numberOfLines={1}
          >
            {selectedWorkers.length > 0
              ? selectedWorkers.map((worker) => worker.name).join("、")
              : "请选择工人"}
          </Text>
          {selectedWorkers.length > 0 ? (
            <TouchableOpacity
              onPress={clearSelectedWorkers}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Icon name="close-circle" size={18} color={colors.textTertiary} />
            </TouchableOpacity>
          ) : (
            <Icon
              name={showWorkerList ? "chevron-up" : "chevron-down"}
              size={20}
              color={colors.textTertiary}
            />
          )}
        </TouchableOpacity>
        {showWorkerList ? (
          <View style={styles.dropdownList}>
            {workers.length > 0 ? (
              <ScrollView
                style={styles.dropdownListScroll}
                nestedScrollEnabled
                showsVerticalScrollIndicator
              >
                {workers.map((worker) => {
                  const active = selectedWorkerIds.includes(worker.id);
                  return (
                    <TouchableOpacity
                      key={worker.id}
                      style={[
                        styles.workerOption,
                        active && styles.workerOptionActive,
                      ]}
                      onPress={() => toggleWorker(worker)}
                      activeOpacity={0.75}
                    >
                      <View style={styles.workerAvatar}>
                        <Text style={styles.workerAvatarText}>
                          {worker.name.slice(0, 1)}
                        </Text>
                      </View>
                      <View style={styles.workerOptionInfo}>
                        <Text style={styles.workerOptionName} numberOfLines={1}>
                          {worker.name}
                        </Text>
                        <Text style={styles.workerOptionMeta} numberOfLines={1}>
                          {worker.phone ? `${worker.phone} · ` : ""}
                          {worker.default_unit_price
                            ? `${worker.default_unit_price} 元/天`
                            : "未设置默认日工资"}
                        </Text>
                      </View>
                      {active ? (
                        <Icon
                          name="check-circle"
                          size={20}
                          color={colors.success}
                        />
                      ) : null}
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>
            ) : (
              <View style={styles.emptyWorkerBox}>
                <Text style={styles.emptyWorkerText}>暂无工人档案</Text>
                <TouchableOpacity
                  onPress={() => navigation.navigate("WorkerCreate")}
                >
                  <Text style={styles.emptyWorkerLink}>去新增工人</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        ) : null}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>工资金额</Text>
        <Text style={styles.fieldLabel}>工时</Text>
        <View style={styles.quickGrid}>
          {HOUR_CHIPS.map((item) => (
            <TouchableOpacity
              key={`hours-${item}`}
              style={[
                styles.quickChip,
                workHours === item && styles.quickChipActive,
              ]}
              onPress={() => setWorkHours(item)}
            >
              <Text
                style={[
                  styles.quickChipText,
                  workHours === item && styles.quickChipTextActive,
                ]}
              >
                {item} 小时
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        <View style={styles.inputRow}>
          <Icon
            name="account-multiple-outline"
            size={18}
            color={colors.textSecondary}
          />
          <TextInput
            style={styles.inlineInput}
            value={workHours}
            onChangeText={setWorkHours}
            keyboardType="decimal-pad"
            placeholder="填写工时"
            placeholderTextColor={colors.textTertiary}
          />
        </View>

        <Text style={styles.fieldLabel}>日工资</Text>
        <View style={styles.quickGrid}>
          {PRICE_CHIPS.map((item) => (
            <TouchableOpacity
              key={`price-${item}`}
              style={[
                styles.quickChip,
                dailyWage === item && styles.quickChipActive,
              ]}
              onPress={() => setDailyWage(item)}
            >
              <Text
                style={[
                  styles.quickChipText,
                  dailyWage === item && styles.quickChipTextActive,
                ]}
              >
                {item} 元/天
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        <View style={styles.inputRow}>
          <Icon name="cash" size={18} color={colors.textSecondary} />
          <TextInput
            style={styles.inlineInput}
            value={dailyWage}
            onChangeText={setDailyWage}
            keyboardType="decimal-pad"
            placeholder="元/天"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
        <View style={styles.inputRow}>
          <Icon name="cash-check" size={18} color={colors.success} />
          <TextInput
            style={styles.inlineInput}
            value={paidAmount}
            onChangeText={setPaidAmount}
            keyboardType="decimal-pad"
            placeholder="已付金额，不填按 0"
            placeholderTextColor={colors.textTertiary}
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>备注</Text>
        <TextInput
          style={[styles.inputRow, styles.textArea]}
          value={note}
          onChangeText={setNote}
          placeholder="可写地块、班组或结算说明"
          placeholderTextColor={colors.textTertiary}
          multiline
        />
      </View>

      <View style={styles.autoCard}>
        <Icon name="link-variant" size={20} color={colors.primary} />
        <View style={styles.autoInfo}>
          <Text style={styles.autoTitle}>保存后自动关联</Text>
          <Text style={styles.autoText}>
            生成工资记录，并同步一条来源为“工资记录”的人工成本账单。
          </Text>
        </View>
      </View>

      <BigButton
        title={submitting ? "保存中..." : loading ? "加载中..." : "保存工资"}
        icon="content-save-outline"
        onPress={submit}
        disabled={submitting || loading}
        style={styles.submitButton}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacingV2.lg, paddingBottom: spacingV2.xxxxl },
  summaryBar: {
    minHeight: 88,
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.xl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.lg,
  },
  summaryLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  summaryValue: {
    marginTop: spacingV2.xs,
    fontSize: fontSizeV2.xxxl,
    color: colors.text,
    fontWeight: "900",
  },
  summarySub: {
    marginTop: 2,
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  summaryPill: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.expenseBg,
  },
  summaryPillText: {
    fontSize: fontSizeV2.sm,
    color: colors.expense,
    fontWeight: "800",
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
    fontSize: fontSizeV2.lg,
    fontWeight: "900",
    color: colors.text,
    marginBottom: spacingV2.xs,
  },
  sectionHint: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 19,
    marginBottom: spacingV2.md,
  },
  chipRow: { gap: spacingV2.sm, paddingVertical: spacingV2.sm },
  selectChip: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surfaceMuted,
  },
  selectChipActive: { backgroundColor: colors.primaryMuted },
  selectChipText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.textSecondary,
  },
  selectChipTextActive: { color: colors.primary },
  inputRow: {
    minHeight: 46,
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
  inlineInput: {
    flex: 1,
    minWidth: 0,
    fontSize: fontSizeV2.md,
    color: colors.text,
    paddingVertical: spacingV2.sm,
  },
  dropdownField: {
    minHeight: 50,
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  dropdownText: {
    flex: 1,
    minWidth: 0,
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "800",
  },
  dropdownPlaceholder: {
    color: colors.textTertiary,
    fontWeight: "600",
  },
  dropdownList: {
    marginTop: spacingV2.sm,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    backgroundColor: colors.background,
    overflow: "hidden",
  },
  dropdownListScroll: {
    maxHeight: 292,
  },
  workerOption: {
    minHeight: 58,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  workerOptionActive: {
    backgroundColor: colors.successMuted,
  },
  workerAvatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  workerAvatarText: {
    fontSize: fontSizeV2.sm,
    color: colors.success,
    fontWeight: "900",
  },
  workerOptionInfo: {
    flex: 1,
    minWidth: 0,
  },
  workerOptionName: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "800",
  },
  workerOptionMeta: {
    marginTop: 2,
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  emptyWorkerBox: {
    padding: spacingV2.lg,
    alignItems: "center",
    gap: spacingV2.sm,
  },
  emptyWorkerText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  emptyWorkerLink: {
    fontSize: fontSizeV2.sm,
    color: colors.primary,
    fontWeight: "900",
  },
  fieldLabel: {
    marginTop: spacingV2.md,
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  quickGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.sm,
    marginTop: spacingV2.sm,
  },
  quickChip: {
    minHeight: 38,
    minWidth: 66,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surfaceMuted,
  },
  quickChipActive: { backgroundColor: colors.successMuted },
  quickChipText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  quickChipTextActive: { color: colors.success },
  textArea: {
    minHeight: 96,
    alignItems: "flex-start",
    paddingTop: spacingV2.md,
    textAlignVertical: "top",
    fontSize: fontSizeV2.md,
    color: colors.text,
  },
  autoCard: {
    flexDirection: "row",
    gap: spacingV2.md,
    padding: spacingV2.lg,
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: colors.primaryMuted,
    marginBottom: spacingV2.lg,
  },
  autoInfo: { flex: 1, minWidth: 0 },
  autoTitle: {
    fontSize: fontSizeV2.md,
    color: colors.primary,
    fontWeight: "900",
  },
  autoText: {
    marginTop: 3,
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 19,
  },
  submitButton: { minHeight: 52 },
});
