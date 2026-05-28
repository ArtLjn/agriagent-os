import React, { useState, useMemo } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
  Dimensions,
} from "react-native";
import dayjs from "dayjs";
import { colors } from "../../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

interface DatePickerModalProps {
  visible: boolean;
  date: Date;
  onConfirm: (date: Date) => void;
  onCancel: () => void;
  disableFuture?: boolean;
}

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];
const SCREEN_WIDTH = Dimensions.get("window").width;

export const DatePickerModal: React.FC<DatePickerModalProps> = ({
  visible,
  date,
  onConfirm,
  onCancel,
  disableFuture = true,
}) => {
  const [viewMonth, setViewMonth] = useState(dayjs(date));
  const [selectedDate, setSelectedDate] = useState(dayjs(date));

  const today = dayjs();

  const days = useMemo(() => {
    const startOfMonth = viewMonth.startOf("month");
    const endOfMonth = viewMonth.endOf("month");
    const startDay = startOfMonth.day();
    const daysInMonth = endOfMonth.date();

    const result: {
      day: number;
      isCurrentMonth: boolean;
      date: dayjs.Dayjs;
    }[] = [];

    // 上月填充
    const prevMonth = startOfMonth.subtract(1, "month");
    const prevDays = prevMonth.endOf("month").date();
    for (let i = startDay - 1; i >= 0; i--) {
      result.push({
        day: prevDays - i,
        isCurrentMonth: false,
        date: prevMonth.date(prevDays - i),
      });
    }

    // 当月
    for (let i = 1; i <= daysInMonth; i++) {
      result.push({
        day: i,
        isCurrentMonth: true,
        date: startOfMonth.date(i),
      });
    }

    // 下月填充到完整周
    const remaining = (7 - (result.length % 7)) % 7;
    const nextMonth = startOfMonth.add(1, "month");
    for (let i = 1; i <= remaining; i++) {
      result.push({
        day: i,
        isCurrentMonth: false,
        date: nextMonth.date(i),
      });
    }

    return result;
  }, [viewMonth]);

  const handlePrevMonth = () => setViewMonth(viewMonth.subtract(1, "month"));
  const handleNextMonth = () => {
    const next = viewMonth.add(1, "month");
    if (disableFuture && next.isAfter(today, "month")) {
      return;
    }
    setViewMonth(next);
  };

  const handleDayPress = (d: dayjs.Dayjs) => {
    if (disableFuture && d.isAfter(today, "day")) {
      return;
    }
    setSelectedDate(d);
  };

  const handleConfirm = () => {
    onConfirm(selectedDate.toDate());
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onCancel}
    >
      <View style={styles.overlay}>
        <View style={styles.container}>
          <View style={styles.header}>
            <TouchableOpacity
              onPress={handlePrevMonth}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            >
              <Icon name="chevron-left" size={24} color={colors.primary} />
            </TouchableOpacity>
            <Text style={styles.monthText}>
              {viewMonth.format("YYYY年M月")}
            </Text>
            <TouchableOpacity
              onPress={handleNextMonth}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            >
              <Icon name="chevron-right" size={24} color={colors.primary} />
            </TouchableOpacity>
          </View>

          <View style={styles.weekRow}>
            {WEEKDAYS.map((w) => (
              <Text key={w} style={styles.weekday}>
                {w}
              </Text>
            ))}
          </View>

          <View style={styles.daysGrid}>
            {days.map((item, idx) => {
              const isSelected = selectedDate.isSame(item.date, "day");
              const isToday = today.isSame(item.date, "day");
              const isFuture = disableFuture && item.date.isAfter(today, "day");
              return (
                <TouchableOpacity
                  key={idx}
                  style={[
                    styles.dayCell,
                    isSelected && styles.dayCellSelected,
                    isToday && !isSelected && styles.dayCellToday,
                  ]}
                  onPress={() => handleDayPress(item.date)}
                  disabled={isFuture}
                >
                  <Text
                    style={[
                      styles.dayText,
                      !item.isCurrentMonth && styles.dayTextMuted,
                      isSelected && styles.dayTextSelected,
                      isFuture && styles.dayTextDisabled,
                    ]}
                  >
                    {item.day}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <View style={styles.actions}>
            <TouchableOpacity style={styles.cancelBtn} onPress={onCancel}>
              <Text style={styles.cancelText}>取消</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.confirmBtn} onPress={handleConfirm}>
              <Text style={styles.confirmText}>确定</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const DAY_CELL_SIZE = (SCREEN_WIDTH - spacing.lg * 2 - spacing.md * 2) / 7;

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: colors.overlay,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.lg,
  },
  container: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.xl,
    padding: spacing.lg,
    width: SCREEN_WIDTH - spacing.lg * 2,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  monthText: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  weekRow: {
    flexDirection: "row",
    marginBottom: spacing.sm,
  },
  weekday: {
    flex: 1,
    textAlign: "center",
    fontSize: fontSize.sm,
    color: colors.textTertiary,
    fontWeight: "600",
  },
  daysGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  dayCell: {
    width: DAY_CELL_SIZE,
    height: DAY_CELL_SIZE,
    justifyContent: "center",
    alignItems: "center",
    borderRadius: borderRadius.full,
  },
  dayCellSelected: {
    backgroundColor: colors.primary,
  },
  dayCellToday: {
    borderWidth: 1,
    borderColor: colors.primary,
  },
  dayText: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "500",
  },
  dayTextMuted: {
    color: colors.textTertiary,
  },
  dayTextSelected: {
    color: colors.textInverse,
    fontWeight: "700",
  },
  dayTextDisabled: {
    color: colors.disabled,
  },
  actions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    marginTop: spacing.md,
    gap: spacing.md,
  },
  cancelBtn: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  cancelText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  confirmBtn: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
  },
  confirmText: {
    fontSize: fontSize.md,
    color: colors.textInverse,
    fontWeight: "700",
  },
});
