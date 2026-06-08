import { useAlertStore, type AlertButton } from "../stores/alertStore";

/**
 * 显示自定义弹窗（替代 Alert.alert）。
 *
 * 使用方式与 Alert.alert 一致：
 * showAlert("标题", "内容", [
 *   { text: "取消", style: "cancel" },
 *   { text: "确认", onPress: () => { ... } },
 * ]);
 */
export const showAlert = (
  title: string,
  message?: string,
  buttons?: AlertButton[]
) => {
  useAlertStore.getState().show(title, message, buttons);
};
