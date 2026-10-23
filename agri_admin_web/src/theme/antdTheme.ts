import { theme } from 'antd';
import type { ThemeConfig } from 'antd';
import type { AppThemeMode } from './themeMode';

const FONT_FAMILY =
  "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', Inter, ui-sans-serif, system-ui, sans-serif";

const lightTheme: ThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#99563e',
    colorInfo: '#99563e',
    colorLink: '#99563e',
    colorSuccess: '#2f9e63',
    colorWarning: '#d98a2b',
    colorError: '#d9503f',
    colorBgBase: '#f2f0ed',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorFillAlter: 'rgba(41, 40, 39, 0.04)',
    colorBorder: 'rgba(41, 40, 39, 0.14)',
    colorBorderSecondary: 'rgba(41, 40, 39, 0.08)',
    colorSplit: 'rgba(41, 40, 39, 0.08)',
    colorText: '#292827',
    colorTextSecondary: '#615d58',
    colorTextTertiary: '#706b65',
    colorTextPlaceholder: '#706b65',
    colorTextQuaternary: 'rgba(41, 40, 39, 0.28)',
    borderRadius: 8,
    fontSize: 16,
    controlHeight: 40,
    fontFamily: FONT_FAMILY,
    boxShadow: '0 12px 40px rgba(41, 40, 39, 0.12)',
    boxShadowSecondary: '0 18px 50px rgba(41, 40, 39, 0.16)',
  },
  components: {
    Button: {
      borderRadius: 8,
      controlHeight: 40,
      primaryShadow: 'none',
      primaryColor: '#ffffff',
      defaultBg: 'rgba(255, 255, 255, 0.72)',
      defaultBorderColor: 'rgba(41, 40, 39, 0.12)',
      defaultColor: '#292827',
    },
    Card: {
      borderRadiusLG: 8,
      headerBg: 'transparent',
    },
    Input: {
      activeBorderColor: '#99563e',
      hoverBorderColor: 'rgba(41, 40, 39, 0.22)',
      activeShadow: '0 0 0 3px rgba(153, 86, 62, 0.14)',
    },
    Select: {
      optionSelectedBg: 'rgba(153, 86, 62, 0.12)',
    },
    Table: {
      headerBg: 'rgba(41, 40, 39, 0.04)',
      rowHoverBg: 'rgba(153, 86, 62, 0.06)',
      borderColor: 'rgba(41, 40, 39, 0.08)',
      headerSplitColor: 'rgba(41, 40, 39, 0.08)',
    },
    Tabs: {
      itemSelectedColor: '#292827',
      itemHoverColor: '#99563e',
      inkBarColor: '#99563e',
    },
    Modal: {
      contentBg: '#ffffff',
      headerBg: 'transparent',
    },
    Menu: {
      itemBg: 'transparent',
      subMenuItemBg: 'transparent',
      itemColor: '#615d58',
      itemHoverColor: '#292827',
      itemHoverBg: 'rgba(41, 40, 39, 0.05)',
      itemSelectedColor: '#854832',
      itemSelectedBg: 'rgba(153, 86, 62, 0.1)',
      groupTitleColor: '#706b65',
    },
  },
};

const darkTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#dea58f',
    colorPrimaryBg: '#3b302c',
    colorPrimaryHover: '#edbba8',
    colorPrimaryActive: '#cc947e',
    colorInfo: '#edbba8',
    colorLink: '#dea58f',
    colorSuccess: '#4ecb7c',
    colorWarning: '#f0a44a',
    colorError: '#ff6b5b',
    colorBgBase: '#202020',
    colorBgContainer: '#292929',
    colorBgElevated: '#303030',
    colorFillAlter: 'rgba(255, 255, 255, 0.04)',
    colorBorder: 'rgba(255, 255, 255, 0.1)',
    colorBorderSecondary: 'rgba(255, 255, 255, 0.08)',
    colorSplit: 'rgba(255, 255, 255, 0.08)',
    colorText: '#ebe8e4',
    colorTextSecondary: '#b9b5af',
    colorTextTertiary: '#a7a29b',
    colorTextPlaceholder: '#a7a29b',
    colorTextQuaternary: 'rgba(226, 236, 248, 0.24)',
    borderRadius: 8,
    fontSize: 16,
    controlHeight: 40,
    fontFamily: FONT_FAMILY,
    boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
    boxShadowSecondary: '0 24px 64px rgba(0, 0, 0, 0.55)',
  },
  components: {
    Button: {
      borderRadius: 8,
      controlHeight: 40,
      primaryShadow: 'none',
      primaryColor: '#292827',
      colorPrimary: '#dea58f',
      colorPrimaryHover: '#edbba8',
      colorPrimaryActive: '#cc947e',
      defaultBg: 'rgba(255, 255, 255, 0.08)',
      defaultBorderColor: 'rgba(255, 255, 255, 0.08)',
      defaultColor: '#ebe8e4',
    },
    Card: {
      borderRadiusLG: 8,
      headerBg: 'transparent',
    },
    Input: {
      activeBorderColor: '#dea58f',
      hoverBorderColor: 'rgba(255, 255, 255, 0.2)',
      activeShadow: '0 0 0 3px rgba(153, 86, 62, 0.24)',
    },
    Select: {
      optionSelectedBg: 'rgba(153, 86, 62, 0.18)',
    },
    Table: {
      headerBg: 'rgba(255, 255, 255, 0.04)',
      rowHoverBg: 'rgba(255, 255, 255, 0.045)',
      borderColor: 'rgba(255, 255, 255, 0.08)',
      headerSplitColor: 'rgba(255, 255, 255, 0.08)',
    },
    Tabs: {
      itemSelectedColor: '#ebe8e4',
      itemHoverColor: '#dea58f',
      inkBarColor: '#edbba8',
    },
    Modal: {
      contentBg: '#303030',
      headerBg: 'transparent',
    },
    Menu: {
      itemBg: 'transparent',
      subMenuItemBg: 'transparent',
      itemColor: '#b9b5af',
      itemHoverColor: '#ffffff',
      itemHoverBg: 'rgba(255, 255, 255, 0.06)',
      itemSelectedColor: '#edbba8',
      itemSelectedBg: 'rgba(153, 86, 62, 0.18)',
      groupTitleColor: '#a7a29b',
    },
  },
};

export const adminThemes: Record<AppThemeMode, ThemeConfig> = {
  light: lightTheme,
  dark: darkTheme,
};
