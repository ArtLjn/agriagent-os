import React from "react";
import { StatusBar } from "react-native";
import { AppNavigator } from "./src/navigation/AppNavigator";
import { colors } from "./src/theme/colors";
import { UpdateDialog } from "./src/components/UpdateDialog";

const App: React.FC = () => (
  <>
    <StatusBar barStyle="light-content" backgroundColor={colors.headerBg} />
    <AppNavigator />
    <UpdateDialog />
  </>
);

export default App;
