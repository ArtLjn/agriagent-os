import React, {useState, useMemo} from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  Alert,
  TouchableOpacity,
  Platform,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import dayjs from 'dayjs';
// import DateTimePicker, {DateTimePickerEvent} from '@react-native-community/datetimepicker';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import {useCostStore} from '../../stores/costStore';
import {useCategoryStore} from '../../stores/categoryStore';
import {BigButton} from '../../components/BigButton';
import {Loading} from '../../components/Loading';
import {costApi} from '../../api/client';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';
import {AIHelper} from './components/AIHelper';
import {CategoryModal} from './components/CategoryModal';
import {DatePickerModal} from './components/DatePickerModal';

const COST_CATEGORIES = ['种子', '化肥', '农药', '人工', '水电', '地租', '其他'];
const INCOME_CATEGORIES = ['销售', '补贴', '其他'];

type CostCreateNavigationProp = NativeStackNavigationProp<RootStackParamList, 'CostCreate'>;

export const CostCreateScreen: React.FC = () => {
  const navigation = useNavigation<CostCreateNavigationProp>();
  const {createRecord, loading, error, clearError} = useCostStore();
  const {categories} = useCategoryStore();

  const [recordType, setRecordType] = useState<'cost' | 'income'>('cost');
  const [category, setCategory] = useState('');
  const [amount, setAmount] = useState('');
  const [recordDate, setRecordDate] = useState(new Date());
  const [note, setNote] = useState('');
  const [aiInput, setAiInput] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);

  // 获取可用分类
  const availableCategories = useMemo(() => {
    const userCategories = categories
      .filter(c => c.category_type === recordType)
      .map(c => c.name);

    if (userCategories.length === 0) {
      return recordType === 'cost' ? COST_CATEGORIES : INCOME_CATEGORIES;
    }

    return userCategories;
  }, [categories, recordType]);

  const handleAiParse = async () => {
    if (!aiInput.trim()) return;
    setAiLoading(true);
    try {
      const res = await costApi.parseRecord(aiInput.trim());
      const data = res.data;
      setRecordType(data.record_type as 'cost' | 'income');
      setCategory(data.category);
      setAmount(String(data.amount));
      setRecordDate(dayjs(data.record_date).toDate());
      if (data.note) setNote(data.note);
      setAiInput('');
    } catch (err: any) {
      Alert.alert('解析失败', err.message || '请稍后重试');
    } finally {
      setAiLoading(false);
    }
  };

  // const handleDateChange = (event: DateTimePickerEvent, date?: Date) => {
  //   setShowDatePicker(Platform.OS === 'ios');
  //   if (date) {
  //     setRecordDate(date);
  //   }
  // };

  const handleCategorySelect = (cat: string) => {
    setCategory(cat);
    setShowCategoryModal(false);
  };

  const handleSubmit = async () => {
    if (!category) {
      Alert.alert('提示', '请选择分类');
      return;
    }
    if (!amount || isNaN(Number(amount))) {
      Alert.alert('提示', '请输入有效金额');
      return;
    }

    await createRecord({
      record_type: recordType,
      category,
      amount,
      record_date: dayjs(recordDate).format('YYYY-MM-DD'),
      note: note.trim() || undefined,
    });

    if (error) {
      Alert.alert('创建失败', error);
      clearError();
      return;
    }

    navigation.goBack();
  };

  if (loading) {
    return <Loading message="保存中..." />;
  }

  const typeColor = recordType === 'cost' ? colors.danger : colors.success;

  return (
    <ScrollView style={styles.container} keyboardShouldPersistTaps="handled">
      <AIHelper
        aiInput={aiInput}
        aiLoading={aiLoading}
        onInputChange={setAiInput}
        onParse={handleAiParse}
      />

      {/* 类型选择 */}
      <View style={styles.formCard}>
        <Text style={styles.sectionTitle}>类型</Text>
        <View style={styles.typeRow}>
          <TouchableOpacity
            style={[styles.typeBtn, recordType === 'cost' && {backgroundColor: colors.dangerLight, borderColor: colors.danger}]}
            onPress={() => { setRecordType('cost'); setCategory(''); }}
            activeOpacity={0.7}>
            <Icon name="arrow-down-circle" size={22} color={recordType === 'cost' ? colors.danger : colors.textTertiary} />
            <Text style={[styles.typeBtnText, recordType === 'cost' && {color: colors.danger, fontWeight: '700'}]}>支出</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.typeBtn, recordType === 'income' && {backgroundColor: colors.successLight, borderColor: colors.success}]}
            onPress={() => { setRecordType('income'); setCategory(''); }}
            activeOpacity={0.7}>
            <Icon name="arrow-up-circle" size={22} color={recordType === 'income' ? colors.success : colors.textTertiary} />
            <Text style={[styles.typeBtnText, recordType === 'income' && {color: colors.success, fontWeight: '700'}]}>收入</Text>
          </TouchableOpacity>
        </View>

        {/* 分类 */}
        <Text style={[styles.sectionTitle, {marginTop: spacing.lg}]}>分类</Text>
        <TouchableOpacity
          style={styles.fieldRow}
          onPress={() => setShowCategoryModal(true)}>
          <View style={styles.fieldLeft}>
            <Icon name="tag-outline" size={20} color={typeColor} />
            <Text style={category ? styles.fieldText : styles.fieldPlaceholder}>
              {category || '请选择分类'}
            </Text>
          </View>
          <Icon name="chevron-right" size={20} color={colors.textTertiary} />
        </TouchableOpacity>

        {/* 金额 */}
        <Text style={[styles.sectionTitle, {marginTop: spacing.lg}]}>金额</Text>
        <View style={styles.amountRow}>
          <Text style={[styles.amountSymbol, {color: typeColor}]}>¥</Text>
          <TextInput
            style={styles.amountInput}
            placeholder="0.00"
            placeholderTextColor={colors.textTertiary}
            keyboardType="decimal-pad"
            value={amount}
            onChangeText={setAmount}
          />
        </View>

        {/* 日期 */}
        <Text style={[styles.sectionTitle, {marginTop: spacing.lg}]}>日期</Text>
        <TouchableOpacity
          style={styles.fieldRow}
          onPress={() => setShowDatePicker(true)}>
          <View style={styles.fieldLeft}>
            <Icon name="calendar-outline" size={20} color={typeColor} />
            <Text style={styles.fieldText}>{dayjs(recordDate).format('YYYY年MM月DD日')}</Text>
          </View>
          <Icon name="chevron-right" size={20} color={colors.textTertiary} />
        </TouchableOpacity>
      </View>

      {/* 备注 */}
      <View style={styles.formCard}>
        <Text style={styles.sectionTitle}>备注</Text>
        <TextInput
          style={styles.noteInput}
          placeholder="添加备注（可选）"
          placeholderTextColor={colors.textTertiary}
          multiline
          numberOfLines={3}
          textAlignVertical="top"
          value={note}
          onChangeText={setNote}
        />
      </View>

      {/* 保存按钮 */}
      <View style={styles.submitArea}>
        <BigButton title="保存" onPress={handleSubmit} />
      </View>

      <DatePickerModal
        visible={showDatePicker}
        date={recordDate}
        onConfirm={(d) => {
          setRecordDate(d);
          setShowDatePicker(false);
        }}
        onCancel={() => setShowDatePicker(false)}
      />

      <CategoryModal
        visible={showCategoryModal}
        categories={availableCategories}
        selectedCategory={category}
        onSelect={handleCategorySelect}
        onClose={() => setShowCategoryModal(false)}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  formCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: '700',
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  typeRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  typeBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.background,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  typeBtnText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  fieldRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  fieldLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    flex: 1,
  },
  fieldText: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: '600',
  },
  fieldPlaceholder: {
    fontSize: fontSize.md,
    color: colors.textTertiary,
  },
  amountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
  },
  amountSymbol: {
    fontSize: 28,
    fontWeight: '700',
    marginRight: spacing.sm,
  },
  amountInput: {
    flex: 1,
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    padding: 0,
  },
  noteInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    backgroundColor: colors.background,
    minHeight: 80,
  },
  submitArea: {
    marginTop: spacing.lg,
    marginBottom: spacing.xxl,
  },
});
