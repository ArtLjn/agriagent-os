import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Linking,
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { versionApi, getAppVersionCode, VersionInfo } from '../api/version';

export function UpdateDialog() {
  const [visible, setVisible] = useState(false);
  const [info, setInfo] = useState<VersionInfo | null>(null);

  const checkUpdate = useCallback(async () => {
    try {
      const code = await getAppVersionCode();
      const res = await versionApi.check(code);
      const data = res.data;
      if (data.latest_version_code > code) {
        setInfo(data);
        setVisible(true);
      }
    } catch {
      // 静默失败
    }
  }, []);

  useEffect(() => {
    checkUpdate();
  }, [checkUpdate]);

  const handleDownload = () => {
    if (!info) return;
    setVisible(false);
    Linking.openURL(info.download_url).catch(() => {
      Alert.alert('提示', '无法打开下载链接，请手动访问下载页面');
    });
  };

  const handleLater = () => {
    if (info?.force_update) return;
    setVisible(false);
  };

  if (!info) return null;

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={handleLater}>
      <View style={styles.overlay}>
        <View style={styles.dialog}>
          <Text style={styles.title}>发现新版本 v{info.latest_version}</Text>
          <Text style={styles.changelog}>{info.changelog}</Text>

          <TouchableOpacity style={styles.primaryBtn} onPress={handleDownload}>
            <Text style={styles.primaryBtnText}>立即更新</Text>
          </TouchableOpacity>

          {!info.force_update && (
            <TouchableOpacity style={styles.secondaryBtn} onPress={handleLater}>
              <Text style={styles.secondaryBtnText}>稍后再说</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  dialog: {
    width: '80%',
    maxWidth: 340,
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 24,
    alignItems: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1a1a1a',
    marginBottom: 12,
  },
  changelog: {
    fontSize: 14,
    color: '#666',
    lineHeight: 20,
    textAlign: 'center',
    marginBottom: 24,
  },
  primaryBtn: {
    width: '100%',
    height: 48,
    backgroundColor: '#4F8CFF',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
  secondaryBtn: {
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  secondaryBtnText: {
    fontSize: 14,
    color: '#999',
  },
});
