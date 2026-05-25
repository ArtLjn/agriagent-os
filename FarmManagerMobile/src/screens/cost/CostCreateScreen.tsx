import React, {useState} from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  Alert,
  TouchableOpacity,
  ActivityIndicator,
  Modal,
  Platform,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import dayjs from 'dayjs';
import DateTimePicker, {DateTimePickerEvent} from '@react-native-community/datetimepicker';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import {useCostStore} from '../../stores/costStore';
import {useCategoryStore} from '../../stores/categoryStore';
import {BigButton} from '../../components/BigButton';
import {Loading} from '../../components/Loading';
import {costApi} from '../../api/client';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';

const COST_CATEGORIES = ['种子', '化肥', '农药', '人工', '水电', '地租', '其他'];
const INCOME_CATEGORIES = ['销售', '补贴', '其他'];

const AI_EXAMPLES = [
  '买了50斤化肥花了120块',
  '今天卖西瓜收入3000元',
  '大棚租金5000',
];

type CostCreateNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  'CostCreate'
>;

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

  // 日期选择器状态
  const [showDatePicker, setShowDatePicker] = useState(false);

  // 分类弹窗状态
  const [showCategoryModal, setShowCategoryModal] = useState(false);

  // 获取可用分类
  const availableCategories = React.useMemo(() => {
    // 先使用用户自定义分类
    const userCategories = categories
      .filter(c => c.category_type === recordType)
      .map(c => c.name);

    // 如果没有用户分类，使用系统默认分类
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

  const handleDateChange = (event: DateTimePickerEvent, date?: Date) => {
    setShowDatePicker(Platform.OS === 'ios');
    if (date) {
      setRecordDate(date);
    }
  };

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
      {/* AI Helper Card */}
      <View style={styles.aiCard}>
        <View style={styles.aiHeader}>
          <Icon name="robot-outline" size={20} color={colors.primary} />
          <Text style={styles.aiTitle}>AI 帮记</Text>
        </View>
        <Text style={styles.aiSubtitle}>
          用一句话描述，AI 自动识别类型和金额
        </Text>
        <View style={styles.aiInputRow}>
          <TextInput
            style={styles.aiInput}
            placeholder="例如：买了50斤化肥花了120块"
            placeholderTextColor={colors.textTertiary}
            value={aiInput}
            onChangeText={setAiInput}
            multiline={false}
            returnKeyType="send"
            onSubmitEditing={handleAiParse}
          />
          <TouchableOpacity
            style={styles.aiButton}
            onPress={handleAiParse}
            disabled={aiLoading}>
            {aiLoading ? (
              <ActivityIndicator size="small" color={colors.textInverse} />
            ) : (
              <Icon name="lightning-bolt" size={20} color={colors.textInverse} />
            )}
          </TouchableOpacity>
        </View>
        <View style={styles.aiExamplesRow}>
          {AI_EXAMPLES.map((example, index) => (
            <TouchableOpacity
              key={index}
              style={styles.aiExampleChip}
              onPress={() => setAiInput(example)}>
              <Text style={styles.aiExampleText}>{example}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

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
      {showDatePicker && (
        <DateTimePicker
          value={recordDate}
          mode="date"
          display="compact"
          onChange={handleDateChange}
          maximumDate={new Date()}
        />
      )}

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

      {/* 分类选择弹窗 */}
      <Modal
        visible={showCategoryModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowCategoryModal(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>选择分类</Text>
              <TouchableOpacity onPress={() => setShowCategoryModal(false)}>
                <Icon name="close" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            <View style={styles.modalGrid}>
              {availableCategories.map(cat => (
                <View key={cat} style={styles.modalGridItem}>
                  <BigButton
                    title={cat}
                    onPress={() => handleCategorySelect(cat)}
                    variant={category === cat ? 'primary' : 'secondary'}
                  />
                </View>
              ))}
            </View>

            <TouchableOpacity
              style={styles.manageCategoriesBtn}
              onPress={() => {
                setShowCategoryModal(false);
                // @ts-ignore
                navigation.navigate('CostCategory');
              }}>
              <Icon name="cog" size={18} color={colors.primary} />
              <Text style={styles.manageCategoriesText}>管理分类</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  aiCard: {
    backgroundColor: colors.primaryMuted,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  aiHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  aiTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.primary,
    marginLeft: spacing.sm,
  },
  aiSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  aiInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  aiInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    backgroundColor: colors.surface,
    marginRight: spacing.sm,
  },
  aiButton: {
    width: 44,
    height: 44,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  aiExamplesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  aiExampleChip: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginRight: spacing.sm,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  aiExampleText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
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
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.card,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    padding: spacing.lg,
    maxHeight: '80%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  modalTitle: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
  },
  modalGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -spacing.sm,
  },
  modalGridItem: {
    width: '33.33%',
    paddingHorizontal: spacing.sm,
    marginBottom: spacing.md,
  },
  manageCategoriesBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.md,
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: borderRadius.lg,
    gap: spacing.sm,
  },
  manageCategoriesText: {
    fontSize: fontSize.md,
    color: colors.primary,
    fontWeight: '600',
  },
});
