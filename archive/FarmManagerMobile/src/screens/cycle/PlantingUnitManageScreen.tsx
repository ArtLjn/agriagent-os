import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Animated,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useRoute, type RouteProp } from "@react-navigation/native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { plantingApi } from "../../api/client";
import type { PlantingUnit } from "../../api/types";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { BigButton } from "../../components/BigButton";
import { colors } from "../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../theme/spacing";
import { showAlert } from "../../utils/alert";

type RouteParams = RouteProp<RootStackParamList, "PlantingUnits">;
type Mode = "single" | "batch";

function buildUnitName(prefix: string, index: number, suffix: string): string {
  return `${prefix.trim()}${index}${suffix.trim() || "号棚"}`;
}

export const PlantingUnitManageScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const { cycleId } = route.params;
  const [units, setUnits] = useState<PlantingUnit[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const [note, setNote] = useState("");
  const [mode, setMode] = useState<Mode>("single");
  const [batchPrefix, setBatchPrefix] = useState("");
  const [batchStart, setBatchStart] = useState("");
  const [batchEnd, setBatchEnd] = useState("");
  const [batchSuffix, setBatchSuffix] = useState("号棚");
  const [batchArea, setBatchArea] = useState("");
  const [batchNote, setBatchNote] = useState("");
  const [saving, setSaving] = useState(false);
  const modeMotion = useRef(new Animated.Value(1)).current;

  const loadUnits = useCallback(async () => {
    const res = await plantingApi.getUnits(cycleId);
    setUnits(res.data);
  }, [cycleId]);

  useEffect(() => {
    loadUnits().catch((err) => showAlert("加载失败", err.message));
  }, [loadUnits]);

  useEffect(() => {
    modeMotion.setValue(0);
    Animated.timing(modeMotion, {
      toValue: 1,
      duration: 180,
      useNativeDriver: true,
    }).start();
  }, [mode, modeMotion]);

  const batchRange = useMemo(() => {
    const start = Number(batchStart);
    const end = Number(batchEnd);
    if (
      !Number.isInteger(start) ||
      !Number.isInteger(end) ||
      start <= 0 ||
      end < start
    ) {
      return [];
    }
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }, [batchEnd, batchStart]);

  const batchPreview = useMemo(
    () =>
      batchRange
        .slice(0, 4)
        .map((item) => buildUnitName(batchPrefix, item, batchSuffix)),
    [batchPrefix, batchRange, batchSuffix]
  );

  const resetForm = () => {
    setEditingId(null);
    setName("");
    setArea("");
    setNote("");
  };

  const switchMode = (nextMode: Mode) => {
    if (mode === nextMode) {
      return;
    }
    resetForm();
    setMode(nextMode);
  };

  const startEdit = (unit: PlantingUnit) => {
    setMode("single");
    setEditingId(unit.id);
    setName(unit.name);
    setArea(unit.area_mu || "");
    setNote(unit.note || "");
  };

  const submit = async () => {
    if (!name.trim()) {
      showAlert("提示", "请填写棚或地块名称");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: name.trim(),
        area_mu: area.trim() || undefined,
        note: note.trim() || undefined,
      };
      if (editingId) {
        await plantingApi.updateUnit(editingId, payload);
      } else {
        await plantingApi.createUnit({ cycle_id: cycleId, ...payload });
      }
      resetForm();
      await loadUnits();
    } catch (err: any) {
      showAlert("保存失败", err.message || "请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  const submitBatch = async () => {
    if (batchRange.length === 0) {
      showAlert("提示", "请填写正确的起止编号");
      return;
    }
    if (batchRange.length > 100) {
      showAlert("提示", "一次最多创建 100 个棚或地块");
      return;
    }
    setSaving(true);
    try {
      await Promise.all(
        batchRange.map((current) =>
          plantingApi.createUnit({
            cycle_id: cycleId,
            name: buildUnitName(batchPrefix, current, batchSuffix),
            area_mu: batchArea.trim() || undefined,
            note: batchNote.trim() || undefined,
          })
        )
      );
      setBatchStart("");
      setBatchEnd("");
      await loadUnits();
    } catch (err: any) {
      showAlert("批量创建失败", err.message || "请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  const animatedFormStyle = {
    opacity: modeMotion,
    transform: [
      {
        translateY: modeMotion.interpolate({
          inputRange: [0, 1],
          outputRange: [10, 0],
        }),
      },
    ],
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.formCard}>
        <View style={styles.formHeader}>
          <View>
            <Text style={styles.formEyebrow}>
              {editingId ? "正在修改" : "棚 / 地块"}
            </Text>
            <Text style={styles.formTitle}>
              {editingId ? "编辑种植单元" : "创建种植单元"}
            </Text>
          </View>
          <View style={styles.formIcon}>
            <Icon name="greenhouse" size={22} color={colors.primary} />
          </View>
        </View>

        {!editingId ? (
          <View style={styles.modeGrid}>
            <TouchableOpacity
              style={[
                styles.modeCard,
                mode === "single" && styles.modeCardActive,
              ]}
              activeOpacity={0.78}
              onPress={() => switchMode("single")}
            >
              <Icon
                name="home-plus-outline"
                size={20}
                color={mode === "single" ? colors.primary : colors.textTertiary}
              />
              <View style={styles.modeCopy}>
                <Text
                  style={[
                    styles.modeTitle,
                    mode === "single" && styles.modeTitleActive,
                  ]}
                >
                  单个创建
                </Text>
                <Text style={styles.modeHint}>临时补一个棚或地块</Text>
              </View>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.modeCard,
                mode === "batch" && styles.modeCardActive,
              ]}
              activeOpacity={0.78}
              onPress={() => switchMode("batch")}
            >
              <Icon
                name="format-list-numbered"
                size={20}
                color={mode === "batch" ? colors.primary : colors.textTertiary}
              />
              <View style={styles.modeCopy}>
                <Text
                  style={[
                    styles.modeTitle,
                    mode === "batch" && styles.modeTitleActive,
                  ]}
                >
                  批量生成
                </Text>
                <Text style={styles.modeHint}>按编号一次建多个</Text>
              </View>
            </TouchableOpacity>
          </View>
        ) : null}

        {mode === "batch" && !editingId ? (
          <Animated.View style={[styles.formBody, animatedFormStyle]}>
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>命名规则</Text>
              <View style={styles.nameBuilder}>
                <TextInput
                  style={[styles.builderInput, styles.builderAffix]}
                  value={batchPrefix}
                  onChangeText={setBatchPrefix}
                  placeholder="东大棚"
                  placeholderTextColor={colors.textTertiary}
                />
                <View style={styles.builderNumber}>
                  <Text style={styles.builderNumberText}>编号</Text>
                </View>
                <TextInput
                  style={[styles.builderInput, styles.builderAffix]}
                  value={batchSuffix}
                  onChangeText={setBatchSuffix}
                  placeholder="号棚"
                  placeholderTextColor={colors.textTertiary}
                />
              </View>
            </View>

            <View style={styles.twoCol}>
              <View style={styles.fieldGroupHalf}>
                <Text style={styles.fieldLabel}>起始编号</Text>
                <TextInput
                  style={styles.input}
                  value={batchStart}
                  onChangeText={setBatchStart}
                  placeholder="1"
                  placeholderTextColor={colors.textTertiary}
                  keyboardType="number-pad"
                />
              </View>
              <View style={styles.fieldGroupHalf}>
                <Text style={styles.fieldLabel}>结束编号</Text>
                <TextInput
                  style={styles.input}
                  value={batchEnd}
                  onChangeText={setBatchEnd}
                  placeholder="20"
                  placeholderTextColor={colors.textTertiary}
                  keyboardType="number-pad"
                />
              </View>
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>统一信息</Text>
              <TextInput
                style={styles.input}
                value={batchArea}
                onChangeText={setBatchArea}
                placeholder="每个面积（亩，可选）"
                placeholderTextColor={colors.textTertiary}
                keyboardType="decimal-pad"
              />
              <TextInput
                style={[styles.input, styles.compactTextArea]}
                value={batchNote}
                onChangeText={setBatchNote}
                placeholder="统一备注"
                placeholderTextColor={colors.textTertiary}
                multiline
              />
            </View>

            <View style={styles.previewBox}>
              <View>
                <Text style={styles.previewLabel}>将创建</Text>
                <Text style={styles.previewCount}>
                  {batchRange.length || 0} 个单元
                </Text>
              </View>
              <View style={styles.previewNames}>
                {batchPreview.length > 0 ? (
                  batchPreview.map((item) => (
                    <Text key={item} style={styles.previewName}>
                      {item}
                    </Text>
                  ))
                ) : (
                  <Text style={styles.previewPlaceholder}>
                    填入编号后显示预览
                  </Text>
                )}
                {batchRange.length > batchPreview.length ? (
                  <Text style={styles.previewMore}>
                    还有 {batchRange.length - batchPreview.length} 个
                  </Text>
                ) : null}
              </View>
            </View>

            <BigButton
              title={saving ? "创建中..." : "批量创建"}
              icon="plus-box-multiple-outline"
              onPress={submitBatch}
              disabled={saving}
              style={styles.saveBtn}
            />
          </Animated.View>
        ) : (
          <Animated.View style={[styles.formBody, animatedFormStyle]}>
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>名称</Text>
              <TextInput
                style={styles.input}
                value={name}
                onChangeText={setName}
                placeholder="例如：东大棚 1-3 号"
                placeholderTextColor={colors.textTertiary}
              />
            </View>
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>面积和备注</Text>
              <TextInput
                style={styles.input}
                value={area}
                onChangeText={setArea}
                placeholder="面积（亩，可选）"
                placeholderTextColor={colors.textTertiary}
                keyboardType="decimal-pad"
              />
              <TextInput
                style={[styles.input, styles.compactTextArea]}
                value={note}
                onChangeText={setNote}
                placeholder="备注"
                placeholderTextColor={colors.textTertiary}
                multiline
              />
            </View>
            <View style={styles.formActions}>
              {editingId ? (
                <TouchableOpacity style={styles.cancelBtn} onPress={resetForm}>
                  <Text style={styles.cancelText}>取消编辑</Text>
                </TouchableOpacity>
              ) : null}
              <BigButton
                title={saving ? "保存中..." : "保存"}
                icon={editingId ? "content-save-outline" : "plus"}
                onPress={submit}
                disabled={saving}
                style={styles.saveBtn}
              />
            </View>
          </Animated.View>
        )}
      </View>

      <View style={styles.listHeader}>
        <Text style={styles.sectionTitle}>已有单元</Text>
        <Text style={styles.sectionMeta}>{units.length} 个</Text>
      </View>
      <View style={styles.unitListCard}>
        {units.length > 0 ? (
          <ScrollView
            style={styles.unitListScroll}
            nestedScrollEnabled
            showsVerticalScrollIndicator
          >
            {units.map((unit) => (
              <TouchableOpacity
                key={unit.id}
                style={styles.unitRow}
                activeOpacity={0.75}
                onPress={() => startEdit(unit)}
              >
                <View style={styles.unitIcon}>
                  <Icon name="greenhouse" size={18} color={colors.primary} />
                </View>
                <View style={styles.unitInfo}>
                  <Text style={styles.unitName}>{unit.name}</Text>
                  <Text style={styles.unitMeta} numberOfLines={1}>
                    {unit.area_mu
                      ? `${Number(unit.area_mu)
                          .toFixed(2)
                          .replace(/\.00$/, "")} 亩`
                      : "未填面积"}
                    {unit.note ? ` · ${unit.note}` : ""}
                  </Text>
                </View>
                <Icon
                  name="pencil-outline"
                  size={18}
                  color={colors.textTertiary}
                />
              </TouchableOpacity>
            ))}
          </ScrollView>
        ) : (
          <View style={styles.emptyBox}>
            <Icon name="greenhouse" size={24} color={colors.textTertiary} />
            <Text style={styles.emptyText}>
              还没有棚、地块或区域，可先按整个批次记录作业。
            </Text>
          </View>
        )}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacingV2.lg, paddingBottom: spacingV2.xxxxl },
  formCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.xl,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  formHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingV2.md,
    marginBottom: spacingV2.lg,
  },
  formEyebrow: {
    fontSize: fontSizeV2.xs,
    color: colors.primary,
    fontWeight: "900",
    marginBottom: 4,
  },
  formTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "900",
    color: colors.text,
  },
  formIcon: {
    width: 44,
    height: 44,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primaryMuted,
  },
  modeGrid: {
    flexDirection: "row",
    gap: spacingV2.sm,
    marginBottom: spacingV2.lg,
  },
  modeCard: {
    flex: 1,
    minHeight: 76,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    backgroundColor: colors.background,
    padding: spacingV2.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  modeCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primaryMuted,
  },
  modeCopy: { flex: 1, minWidth: 0 },
  modeTitle: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "900",
  },
  modeTitleActive: { color: colors.primary },
  modeHint: {
    marginTop: 3,
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  formBody: {
    gap: spacingV2.md,
  },
  fieldGroup: {
    gap: spacingV2.sm,
  },
  fieldGroupHalf: {
    flex: 1,
    gap: spacingV2.sm,
  },
  fieldLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "900",
  },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadiusV2.lg,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.background,
  },
  compactTextArea: {
    minHeight: 76,
    textAlignVertical: "top",
  },
  nameBuilder: {
    minHeight: 50,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.background,
    overflow: "hidden",
  },
  builderInput: {
    minHeight: 50,
    paddingHorizontal: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
  },
  builderAffix: {
    flex: 1,
    minWidth: 0,
  },
  builderNumber: {
    minHeight: 50,
    paddingHorizontal: spacingV2.md,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceMuted,
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: colors.borderLight,
  },
  builderNumberText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "900",
  },
  twoCol: { flexDirection: "row", gap: spacingV2.md },
  previewBox: {
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    backgroundColor: colors.background,
    padding: spacingV2.md,
    flexDirection: "row",
    gap: spacingV2.md,
  },
  previewLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  previewCount: {
    marginTop: 3,
    fontSize: fontSizeV2.lg,
    color: colors.text,
    fontWeight: "900",
  },
  previewNames: {
    flex: 1,
    minWidth: 0,
    gap: 4,
  },
  previewName: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "700",
  },
  previewPlaceholder: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    fontWeight: "700",
  },
  previewMore: {
    fontSize: fontSizeV2.xs,
    color: colors.primary,
    fontWeight: "900",
  },
  formActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
  },
  cancelBtn: {
    minHeight: 48,
    paddingHorizontal: spacingV2.md,
    alignItems: "center",
    justifyContent: "center",
  },
  cancelText: {
    color: colors.textSecondary,
    fontWeight: "800",
    fontSize: fontSizeV2.sm,
  },
  saveBtn: { flex: 1 },
  listHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.md,
  },
  sectionTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "900",
    color: colors.text,
  },
  sectionMeta: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  unitListCard: {
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    overflow: "hidden",
  },
  unitListScroll: {
    maxHeight: 420,
  },
  unitRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    gap: spacingV2.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  unitIcon: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  unitInfo: { flex: 1, minWidth: 0 },
  unitName: {
    fontSize: fontSizeV2.md,
    fontWeight: "900",
    color: colors.text,
  },
  unitMeta: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  emptyBox: {
    minHeight: 132,
    alignItems: "center",
    justifyContent: "center",
    padding: spacingV2.xl,
    gap: spacingV2.sm,
  },
  emptyText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    lineHeight: 22,
    textAlign: "center",
  },
});
