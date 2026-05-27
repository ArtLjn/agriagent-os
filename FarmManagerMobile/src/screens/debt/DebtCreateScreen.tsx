import React, {useState} from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
  Platform,
} from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import dayjs from 'dayjs';
import {useDebtStore} from '../../stores/debtStore';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';

const COST_CATEGORIES = ['化肥', '农药', '种子', '人工', '水电', '地租', '其他'];

export const DebtCreateScreen: React.FC = () => {
  const navigation = useNavigation<NativeStackNavigationProp<any>>();
  const {createDebt, loading} = useDebtStore();

  const [category, setCategory] = useState('化肥');
  const [amount, setAmount] = useState('');
  const [counterparty, setCounterparty] = useState('');
  const [dueDate, setDueDate] = useState<Date | undefined>(undefined);
  const [note, setNote] = useState('');
  const [showCategoryPicker, setShowCategoryPicker] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);

  const handleSubmit = async () => {
    if (!amount || !counterparty) {
      Alert.alert('请填写完整', '金额和债权人名称必填');
      return;
    }
    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount <= 0) {
      Alert.alert('金额无效', '请输入大于 0 的金额');
      return;
    }

    await createDebt({
      record_type: 'cost',
      category,
      amount: String(numAmount),
      record_date: dayjs().format('YYYY-MM-DD'),
      record_subtype: '赊账',
      counterparty: counterparty.trim(),
      due_date: dueDate ? dayjs(dueDate).format('YYYY-MM-DD') : undefined,
      note: note.trim() || undefined,
    });

    navigation.goBack();
  };

  const handleDateChange = (_event: any, date?: Date) => {
    setShowDatePicker(Platform.OS === 'ios');
    if (date) {
      setDueDate(date);
    }
  };

  return (
    <ScrollView style={styles.container} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>记一笔赊账</Text>

      <View style={styles.field}>
        <Text style={styles.label}>分类</Text>
        <TouchableOpacity
          style={styles.selectButton}
          onPress={() => setShowCategoryPicker(!showCategoryPicker)}>
          <Text style={{color: colors.text}}>{category}</Text>
        </TouchableOpacity>
        {showCategoryPicker && (
          <View style={styles.pickerContainer}>
            {COST_CATEGORIES.map(c => (
              <TouchableOpacity
                key={c}
                style={[
                  styles.pickerItem,
                  category === c && styles.pickerItemActive,
                ]}
                onPress={() => {
                  setCategory(c);
                  setShowCategoryPicker(false);
                }}>
                <Text
                  style={
                    category === c
                      ? styles.pickerItemTextActive
                      : {color: colors.text}
                  }>
                  {c}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>金额（元）</Text>
        <TextInput
          style={styles.input}
          value={amount}
          onChangeText={setAmount}
          keyboardType="decimal-pad"
          placeholder="请输入金额"
          placeholderTextColor={colors.textSecondary}
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>债权人</Text>
        <TextInput
          style={styles.input}
          value={counterparty}
          onChangeText={setCounterparty}
          placeholder="如：老王农资店"
          placeholderTextColor={colors.textSecondary}
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>到期日（可选）</Text>
        <TouchableOpacity
          style={styles.selectButton}
          onPress={() => setShowDatePicker(true)}>
          <Text style={{color: dueDate ? colors.text : colors.textSecondary}}>
            {dueDate ? dayjs(dueDate).format('YYYY-MM-DD') : '点击选择日期'}
          </Text>
        </TouchableOpacity>
        {showDatePicker && (
          <DateTimePicker
            value={dueDate || new Date()}
            mode="date"
            display={Platform.OS === 'ios' ? 'spinner' : 'default'}
            onChange={handleDateChange}
            minimumDate={new Date()}
          />
        )}
        {dueDate ? (
          <TouchableOpacity
            onPress={() => setDueDate(undefined)}
            style={styles.clearDate}>
            <Text style={styles.clearDateText}>清除日期</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>备注（可选）</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          value={note}
          onChangeText={setNote}
          placeholder="添加备注..."
          placeholderTextColor={colors.textSecondary}
          multiline
          numberOfLines={3}
        />
      </View>

      <TouchableOpacity
        style={[styles.submitButton, loading && {opacity: 0.6}]}
        onPress={handleSubmit}
        disabled={loading}>
        <Text style={styles.submitButtonText}>
          {loading ? '保存中...' : '保存'}
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    marginBottom: spacing.lg,
    color: colors.text,
  },
  field: {marginBottom: spacing.md},
  label: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.sm,
    padding: spacing.sm,
    fontSize: fontSize.md,
    backgroundColor: colors.surface,
    color: colors.text,
  },
  textArea: {height: 80, textAlignVertical: 'top'},
  selectButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.sm,
    padding: spacing.sm,
    backgroundColor: colors.surface,
  },
  pickerContainer: {
    marginTop: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.sm,
    backgroundColor: colors.surface,
  },
  pickerItem: {padding: spacing.sm},
  pickerItemActive: {backgroundColor: colors.primaryMuted},
  pickerItemTextActive: {color: colors.primary, fontWeight: '600'},
  submitButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.lg,
  },
  submitButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  clearDate: {
    marginTop: spacing.xs,
    alignSelf: 'flex-start',
  },
  clearDateText: {
    color: colors.primary,
    fontSize: fontSize.sm,
  },
});
