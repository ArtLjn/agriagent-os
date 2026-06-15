import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  extractDownloadUrl,
  formatVersionLabel,
  normalizeAppVersion,
} from '../dist-test/api/appVersionCore.js';

test('从后端版本响应中读取 APK 下载链接', () => {
  const response = {
    latest_version: '1.2.3',
    latest_version_code: 12,
    download_url: 'https://apk.farm.lllcnm.cn/app-release.apk',
    changelog: '更新说明',
    force_update: false,
  };

  assert.equal(
    extractDownloadUrl(response),
    'https://apk.farm.lllcnm.cn/app-release.apk',
  );
});

test('后端未返回下载链接时保留默认链接兜底', () => {
  assert.equal(extractDownloadUrl({ download_url: '' }), '/downloads/farm-manager-latest.apk');
});

test('规范化后端版本响应供页面展示', () => {
  const version = normalizeAppVersion({
    latest_version: '1.2.8',
    latest_version_code: 14,
    download_url: 'https://apk.farm.lllcnm.cn/app-release.apk',
    changelog: '优化发布脚本',
    force_update: true,
  });

  assert.deepEqual(version, {
    latestVersion: '1.2.8',
    latestVersionCode: 14,
    downloadUrl: 'https://apk.farm.lllcnm.cn/app-release.apk',
    changelog: '优化发布脚本',
    forceUpdate: true,
  });
});

test('版本号展示自动补齐 v 前缀', () => {
  assert.equal(formatVersionLabel('1.2.8'), 'v1.2.8');
  assert.equal(formatVersionLabel('v1.2.8'), 'v1.2.8');
});
