import React from 'react';
import { StatusBar } from 'react-native';
import { AppNavigator } from './src/navigation/AppNavigator';
import { colors } from './src/theme/colors';

const App: React.FC = () => (
  <>
    <StatusBar barStyle="light-content" backgroundColor={colors.headerBg} />
    <AppNavigator />
  </>
);

export default App;
