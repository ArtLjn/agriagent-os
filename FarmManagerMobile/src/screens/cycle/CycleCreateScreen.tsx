import React, {useEffect, useState} from 'react';
import {View, Text, TextInput, StyleSheet, ScrollView, Alert} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import type {RootStackParamList} from '../../navigation/AppNavigator';
import {useCycleStore} from '../../stores/cycleStore';
import {BigButton} from '../../components/BigButton';
import {Loading} from '../../components/Loading';
import {colors} from '../../theme/colors';
import {spacing, fontSize} from '../../theme/spacing';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const CycleCreateScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const {templates, loading, fetchTemplates, createCycle, error, clearError} = useCycleStore();

  const [name, setName] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState('');
  const [fieldName, setFieldName] = useState('');

  useEffect(() => { fetchTemplates(); }, []);
  useEffect(() => { if (error) { Alert.alert('错误', error); clearError(); } }, [error]);

  const handleSubmit = async () => {
    if (!name.trim() || !selectedTemplateId || !startDate.trim()) {
      Alert.alert('提示', '请填写茬口名称、选择作物模板和开始日期'); return;
    }
    await createCycle({name: name.trim(), crop_template_id: selectedTemplateId, start_date: startDate.trim(), field_name: fieldName.trim() || undefined});
    navigation.goBack();
  };

  if (loading && templates.length === 0) return <Loading />;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.label}>茬口名称</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="例如：2024春季西瓜" placeholderTextColor={colors.textSecondary} />
      <Text style={styles.label}>选择作物</Text>
      <View style={styles.templateList}>
        {templates.map(t => (
          <BigButton key={t.id} title={`${t.name} ${t.variety || ''}`} variant={selectedTemplateId === t.id ? 'primary' : 'secondary'} onPress={() => setSelectedTemplateId(t.id)} style={styles.templateButton} />
        ))}
      </View>
      <Text style={styles.label}>开始日期（YYYY-MM-DD）</Text>
      <TextInput style={styles.input} value={startDate} onChangeText={setStartDate} placeholder="2024-03-15" placeholderTextColor={colors.textSecondary} keyboardType="numbers-and-punctuation" />
      <Text style={styles.label}>地块名称（可选）</Text>
      <TextInput style={styles.input} value={fieldName} onChangeText={setFieldName} placeholder="例如：东大棚" placeholderTextColor={colors.textSecondary} />
      <BigButton title="创建茬口" onPress={handleSubmit} style={styles.submitButton} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  content: {padding: spacing.md, paddingBottom: spacing.xxl},
  label: {fontSize: fontSize.lg, fontWeight: '600', color: colors.text, marginTop: spacing.lg, marginBottom: spacing.sm},
  input: {borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: spacing.md, fontSize: fontSize.lg, backgroundColor: colors.surface, color: colors.text},
  templateList: {gap: spacing.sm},
  templateButton: {marginBottom: spacing.sm},
  submitButton: {marginTop: spacing.xl},
});
