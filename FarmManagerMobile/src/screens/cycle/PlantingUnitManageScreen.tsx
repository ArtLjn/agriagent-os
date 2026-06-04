import React, { useEffect, useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { plantingApi } from "../../api/client";
import type { PlantingUnit } from "../../api/types";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { BigButton } from "../../components/BigButton";
import { colors } from "../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../theme/spacing";
import { showAlert } from "../../utils/alert";

type RouteParams = RouteProp<RootStackParamList, "PlantingUnits">;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const PlantingUnitManageScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const { cycleId } = route.params;
  const [units, setUnits] = useState<PlantingUnit[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const loadUnits = async () => {
    const res = await plantingApi.getUnits(cycleId);
    setUnits(res.data);
  };

  useEffect(() => {
    loadUnits().catch((err) => showAlert("加载失败", err.message));
  }, [cycleId]);

  const resetForm = () => {
    setEditingId(null);
    setName("");
    setArea("");
    setNote("");
  };

  const startEdit = (unit: PlantingUnit) => {
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

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.formCard}>
        <Text style={styles.formTitle}>{editingId ? "编辑种植单元" : "新增种植单元"}</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="例如：东大棚 1-3 号"
          placeholderTextColor={colors.textTertiary}
        />
        <TextInput
          style={styles.input}
          value={area}
          onChangeText={setArea}
          placeholder="面积（亩）"
          placeholderTextColor={colors.textTertiary}
          keyboardType="decimal-pad"
        />
        <TextInput
          style={[styles.input, styles.textArea]}
          value={note}
          onChangeText={setNote}
          placeholder="备注"
          placeholderTextColor={colors.textTertiary}
          multiline
        />
        <View style={styles.formActions}>
          {editingId ? (
            <TouchableOpacity style={styles.cancelBtn} onPress={resetForm}>
              <Text style={styles.cancelText}>取消编辑</Text>
            </TouchableOpacity>
          ) : null}
          <BigButton title={saving ? "保存中..." : "保存"} onPress={submit} style={styles.saveBtn} />
        </View>
      </View>

      <Text style={styles.sectionTitle}>已有单元</Text>
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
            <Text style={styles.unitMeta}>
              {unit.area_mu ? `${Number(unit.area_mu).toFixed(2).replace(/\.00$/, "")} 亩` : "未填面积"}
              {unit.note ? ` · ${unit.note}` : ""}
            </Text>
          </View>
          <Icon name="pencil-outline" size={18} color={colors.textTertiary} />
        </TouchableOpacity>
      ))}
      {units.length === 0 ? (
        <Text style={styles.emptyText}>还没有棚、地块或区域，可先按整个批次记录作业。</Text>
      ) : null}
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
    gap: spacingV2.md,
    marginBottom: spacingV2.xl,
  },
  formTitle: { fontSize: fontSizeV2.lg, fontWeight: "800", color: colors.text },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadiusV2.md,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.md,
    fontSize: fontSizeV2.md,
    color: colors.text,
    backgroundColor: colors.background,
  },
  textArea: { minHeight: 84, textAlignVertical: "top" },
  formActions: { flexDirection: "row", alignItems: "center", gap: spacingV2.md },
  cancelBtn: { paddingHorizontal: spacingV2.md, paddingVertical: spacingV2.md },
  cancelText: { color: colors.textSecondary, fontWeight: "700" },
  saveBtn: { flex: 1 },
  sectionTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    color: colors.text,
    marginBottom: spacingV2.md,
  },
  unitRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.sm,
    gap: spacingV2.md,
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
  unitName: { fontSize: fontSizeV2.md, fontWeight: "800", color: colors.text },
  unitMeta: { fontSize: fontSizeV2.sm, color: colors.textSecondary, marginTop: 2 },
  emptyText: { fontSize: fontSizeV2.md, color: colors.textSecondary, lineHeight: 22 },
});
