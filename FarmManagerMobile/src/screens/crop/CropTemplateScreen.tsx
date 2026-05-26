import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Alert,
  RefreshControl,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import {cropApi} from '../../api/client';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';

interface GrowthStage {
  id: number;
  name: string;
  duration_days: number;
  order_index: number;
  key_tasks?: string | null;
}

interface CropTemplate {
  id: number;
  name: string;
  variety?: string | null;
  stages: GrowthStage[];
}

export const CropTemplateScreen: React.FC = () => {
  const [templates, setTemplates] = useState<CropTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const res = await cropApi.getTemplates();
      const data = res.data as any;
      setTemplates(data.items ?? data ?? []);
    } catch (err: any) {
      Alert.alert('加载失败', err.message || '请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchTemplates();
    setRefreshing(false);
  };

  const renderTemplateItem = ({item}: {item: CropTemplate}) => (
    <View style={styles.templateCard}>
      <View style={styles.templateHeader}>
        <Text style={styles.templateName}>{item.name}</Text>
        {item.variety && (
          <Text style={styles.templateVariety}>品种：{item.variety}</Text>
        )}
      </View>
      <Text style={styles.stageTitle}>生长阶段：</Text>
      {item.stages.map(stage => (
        <View key={stage.id} style={styles.stageRow}>
          <Text style={styles.stageName}>{stage.order_index + 1}. {stage.name}</Text>
          <Text style={styles.stageDuration}>{stage.duration_days}天</Text>
        </View>
      ))}
      {item.stages.length === 0 && (
        <Text style={styles.emptyStage}>暂无阶段信息</Text>
      )}
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>作物模板</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => Alert.alert('提示', '创建模板功能后续开放')}>
          <Icon name="plus" size={24} color={colors.primary} />
        </TouchableOpacity>
      </View>

      <FlatList
        data={templates}
        keyExtractor={item => String(item.id)}
        renderItem={renderTemplateItem}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>暂无作物模板</Text>
            </View>
          ) : null
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  headerTitle: {fontSize: fontSize.xl, fontWeight: '700', color: colors.text},
  addButton: {padding: spacing.sm},
  listContent: {padding: spacing.md},
  templateCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  templateHeader: {marginBottom: spacing.sm},
  templateName: {fontSize: fontSize.lg, fontWeight: '700', color: colors.text},
  templateVariety: {fontSize: fontSize.sm, color: colors.textSecondary, marginTop: spacing.xs},
  stageTitle: {fontSize: fontSize.md, fontWeight: '600', marginTop: spacing.sm, color: colors.text},
  stageRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
  },
  stageName: {fontSize: fontSize.sm, color: colors.text},
  stageDuration: {fontSize: fontSize.sm, color: colors.textSecondary},
  emptyStage: {fontSize: fontSize.sm, color: colors.textSecondary, marginTop: spacing.xs},
  emptyContainer: {alignItems: 'center', paddingVertical: spacing.xl},
  emptyText: {color: colors.textSecondary, fontSize: fontSize.md},
});
