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

  return (
    <ScrollView style={styles.container} keyboardShouldPersistTaps="handled">
      <AIHelper
        aiInput={aiInput}
        aiLoading={aiLoading}
        onInputChange={setAiInput}
        onParse={handleAiParse}
      />

      <Text style={styles.sectionTitle}>类型</Text>
      <View style={styles.typeRow}>
        <View style={styles.typeItem}>
          <BigButton
            title="支出"
            onPress={() => {
              setRecordType('cost');
              setCategory('');
            }}
            variant={recordType === 'cost' ? 'danger' : 'secondary'}
          />
        </View>
        <View style={styles.typeItem}>
          <BigButton
            title="收入"
            onPress={() => {
              setRecordType('income');
              setCategory('');
            }}
            variant={recordType === 'income' ? 'primary' : 'secondary'}
          />
        </View>
      </View>

      <Text style={styles.sectionTitle}>分类</Text>
      <TouchableOpacity
        style={styles.categorySelector}
        onPress={() => setShowCategoryModal(true)}>
        <Text style={category ? styles.categoryText : styles.categoryPlaceholder}>
          {category || '请选择分类'}
        </Text>
        <Icon name="chevron-right" size={24} color={colors.textSecondary} />
      </TouchableOpacity>

      <Text style={styles.sectionTitle}>金额</Text>
      <View style={styles.amountRow}>
        <Text style={styles.amountSymbol}>¥</Text>
        <TextInput
          style={styles.amountInput}
          placeholder="0.00"
          placeholderTextColor={colors.textSecondary}
          keyboardType="decimal-pad"
          value={amount}
          onChangeText={setAmount}
        />
      </View>

      <Text style={styles.sectionTitle}>日期</Text>
      <TouchableOpacity
        style={styles.dateSelector}
        onPress={() => setShowDatePicker(true)}>
        <Icon name="calendar" size={20} color={colors.primary} />
        <Text style={styles.dateText}>{dayjs(recordDate).format('YYYY年MM月DD日')}</Text>
      </TouchableOpacity>
      <DatePickerModal
        visible={showDatePicker}
        date={recordDate}
        onConfirm={(d) => {
          setRecordDate(d);
          setShowDatePicker(false);
        }}
        onCancel={() => setShowDatePicker(false)}
      />

      <Text style={styles.sectionTitle}>备注</Text>
      <TextInput
        style={styles.noteInput}
        placeholder="添加备注（可选）"
        placeholderTextColor={colors.textSecondary}
        multiline
        numberOfLines={3}
        textAlignVertical="top"
        value={note}
        onChangeText={setNote}
      />

      <View style={styles.submitArea}>
        <BigButton title="保存" onPress={handleSubmit} />
      </View>

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
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginTop: spacing.lg,
    marginBottom: spacing.md,
  },
  typeRow: {
    flexDirection: 'row',
    marginHorizontal: -spacing.sm,
  },
  typeItem: {
    flex: 1,
    paddingHorizontal: spacing.sm,
  },
  categorySelector: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.lg,
    backgroundColor: colors.surface,
  },
  categoryText: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: '600',
  },
  categoryPlaceholder: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  amountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surface,
  },
  amountSymbol: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
    marginRight: spacing.sm,
  },
  amountInput: {
    flex: 1,
    padding: spacing.md,
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
  },
  dateSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.lg,
    backgroundColor: colors.surface,
    gap: spacing.md,
  },
  dateText: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: '600',
  },
  noteInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    backgroundColor: colors.surface,
    minHeight: 80,
  },
  submitArea: {
    marginTop: spacing.xl,
    marginBottom: spacing.xxl,
  },
});
