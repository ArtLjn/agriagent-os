import React, { useCallback, useEffect, useState } from "react";
import { showAlert } from "../../utils/alert";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Linking,
 
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import { versionApi, APP_VERSION, APP_BUILD_NUMBER, VersionInfo } from "../../api/version";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import { shadowV2 } from "../../theme/designTokens";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

type CheckState = "idle" | "checking" | "up_to_date" | "update_available" | "error";

export const AboutScreen: React.FC = () => {
  const navigation = useNavigation();
  const [checkState, setCheckState] = useState<CheckState>("idle");
  const [updateInfo, setUpdateInfo] = useState<VersionInfo | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: "关于" });
  }, []);

  const handleCheckUpdate = useCallback(async () => {
    setCheckState("checking");
    try {
      const res = await versionApi.check(APP_BUILD_NUMBER);
      const data = res.data;
      if (data.latest_version_code > APP_BUILD_NUMBER) {
        setUpdateInfo(data);
        setCheckState("update_available");
      } else {
        setCheckState("up_to_date");
      }
    } catch {
      setCheckState("error");
    }
  }, []);

  const handleDownload = () => {
    if (!updateInfo) return;
    if (updateInfo.force_update) {
      doDownload();
    } else {
      showAlert(
        `发现新版本 v${updateInfo.latest_version}`,
        updateInfo.changelog,
        [
          { text: "取消", style: "cancel" },
          { text: "立即更新", onPress: doDownload },
        ]
      );
    }
  };

  const doDownload = () => {
    if (!updateInfo) return;
    Linking.openURL(updateInfo.download_url).catch(() => {
      showAlert("提示", "无法打开下载链接");
    });
  };

  const getStatusText = () => {
    switch (checkState) {
      case "checking":
        return "正在检查...";
      case "up_to_date":
        return "已是最新版本";
      case "update_available":
        return `发现新版本 v${updateInfo?.latest_version}`;
      case "error":
        return "检查失败，请稍后重试";
      default:
        return "";
    }
  };

  const getStatusColor = () => {
    switch (checkState) {
      case "up_to_date":
        return colors.success;
      case "update_available":
        return colors.primary;
      case "error":
        return colors.danger;
      default:
        return colors.textSecondary;
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* App Identity */}
        <View style={styles.identitySection}>
          <View style={styles.appIcon}>
            <Icon name="sprout" size={40} color={colors.primary} />
          </View>
          <Text style={styles.appName}>智能种植助手</Text>
          <Text style={styles.versionText}>v{APP_VERSION}</Text>
        </View>

        {/* Check Update Card */}
        <View style={styles.card}>
          <TouchableOpacity
            style={styles.updateRow}
            onPress={
              checkState === "update_available"
                ? handleDownload
                : handleCheckUpdate
            }
            activeOpacity={0.7}
            disabled={checkState === "checking"}
          >
            <View style={styles.updateLeft}>
              <View
                style={[
                  styles.updateIcon,
                  checkState === "update_available" && styles.updateIconActive,
                ]}
              >
                <Icon
                  name={
                    checkState === "update_available"
                      ? "download"
                      : "update"
                  }
                  size={20}
                  color={
                    checkState === "update_available"
                      ? colors.surface
                      : colors.primary
                  }
                />
              </View>
              <View style={styles.updateTextWrap}>
                <Text style={styles.updateLabel}>
                  {checkState === "update_available"
                    ? "立即更新"
                    : "检查更新"}
                </Text>
                {checkState !== "idle" && (
                  <View style={styles.statusRow}>
                    {checkState === "checking" && (
                      <ActivityIndicator size="small" color={colors.primary} />
                    )}
                    <Text style={[styles.statusText, { color: getStatusColor() }]}>
                      {getStatusText()}
                    </Text>
                  </View>
                )}
              </View>
            </View>

            {checkState === "update_available" ? (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>NEW</Text>
              </View>
            ) : (
              <Icon
                name="chevron-right"
                size={20}
                color={colors.textTertiary}
              />
            )}
          </TouchableOpacity>
        </View>

        {/* Changelog */}
        {updateInfo && updateInfo.changelog && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>更新内容</Text>
            <Text style={styles.changelogText}>{updateInfo.changelog}</Text>
          </View>
        )}

        {/* Info Card */}
        <View style={styles.card}>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>应用名称</Text>
            <Text style={styles.infoValue}>智能种植助手</Text>
          </View>
          <View style={styles.infoDivider} />
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>版本号</Text>
            <Text style={styles.infoValue}>v{APP_VERSION}</Text>
          </View>
        </View>

        {/* Footer */}
        <Text style={styles.footer}>
          Made with care for farmers
        </Text>
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
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.xxl,
    paddingBottom: spacingV2.xxxl,
  },
  identitySection: {
    alignItems: "center",
    marginBottom: spacingV2.xxl,
  },
  appIcon: {
    width: 80,
    height: 80,
    borderRadius: 24,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacingV2.md,
  },
  appName: {
    fontSize: fontSizeV2.xl,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: -0.3,
  },
  versionText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 4,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingVertical: spacingV2.md,
    paddingHorizontal: spacingV2.lg,
    marginBottom: spacingV2.md,
    ...shadowV2.light,
  },
  updateRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacingV2.xs,
  },
  updateLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
    flex: 1,
  },
  updateIcon: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  updateIconActive: {
    backgroundColor: colors.primary,
  },
  updateTextWrap: {
    flex: 1,
  },
  updateLabel: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.text,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
    marginTop: 2,
  },
  statusText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "500",
  },
  badge: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacingV2.sm,
    paddingVertical: 2,
    borderRadius: borderRadiusV2.full,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.surface,
    letterSpacing: 0.5,
  },
  cardTitle: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.textSecondary,
    marginBottom: spacingV2.sm,
  },
  changelogText: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    lineHeight: 22,
  },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacingV2.sm,
  },
  infoDivider: {
    height: 1,
    backgroundColor: colors.borderLight,
  },
  infoLabel: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
  },
  infoValue: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "500",
  },
  footer: {
    textAlign: "center",
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    marginTop: spacingV2.xl,
  },
});
