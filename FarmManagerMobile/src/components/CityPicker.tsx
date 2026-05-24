import React from 'react';
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
} from 'react-native';
import {colors} from '../theme/colors';
import {spacing, fontSize, borderRadius} from '../theme/spacing';
import {CITIES, type City} from '../data/cities';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

interface CityPickerProps {
  visible: boolean;
  selectedCity: string;
  onSelect: (city: City) => void;
  onClose: () => void;
}

export const CityPicker: React.FC<CityPickerProps> = ({
  visible,
  selectedCity,
  onSelect,
  onClose,
}) => {
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <Text style={styles.title}>选择城市</Text>
            <TouchableOpacity onPress={onClose} activeOpacity={0.7}>
              <Icon name="close" size={24} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>

          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={styles.list}>
            {CITIES.map(city => {
              const isSelected = city.name === selectedCity;
              return (
                <TouchableOpacity
                  key={city.name}
                  style={[styles.item, isSelected && styles.itemActive]}
                  onPress={() => {
                    onSelect(city);
                    onClose();
                  }}
                  activeOpacity={0.7}>
                  <Text
                    style={[
                      styles.itemText,
                      isSelected && styles.itemTextActive,
                    ]}>
                    {city.name}
                  </Text>
                  {isSelected && (
                    <Icon
                      name="check"
                      size={20}
                      color={colors.primary}
                    />
                  )}
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xxl,
    borderTopRightRadius: borderRadius.xxl,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxl,
    maxHeight: '70%',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.text,
  },
  list: {
    paddingHorizontal: spacing.lg,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    marginBottom: spacing.xs,
  },
  itemActive: {
    backgroundColor: colors.primaryMuted,
  },
  itemText: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  itemTextActive: {
    fontWeight: '700',
    color: colors.primary,
  },
});
