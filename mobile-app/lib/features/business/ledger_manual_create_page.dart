import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/repositories/business_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../theme/app_colors.dart';
import 'business_ui.dart';

class LedgerManualCreatePage extends StatefulWidget {
  const LedgerManualCreatePage({
    super.key,
    required this.repository,
    this.onBottomTabChanged,
  });

  static const routePath = '/ledger-manual-create';

  final BusinessRepository repository;
  final ValueChanged<int>? onBottomTabChanged;

  @override
  State<LedgerManualCreatePage> createState() => _LedgerManualCreatePageState();
}

class _LedgerManualCreatePageState extends State<LedgerManualCreatePage> {
  final _category = TextEditingController(text: '饲料');
  final _amount = TextEditingController(text: '¥3,680');
  final _date = TextEditingController(text: '今天 2026-06-09');
  final _cycle = TextEditingController(text: '西瓜春茬');
  final _counterparty = TextEditingController(text: 'XX饲料厂');
  final _note = TextEditingController(text: '买饲料');
  String _recordType = 'cost';
  String _settlement = 'paid';
  bool _saving = false;

  @override
  void dispose() {
    _category.dispose();
    _amount.dispose();
    _date.dispose();
    _cycle.dispose();
    _counterparty.dispose();
    _note.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    final amountText = _amount.text.replaceAll(RegExp(r'[^0-9.]'), '');
    final dateText = _date.text.replaceFirst('今天 ', '').trim();
    try {
      await widget.repository.createLedgerRecord({
        'record_type': _recordType,
        'category': _category.text.trim(),
        'amount': num.tryParse(amountText) ?? amountText,
        'record_date': dateText,
        'record_subtype': _settlement,
        'counterparty': _counterparty.text.trim(),
        'note': _note.text.trim(),
      }..removeWhere((_, value) => value == null || value == ''));
      _showMessage('保存记录成功');
    } catch (_) {
      _showMessage('保存失败，请稍后再试');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return BusinessPageFrame(
      title: '记账',
      trailingIcon: LucideIcons.history,
      bottomBar: BottomActions(
        secondaryLabel: '取消',
        primaryLabel: _saving ? '保存中' : '保存记录',
        onPrimary: _save,
        showTabs: true,
        onBottomTabChanged: widget.onBottomTabChanged,
      ),
      children: [
        const BusinessHeroBanner(
          title: '手动记账',
          subtitle: '记录收支明细，保存后同步到账本',
          asset: AppAssets.businessLedgerBlueBanner,
          accent: businessBlue,
          tags: ['今日', '可追溯', '按茬口归集'],
          metric: '¥3,680',
        ),
        FormRowsCard(
          title: '记录类型',
          icon: LucideIcons.walletCards,
          children: [
            SegmentedFormRow(
              label: '类型',
              options: const {'cost': '支出', 'income': '收入'},
              value: _recordType,
              onChanged: (value) => setState(() => _recordType = value),
            ),
            BusinessFormRow(
              label: '分类',
              value: '饲料',
              controller: _category,
              chevron: true,
            ),
            BusinessFormRow(
              label: '金额',
              value: '¥3,680',
              controller: _amount,
              large: true,
              keyboardType: TextInputType.number,
            ),
            BusinessFormRow(
              label: '日期',
              value: '今天 2026-06-09',
              controller: _date,
              chevron: true,
            ),
            BusinessFormRow(
              label: '关联茬口',
              value: '西瓜春茬',
              controller: _cycle,
              chevron: true,
            ),
            BusinessFormRow(
              label: '供应商',
              value: 'XX饲料厂',
              controller: _counterparty,
              chevron: true,
            ),
            SegmentedFormRow(
              label: '结算状态',
              options: const {'paid': '已付', 'debt': '赊账'},
              value: _settlement,
              onChanged: (value) => setState(() => _settlement = value),
            ),
            BusinessFormRow(
              label: '备注',
              value: '买饲料',
              controller: _note,
              chevron: true,
            ),
          ],
        ),
        const AssistEntryCard(text: '可用一句话智能填写'),
        const SizedBox(height: 8),
        const _LedgerHintCard(),
      ],
    );
  }
}

class _LedgerHintCard extends StatelessWidget {
  const _LedgerHintCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.greenSoft,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.green.withValues(alpha: 0.16)),
      ),
      child: const Row(
        children: [
          Icon(LucideIcons.circleCheckBig,
              color: AppColors.greenDark, size: 20),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              '手动保存直接调用 /costs，不会假装走未支持的 AI 落库。',
              style: TextStyle(
                color: AppColors.greenDark,
                fontSize: 13,
                height: 18 / 13,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
