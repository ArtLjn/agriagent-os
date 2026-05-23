const {getDefaultConfig, mergeConfig} = require('@react-native/metro-config');

const config = getDefaultConfig(__dirname);

module.exports = mergeConfig(config, config);
