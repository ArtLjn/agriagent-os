import React, {useState, useEffect} from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  Modal,
  StyleSheet,
} from 'react-native';
import {useCategoryStore} from '../../stores/categoryStore';
import {BigButton} from '../../components/BigButton';
import {Card} from '../../components/Card';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';

export const CostCategoryScreen: React.FC = () => {
  const {categories, loading, error, fetchCategories, createCategory, deleteCategory, clearError} =
    useCategoryStore();

  const [modalVisible, setModalVisible] = useState(false);
  const [categoryType, setCategoryType] = useState<'expense' | 'income'>('expense');
  const [categoryName, setCategoryName] = useState('');

  useEffect(() => {
    fetchCategories();
  }, []);

  useEffect(() => {
    if (error) {
      Alert.alert('错误', error);
      clearError();
    }
  }, [error]);

  const handleCreate = async () => {
    if (!categoryName.trim()) {
      Alert.alert('提示', '请输入分类名称');
      return;
    }

    try {
      await createCategory({name: categoryName.trim(), category_type: categoryType});
      setModalVisible(false);
      setCategoryName('');
      setCategoryType('expense');
    } catch (err) {
      // Error 已在 store 中处理
    }
  };

  const handleDelete = (id: number, name: string) => {
    Alert.alert('确认删除', `确定要删除分类"${name}"吗？`, [
      {text: '取消', style: 'cancel'},
      {
        text: '删除',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteCategory(id);
          } catch (err) {
            // Error 已在 store 中处理
          }
        },
      },
    ]);
  };

  const expenseCategories = categories.filter(c => c.category_type === 'expense');
  const incomeCategories = categories.filter(c => c.category_type === 'income');

  return (
    <ScrollView style={localStyles.container}>
      <View style={localStyles.content}>
        {/* 支出分类 */}
        <Text style={localStyles.sectionTitle}>支出分类</Text>
        {expenseCategories.map(category => (
          <Card key={category.id} style={localStyles.categoryItem}>
            <View style={localStyles.categoryRow}>
              <Text style={localStyles.categoryName}>{category.name}</Text>
              <View style={localStyles.categoryTags}>
                {category.is_system && (
                  <Text style={localStyles.systemTag}>系统预设</Text>
                )}
                {!category.is_system && (
                  <TouchableOpacity
                    onPress={() => handleDelete(category.id, category.name)}>
                    <Text style={localStyles.deleteText}>删除</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          </Card>
        ))}

        {/* 收入分类 */}
        <Text style={localStyles.sectionTitle}>收入分类</Text>
        {incomeCategories.map(category => (
          <Card key={category.id} style={localStyles.categoryItem}>
            <View style={localStyles.categoryRow}>
              <Text style={localStyles.categoryName}>{category.name}</Text>
              <View style={localStyles.categoryTags}>
                {category.is_system && (
                  <Text style={localStyles.systemTag}>系统预设</Text>
                )}
                {!category.is_system && (
                  <TouchableOpacity
                    onPress={() => handleDelete(category.id, category.name)}>
                    <Text style={localStyles.deleteText}>删除</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          </Card>
        ))}

        {/* 新增按钮 */}
        <BigButton
          title="新增分类"
          onPress={() => setModalVisible(true)}
          disabled={loading}
          style={{marginTop: spacing.md}}
        />
      </View>

      {/* 新增分类弹窗 */}
      <Modal
        visible={modalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setModalVisible(false)}>
        <View style={localStyles.modalOverlay}>
          <View style={localStyles.modalContent}>
            <Text style={localStyles.modalTitle}>新增分类</Text>

            {/* 类型选择 */}
            <Text style={localStyles.label}>分类类型</Text>
            <View style={localStyles.typeSelector}>
              <TouchableOpacity
                style={[
                  localStyles.typeButton,
                  categoryType === 'expense' && localStyles.typeButtonActive,
                ]}
                onPress={() => setCategoryType('expense')}>
                <Text
                  style={[
                    localStyles.typeButtonText,
                    categoryType === 'expense' && localStyles.typeButtonTextActive,
                  ]}>
                  支出
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  localStyles.typeButton,
                  categoryType === 'income' && localStyles.typeButtonActive,
                ]}
                onPress={() => setCategoryType('income')}>
                <Text
                  style={[
                    localStyles.typeButtonText,
                    categoryType === 'income' && localStyles.typeButtonTextActive,
                  ]}>
                  收入
                </Text>
              </TouchableOpacity>
            </View>

            {/* 名称输入 */}
            <Text style={localStyles.label}>分类名称</Text>
            <TextInput
              style={localStyles.input}
              value={categoryName}
              onChangeText={setCategoryName}
              placeholder="请输入分类名称"
              autoFocus
            />

            {/* 按钮组 */}
            <View style={localStyles.modalButtons}>
              <TouchableOpacity
                style={[localStyles.modalButton, localStyles.modalButtonCancel]}
                onPress={() => setModalVisible(false)}>
                <Text style={localStyles.modalButtonText}>取消</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[localStyles.modalButton, localStyles.modalButtonConfirm]}
                onPress={handleCreate}>
                <Text style={localStyles.modalButtonText}>确定</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
};

const localStyles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  categoryItem: {
    marginBottom: spacing.sm,
  },
  categoryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  categoryName: {
    fontSize: fontSize.md,
    color: colors.text,
    flex: 1,
  },
  categoryTags: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  systemTag: {
    fontSize: fontSize.xs,
    color: colors.gray,
    backgroundColor: colors.grayLight,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
  },
  deleteText: {
    fontSize: fontSize.md,
    color: colors.danger,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    width: '85%',
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: fontSize.xl,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.lg,
    textAlign: 'center',
  },
  label: {
    fontSize: fontSize.md,
    color: colors.text,
    marginBottom: spacing.sm,
    marginTop: spacing.md,
  },
  typeSelector: {
    flexDirection: 'row',
    backgroundColor: colors.grayLight,
    borderRadius: borderRadius.md,
    padding: spacing.xs,
  },
  typeButton: {
    flex: 1,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    borderRadius: borderRadius.sm,
  },
  typeButtonActive: {
    backgroundColor: colors.primary,
  },
  typeButtonText: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  typeButtonTextActive: {
    color: colors.white,
    fontWeight: '600',
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    marginTop: spacing.sm,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: spacing.md,
    marginTop: spacing.xl,
  },
  modalButton: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    alignItems: 'center',
  },
  modalButtonCancel: {
    backgroundColor: colors.grayLight,
  },
  modalButtonConfirm: {
    backgroundColor: colors.primary,
  },
  modalButtonText: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: '600',
  },
});
