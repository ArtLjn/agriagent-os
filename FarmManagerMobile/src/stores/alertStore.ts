import { create } from "zustand";

export interface AlertButton {
  text: string;
  onPress?: () => void;
  style?: "default" | "cancel" | "destructive";
}

interface AlertState {
  visible: boolean;
  title: string;
  message: string;
  buttons: AlertButton[];
  show: (title: string, message?: string, buttons?: AlertButton[]) => void;
  hide: () => void;
}

export const useAlertStore = create<AlertState>((set) => ({
  visible: false,
  title: "",
  message: "",
  buttons: [{ text: "确定" }],
  show: (title, message = "", buttons = [{ text: "确定" }]) =>
    set({ visible: true, title, message, buttons }),
  hide: () => set({ visible: false }),
}));
