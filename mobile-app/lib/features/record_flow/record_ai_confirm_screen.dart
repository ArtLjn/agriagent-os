import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import 'record_manual_edit_screen.dart';
import 'record_save_success_screen.dart';
import 'record_flow_widgets.dart';

class RecordAiConfirmScreen extends StatelessWidget {
  const RecordAiConfirmScreen({
    super.key,
    this.onGoHome,
    this.onGoLedger,
    this.onRecordAgain,
  });

  final VoidCallback? onGoHome;
  final VoidCallback? onGoLedger;
  final VoidCallback? onRecordAgain;

  void _openManualEdit(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RecordManualEditScreen(
          onGoHome: onGoHome,
          onGoLedger: onGoLedger,
          onRecordAgain: onRecordAgain,
        ),
      ),
    );
  }

  void _openSuccess(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RecordSaveSuccessScreen(
          onGoHome: onGoHome,
          onGoLedger: onGoLedger,
          onRecordAgain: onRecordAgain,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return FlowScaffold(
      title: '智能确认',
      centerTitle: true,
      bottomBar: StickyActionBar(
        children: [
          Expanded(
            child: FlowButton(
              label: '改一下',
              primary: false,
              onTap: () => _openManualEdit(context),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: FlowButton(
              label: '确认保存',
              onTap: () => _openSuccess(context),
            ),
          ),
        ],
      ),
      children: const [
        StepIndicator(),
        HeroUnderstandingCard(),
        SizedBox(height: 14),
        OriginalTextCard(),
        SizedBox(height: 14),
        FieldGroupCard(
          title: '账务信息',
          icon: LucideIcons.receiptText,
          color: AppColors.blue,
          background: AppColors.blueSoft,
          rows: [
            FieldValueRow(label: '分类', value: '饲料采购'),
            FieldValueRow(label: '金额', value: '¥3,680.00'),
            FieldValueRow(label: '付款', value: '现金'),
          ],
        ),
        SizedBox(height: 14),
        FieldGroupCard(
          title: '关联信息',
          icon: LucideIcons.link,
          color: AppColors.greenDark,
          background: AppColors.greenSoft,
          rows: [
            FieldValueRow(label: '批次', value: '5月第2批次'),
            FieldValueRow(label: '日期', value: '今天'),
            FieldValueRow(label: '备注', value: '饲料采购'),
          ],
        ),
        SizedBox(height: 14),
        FlowHintCard(text: '不确定？点字段可以修改'),
      ],
    );
  }
}
