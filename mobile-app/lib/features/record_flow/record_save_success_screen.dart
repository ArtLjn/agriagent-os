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
    return FlowScaffold(
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
    'id',
    'name',
    'title',
    'category',
    'amount',
    'record_type',
    'counterparty',
    'operation_type',
    'work_date',
    'created_at',
  ];
  final rows = <MapEntry<String, String>>[];
  for (final key in preferred) {
    final value = json[key];
    if (value != null && '$value'.isNotEmpty) {
      rows.add(MapEntry(key, '$value'));
    }
    if (rows.length == 5) return rows;
  }
  for (final entry in json.entries) {
    if (rows.any((row) => row.key == entry.key)) continue;
    if (entry.value == null || '${entry.value}'.isEmpty) continue;
    rows.add(MapEntry(entry.key, '${entry.value}'));
    if (rows.length == 5) break;
  }
  return rows;
}
