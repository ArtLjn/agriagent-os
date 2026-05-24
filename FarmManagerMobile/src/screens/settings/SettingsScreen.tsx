import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { Card } from '../../components/Card';
import { colors } from '../../theme/colors';
import { spacing, fontSize, borderRadius } from '../../theme/spacing';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

const AI_SECTION = [
  { label: '农事顾问', icon: 'chat-processing', color: colors.primary, route: 'AgentChat' },
  { label: '种植报告', icon: 'file-document', color: colors.success, route: 'AgentReport' },
];

const ABOUT_SECTION = [
  { label: '版本', value: 'v1.0', icon: 'tag', color: colors.textTertiary },
  { label: '使用指南', value: '', icon: 'book-open-variant', color: colors.primary, route: 'Guide' },
  { label: '关于', value: '智能种植管理平台', icon: 'information', color: colors.textTertiary },
];

export const SettingsScreen: React.FC = () => {
  const navigation = useNavigation();

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Profile Header */}
        <View style={styles.profileSection}>
          <View style={styles.profileCard}>
            <View style={styles.avatar}>
              <Icon name="account" size={32} color={colors.primary} />
            </View>
            <View style={styles.profileInfo}>
              <Text style={styles.profileName}>农事助手</Text>
              <Text style={styles.profileSub}>让种植更简单</Text>
            </View>
          </View>
        </View>

        {/* AI Features */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>AI 功能</Text>
          <Card elevated={false} style={styles.menuCard}>
            {AI_SECTION.map((item, index) => (
              <TouchableOpacity
                key={item.label}
                style={[
                  styles.menuItem,
                  index < AI_SECTION.length - 1 && styles.menuItemBorder,
                ]}
                onPress={() => navigation.navigate(item.route as never)}
                activeOpacity={0.6}
              >
                <View style={styles.menuLeft}>
                  <View style={[styles.menuIcon, { backgroundColor: item.color + '12' }]}>
                    <Icon name={item.icon} size={20} color={item.color} />
                  </View>
                  <Text style={styles.menuText}>{item.label}</Text>
                </View>
                <Icon name="chevron-right" size={20} color={colors.textTertiary} />
              </TouchableOpacity>
            ))}
          </Card>
        </View>

        {/* About */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>关于</Text>
          <Card elevated={false} style={styles.menuCard}>
            {ABOUT_SECTION.map((item, index) =>
              item.route ? (
                <TouchableOpacity
                  key={item.label}
                  style={[
                    styles.infoItem,
                    index < ABOUT_SECTION.length - 1 && styles.menuItemBorder,
                  ]}
                  onPress={() => navigation.navigate(item.route as never)}
                  activeOpacity={0.6}
                >
                  <View style={styles.menuLeft}>
                    <View style={[styles.menuIcon, { backgroundColor: item.color + '12' }]}>
                      <Icon name={item.icon} size={20} color={item.color} />
                    </View>
                    <Text style={styles.menuText}>{item.label}</Text>
                  </View>
                  <Icon name="chevron-right" size={20} color={colors.textTertiary} />
                </TouchableOpacity>
              ) : (
                <View
                  key={item.label}
                  style={[
                    styles.infoItem,
                    index < ABOUT_SECTION.length - 1 && styles.menuItemBorder,
                  ]}
                >
                  <View style={styles.menuLeft}>
                    <View style={[styles.menuIcon, { backgroundColor: item.color + '12' }]}>
                      <Icon name={item.icon} size={20} color={item.color} />
                    </View>
                    <Text style={styles.menuText}>{item.label}</Text>
                  </View>
                  <Text style={styles.infoValue}>{item.value}</Text>
                </View>
              )
            )}
          </Card>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingBottom: spacing.xxl,
  },
  profileSection: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
  },
  profileCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.headerBg,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: borderRadius.lg,
    backgroundColor: 'rgba(255,255,255,0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.headerText,
  },
  profileSub: {
    fontSize: fontSize.sm,
    color: 'rgba(255,255,255,0.6)',
    marginTop: 2,
  },
  section: {
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing.md,
  },
  menuCard: {
    padding: 0,
    overflow: 'hidden',
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
  },
  menuItemBorder: {
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  menuLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuText: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: '500',
  },
  infoItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
  },
  infoValue: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
});
