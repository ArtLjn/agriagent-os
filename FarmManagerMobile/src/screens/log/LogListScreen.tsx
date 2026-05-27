import React, { useEffect } from "react";
import { View, Text, StyleSheet, FlatList } from "react-native";
import {
  useNavigation,
  useRoute,
  type RouteProp,
} from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { useLogStore } from "../../stores/logStore";
import { Card } from "../../components/Card";
import { BigButton } from "../../components/BigButton";
import { Loading } from "../../components/Loading";
import { EmptyState } from "../../components/EmptyState";
import { colors } from "../../theme/colors";
import { spacing, fontSize } from "../../theme/spacing";

type RouteParams = RouteProp<RootStackParamList, "LogList">;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const OPERATION_LABELS: Record<string, string> = {
  sowing: "播种",
  fertilizing: "施肥",
  watering: "浇水",
  weeding: "除草",
  pest_control: "病虫害防治",
  pruning: "修剪",
  harvesting: "采收",
  other: "其他",
};

export const LogListScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const { cycleId } = route.params;
  const { logs, loading, fetchLogs } = useLogStore();

  useEffect(() => {
    fetchLogs(cycleId);
  }, [cycleId]);

  if (loading && logs.length === 0) {
    return <Loading />;
  }
  if (logs.length === 0) {
    return (
      <EmptyState
        title="暂无记录"
        subtitle="记录每一次农事活动"
        actionLabel="添加记录"
        onAction={() => navigation.navigate("LogCreate", { cycleId })}
      />
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={logs}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <Card style={styles.card}>
            <View style={styles.row}>
              <Text style={styles.type}>
                {OPERATION_LABELS[item.operation_type] || item.operation_type}
              </Text>
              <Text style={styles.date}>{item.operation_date}</Text>
            </View>
            {item.note && <Text style={styles.note}>{item.note}</Text>}
          </Card>
        )}
        ListFooterComponent={
          <BigButton
            title="+ 添加记录"
            variant="secondary"
            onPress={() => navigation.navigate("LogCreate", { cycleId })}
            style={styles.addButton}
          />
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  list: { padding: spacing.md, paddingBottom: spacing.xxl },
  card: { marginBottom: spacing.md },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  type: { fontSize: fontSize.lg, fontWeight: "600", color: colors.primary },
  date: { fontSize: fontSize.md, color: colors.textSecondary },
  note: { fontSize: fontSize.md, color: colors.text },
  addButton: { marginTop: spacing.md },
});
