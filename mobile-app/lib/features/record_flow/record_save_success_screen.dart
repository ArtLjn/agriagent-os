import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'record_flow_controller.dart';
import 'record_flow_widgets.dart';

class RecordSaveSuccessScreen extends StatelessWidget {
  const RecordSaveSuccessScreen({
    super.key,
    required this.result,
    this.onGoHome,
    this.onGoLedger,
    this.onRecordAgain,
  });

  final RecordSaveResult result;
  final VoidCallback? onGoHome;
  final VoidCallback? onGoLedger;
  final VoidCallback? onRecordAgain;

  void _goRecord(BuildContext context) {
    Navigator.of(context).popUntil((route) => route.isFirst);
    onRecordAgain?.call();
  }

  void _goLedger(BuildContext context) {
    Navigator.of(context).popUntil((route) => route.isFirst);
    onGoLedger?.call();
  }

  void _goHome(BuildContext context) {
    Navigator.of(context).popUntil((route) => route.isFirst);
    onGoHome?.call();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _goRecord(context);
      },
      child: FlowScaffold(
        title: '',
        bottomPadding: 96,
        bottomBar: StickyActionBar(
          children: [
            Expanded(
              child: FlowButton(
                label: '完成',
                onTap: () => _goRecord(context),
              ),
            ),
          ],
        ),
        children: [
          const SuccessEmblem(),
          Text(
            '记录已保存',
            textAlign: TextAlign.center,
            style: AppTextStyles.title.copyWith(fontSize: 24),
          ),
          const SizedBox(height: 8),
          Text(
            result.label,
            textAlign: TextAlign.center,
            style: AppTextStyles.body.copyWith(
              color: AppColors.muted,
              fontSize: 14,
            ),
          ),
          const SizedBox(height: 20),
          _ResultSummaryCard(json: result.json),
          const SizedBox(height: 12),
          SuccessActionCard(
            onAgain: () => _goRecord(context),
            onLedger: () => _goLedger(context),
            onHome: () => _goHome(context),
          ),
          const SizedBox(height: 12),
          const ManagerTipCard(),
        ],
      ),
    );
  }
}

class _ResultSummaryCard extends StatelessWidget {
  const _ResultSummaryCard({required this.json});

  final Map<String, dynamic> json;

  @override
  Widget build(BuildContext context) {
    final rows = _summaryRows(json);
    return FieldGroupCard(
      title: '保存结果',
      icon: Icons.check_circle_outline,
      color: AppColors.greenDark,
      background: AppColors.greenSoft,
      rows: rows.isEmpty
          ? const [FieldValueRow(label: '状态', value: '已保存')]
          : rows
              .map((entry) =>
                  FieldValueRow(label: entry.key, value: entry.value))
              .toList(),
    );
  }
}

List<MapEntry<String, String>> _summaryRows(Map<String, dynamic> json) {
  const preferred = [
    'record_type',
    'category',
    'amount',
    'record_date',
    'note',
    'operation_type',
    'work_date',
    'counterparty',
    'name',
    'title',
    'created_at',
  ];
  final rows = <MapEntry<String, String>>[];
  for (final key in preferred) {
    final value = json[key];
    if (value != null && '$value'.isNotEmpty) {
      rows.add(MapEntry(_fieldLabel(key), _formatFieldValue(key, value)));
    }
    if (rows.length == 5) return rows;
  }
  for (final entry in json.entries) {
    if (_hiddenKeys.contains(entry.key)) continue;
    final label = _fieldLabel(entry.key);
    if (rows.any((row) => row.key == label)) continue;
    if (entry.value == null || '${entry.value}'.isEmpty) continue;
    rows.add(MapEntry(label, _formatFieldValue(entry.key, entry.value)));
    if (rows.length == 5) break;
  }
  return rows;
}

const _hiddenKeys = {
  'id',
  'cycle_id',
  'parent_record_id',
  'settlement_status',
  'settled_amount',
  'settled_at',
  'unsettled_amount',
  'unsettled_cost',
  'unsettled_income',
  'due_date',
};

String _fieldLabel(String key) {
  return switch (key) {
    'record_type' => '类型',
    'category' => '分类',
    'amount' => '金额',
    'record_date' => '日期',
    'note' => '备注',
    'counterparty' => '对象',
    'operation_type' => '作业类型',
    'work_date' => '作业日期',
    'name' => '名称',
    'title' => '标题',
    'created_at' => '保存时间',
    _ => key,
  };
}

String _formatFieldValue(String key, Object? value) {
  if (key == 'record_type') return _recordTypeLabel(value);
  if (key.endsWith('_date') || key.endsWith('_at')) return _formatDate(value);
  return '${value ?? '-'}';
}

String _recordTypeLabel(Object? value) {
  return switch ('${value ?? ''}'.trim().toLowerCase()) {
    'cost' => '支出',
    'income' => '收入',
    'debt' => '欠款',
    'daily' => '日常',
    '' => '-',
    _ => '$value',
  };
}

String _formatDate(Object? value) {
  final text = '${value ?? ''}'.trim();
  if (text.isEmpty) return '-';
  final date = DateTime.tryParse(text);
  if (date == null) return text;
  final month = date.month.toString().padLeft(2, '0');
  final day = date.day.toString().padLeft(2, '0');
  return '${date.year}-$month-$day';
}
