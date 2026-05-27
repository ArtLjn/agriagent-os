import React from 'react';
import {Text} from 'react-native';

const Icon = ({name, size, color, style}) => (
  <Text style={[{fontSize: size, color}, style]}>{name}</Text>
);

export default Icon;
