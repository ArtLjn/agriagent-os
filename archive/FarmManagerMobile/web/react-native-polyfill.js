// react-native-web polyfill: 补齐原生模块缺失的 API
export * from 'react-native-web';

// requireNativeComponent: 被 react-native-svg、react-native-linear-gradient 等调用
export const requireNativeComponent = (_name) => {
  // web 环境下返回空组件
  return 'div';
};

// 部分库可能直接访问 NativeModules
export const NativeModules = {};

// UIManager 在 web 上的 stub
export const UIManager = {};
