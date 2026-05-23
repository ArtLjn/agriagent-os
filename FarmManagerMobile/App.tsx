import React from 'react';
import {StatusBar} from 'react-native';
import {AppNavigator} from './src/navigation/AppNavigator';

const App: React.FC = () => (
  <>
    <StatusBar barStyle="light-content" backgroundColor="#1B5E20" />
    <AppNavigator />
  </>
);

export default App;
