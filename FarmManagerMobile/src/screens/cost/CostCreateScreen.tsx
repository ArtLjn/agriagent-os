import React, {useState} from 'react';
import {
  View,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  Alert,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import dayjs from 'dayjs';
import {useCostStore} from '../../stores/costStore';
import {BigButton} from '../../components/BigButton';
import {Loading} from '../../components/Loading';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';

const COST_CATEGORIES = ['种子', '化肥', '农药', '人工', '水电', '地租', '其他'];
const INCOME_CATEGORIES = ['销售', '补贴', '其他'];

type CostCreateNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  'CostCreate'
>;

export const CostCreateScreen: React.FC = () => {
  const navigation = useNavigation<CostCreateNavigationProp>();
  const {createRecord, loading, error, clearError} = useCostStore();

  const [recordType, setRecordType] = useState<'cost' | 'income'>('cost');
  const [category, setCategory] = useState('');
  const [amount, setAmount] = useState('');
  const [recordDate, setRecordDate] = useState(dayjs().format('YYYY-MM-DD'));
  const [note, setNote] = useState('');

  const categories =
    recordType === 'cost' ? COST_CATEGORIES : INCOME_CATEGORIES;

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
      record_date: recordDate,
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
      <View style={styles.grid}>
        {categories.map(cat => (
          <View key={cat} style={styles.gridItem}>
            <BigButton
              title={cat}
              onPress={() => setCategory(cat)}
              variant={category === cat ? 'primary' : 'secondary'}
            />
          </View>
        ))}
      </View>

      <Text style={styles.sectionTitle}>金额</Text>
      <TextInput
        style={styles.input}
        placeholder="0.00"
        placeholderTextColor={colors.textSecondary}
        keyboardType="decimal-pad"
        value={amount}
        onChangeText={setAmount}
      />

      <Text style={styles.sectionTitle}>日期</Text>
      <TextInput
        style={styles.input}
        placeholder="YYYY-MM-DD"
        placeholderTextColor={colors.textSecondary}
        value={recordDate}
        onChangeText={setRecordDate}
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
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -spacing.sm,
  },
  gridItem: {
    width: '33.33%',
    paddingHorizontal: spacing.sm,
    marginBottom: spacing.md,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    backgroundColor: colors.surface,
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
