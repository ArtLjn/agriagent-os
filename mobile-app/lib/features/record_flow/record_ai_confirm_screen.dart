import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'record_flow_controller.dart';
import 'record_flow_widgets.dart';
import 'record_manual_edit_screen.dart';
import 'record_save_success_screen.dart';

class RecordAiConfirmScreen extends StatefulWidget {
  const RecordAiConfirmScreen({
    super.key,
    required this.controller,
    required this.draft,
    this.onGoHome,
    this.onGoLedger,
    this.onRecordAgain,
  });

  final RecordFlowController controller;
  final RecordDraft draft;
  final VoidCallback? onGoHome;
  final VoidCallback? onGoLedger;
  final VoidCallback? onRecordAgain;

  @override
  State<RecordAiConfirmScreen> createState() => _RecordAiConfirmScreenState();
}

class _RecordAiConfirmScreenState extends State<RecordAiConfirmScreen> {
  bool _saving = false;
  String? _error;

  void _openManualEdit() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RecordManualEditScreen(
          controller: widget.controller,
          draft: widget.draft,
          onGoHome: widget.onGoHome,
          onGoLedger: widget.onGoLedger,
          onRecordAgain: widget.onRecordAgain,
        ),
      ),
    );
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final result = await widget.controller.save(widget.draft);
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => RecordSaveSuccessScreen(
            result: result,
            onGoHome: widget.onGoHome,
            onGoLedger: widget.onGoLedger,
            onRecordAgain: widget.onRecordAgain,
          ),
        ),
      );
    } on MissingRecordFieldsException catch (error) {
      _setError('还有字段需要补充：${error.fields.join('、')}');
    } on UnsupportedRecordSceneException catch (error) {
      _setError('暂不支持保存该记录类型：${error.scene}');
    } catch (_) {
      _setError('保存失败，请检查后再试');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _setError(String message) {
    if (!mounted) return;
    setState(() => _error = message);
  }

  @override
  Widget build(BuildContext context) {
    final fields = widget.draft.fields.entries.toList();
    return FlowScaffold(
      title: '智能确认',
      centerTitle: true,
      bottomBar: StickyActionBar(
        children: [
          Expanded(
            child: FlowButton(
              label: '改一下',
              primary: false,
              onTap: _openManualEdit,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: FlowButton(
              label: _saving ? '保存中' : '确认保存',
              onTap: _save,
            ),
          ),
        ],
      ),
      children: [
        const StepIndicator(),
        _RecordUnderstandingCard(draft: widget.draft),
        const SizedBox(height: 14),
        _OriginalTextCard(text: widget.draft.originalText),
        const SizedBox(height: 14),
        FieldGroupCard(
          title: '识别字段',
          icon: LucideIcons.listChecks,
          color: AppColors.blue,
          background: AppColors.blueSoft,
          rows: fields.isEmpty
              ? const [FieldValueRow(label: '状态', value: '暂无字段')]
              : fields
                  .map(
                    (entry) => FieldValueRow(
                      label: _fieldLabel(entry.key),
                      value: _formatFieldValue(entry.key, entry.value),
                    ),
                  )
                  .toList(),
        ),
        if (widget.draft.missingFields.isNotEmpty) ...[
          const SizedBox(height: 14),
          _NoticeCard(
            icon: LucideIcons.circleAlert,
            color: AppColors.amber,
            text: '待补充：${widget.draft.missingFields.join('、')}',
          ),
        ],
        if (widget.draft.warnings.isNotEmpty) ...[
          const SizedBox(height: 14),
          _NoticeCard(
            icon: LucideIcons.info,
            color: AppColors.purple,
            text: widget.draft.warnings.join('；'),
          ),
        ],
        if (_error != null) ...[
          const SizedBox(height: 14),
          _NoticeCard(
            icon: LucideIcons.triangleAlert,
            color: AppColors.amber,
            text: _error!,
          ),
        ],
        const SizedBox(height: 14),
        const FlowHintCard(text: '不确定？点改一下补全后再保存'),
      ],
    );
  }
}

class _RecordUnderstandingCard extends StatelessWidget {
  const _RecordUnderstandingCard({required this.draft});

  final RecordDraft draft;

  @override
  Widget build(BuildContext context) {
    final amount =
        _pickField(draft.fields, const ['amount', 'total', 'paid_amount']);
    final category =
        _pickField(draft.fields, const ['category', 'operation_type', 'name']);
    return CardPanel(
      radius: 18,
      padding: const EdgeInsets.all(16),
      borderColor: Colors.transparent,
      gradient: const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFF68A1FF), AppColors.blue],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                '我理解为',
                style: AppTextStyles.body.copyWith(
                  color: Colors.white.withValues(alpha: 0.82),
                  fontSize: 14,
                ),
              ),
              Text(
                _sceneLabel(draft.scene),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  height: 26 / 20,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0,
                ),
              ),
            ],
          ),
          if (amount != null) ...[
            const SizedBox(height: 12),
            Text(
              _formatValue(amount),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 32,
                height: 38 / 32,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
            ),
          ],
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              if (category != null)
                FlowChip(
                  label: _formatValue(category),
                  icon: LucideIcons.tag,
                  color: AppColors.blue,
                  background: const Color(0xEEFFFFFF),
                ),
              FlowChip(
                label: draft.missingFields.isEmpty ? '可保存' : '需补充',
                icon: draft.missingFields.isEmpty
                    ? LucideIcons.circleCheck
                    : LucideIcons.circleAlert,
                color: draft.missingFields.isEmpty
                    ? AppColors.greenDark
                    : AppColors.amber,
                background: const Color(0xEEFFFFFF),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _OriginalTextCard extends StatelessWidget {
  const _OriginalTextCard({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(14),
      child: Text(
        text.isEmpty ? '用户原话待补充' : '用户原话  $text',
        style: AppTextStyles.body.copyWith(color: AppColors.ink2),
      ),
    );
  }
}

class _NoticeCard extends StatelessWidget {
  const _NoticeCard({
    required this.icon,
    required this.color,
    required this.text,
  });

  final IconData icon;
  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(14),
      background: color.withValues(alpha: 0.1),
      borderColor: color.withValues(alpha: 0.24),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: AppTextStyles.body.copyWith(color: AppColors.ink2),
            ),
          ),
        ],
      ),
    );
  }
}

