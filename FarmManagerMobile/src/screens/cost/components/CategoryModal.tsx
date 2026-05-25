import React from 'react';
import {View, Text, Modal, TouchableOpacity, StyleSheet} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import {BigButton} from '../../../components/BigButton';
import {colors} from '../../../theme/colors';
import {spacing, borderRadius} from '../../../theme/spacing';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import type {RootStackParamList} from '../../../navigation/AppNavigator';

interface CategoryModalProps {
  visible: boolean;
  categories: string[];
  selectedCategory: string;
  onSelect: (category: string) => void;
  onClose: () => void;
}

export const CategoryModal: React.FC<CategoryModalProps> = ({
  visible,
  categories,
  selectedCategory,
  onSelect,
  onClose,
}) => {
  const navigation = useNavigation();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>选择分类</Text>
            <TouchableOpacity onPress={onClose}>
              <Icon name="close" size={24} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>

          <View style={styles.modalGrid}>
            {categories.map(cat => (
              <View key={cat} style={styles.modalGridItem}>
                <BigButton
                  title={cat}
                  onPress={() => onSelect(cat)}
                  variant={selectedCategory === cat ? 'primary' : 'secondary'}
                />
              </View>
            ))}
          </View>

          <TouchableOpacity
            style={styles.manageCategoriesBtn}
            onPress={() => {
              onClose();
              // @ts-ignore
              navigation.navigate('CostCategory');
            }}>
            <Icon name="cog" size={18} color={colors.primary} />
            <Text style={styles.manageCategoriesText}>管理分类</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
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
    fontSize: 20,
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
    fontSize: 16,
    color: colors.primary,
    fontWeight: '600',
  },
});