Object? _pickField(Map<String, Object?> fields, List<String> keys) {
  for (final key in keys) {
    final value = fields[key];
    if (value != null && '$value'.isNotEmpty) return value;
  }
  return null;
}

String _formatValue(Object? value) {
  if (value == null) return '-';
  if (value is List) return value.map(_formatValue).join('、');
  if (value is Map) {
    return value.entries.map((e) => '${e.key}:${e.value}').join('、');
  }
  return '$value';
}

String _formatFieldValue(String key, Object? value) {
  if (key == 'record_type') return _recordTypeLabel(value);
  if (key.endsWith('_date') || key.endsWith('_at')) {
    return _formatDate(value);
  }
  return _formatValue(value);
}

String _sceneLabel(String scene) {
  return switch (scene.trim().toLowerCase()) {
    'ledger.record' || 'cost.record' => '记账记录',
    'debt.record' => '赊账记录',
    'farm.log' || 'log.record' => '农事记录',
    'work_order.create' => '作业单',
    'wage.record' || 'labor.wage' => '工资记录',
    '' => '待确认记录',
    _ => '待确认记录',
  };
}

String _fieldLabel(String key) {
  return switch (key) {
    'record_type' => '类型',
    'category' => '分类',
    'amount' => '金额',
    'record_date' => '日期',
    'note' => '备注',
    'record_subtype' => '子类',
    'counterparty' => '对象',
    'due_date' => '到期日',
    'created_at' => '创建时间',
    'operation_type' => '作业类型',
    'work_date' => '作业日期',
    'name' => '名称',
    _ => key,
  };
}

String _recordTypeLabel(Object? value) {
  return switch ('${value ?? ''}'.trim().toLowerCase()) {
    'cost' => '支出',
    'income' => '收入',
    'debt' => '欠款',
    'daily' => '日常',
    '' => '-',
    _ => _formatValue(value),
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
