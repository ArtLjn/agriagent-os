import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../theme/app_colors.dart';
import 'record_flow_widgets.dart';
import 'record_save_success_screen.dart';

class RecordManualEditScreen extends StatelessWidget {
  const RecordManualEditScreen({
    super.key,
    this.onGoHome,
    this.onGoLedger,
    this.onRecordAgain,
  });

  final VoidCallback? onGoHome;
  final VoidCallback? onGoLedger;
  final VoidCallback? onRecordAgain;

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
      title: '改一下',
      subtitle: '哪里不对，点哪里改',
      bottomPadding: 150,
      bottomBar: StickyActionBar(
        children: [
          Expanded(
            child: FlowButton(
              label: '保存修改',
              icon: LucideIcons.circleCheckBig,
              onTap: () => _openSuccess(context),
            ),
          ),
        ],
      ),
      children: const [
        ContextPill(),
        SegmentedRecordType(),
        SizedBox(height: 12),
        EditSectionCard(
          title: '金额与分类',
          icon: LucideIcons.circleDollarSign,
          children: [AmountCategoryEditor()],
        ),
        SizedBox(height: 12),
        EditSectionCard(
          title: '时间与归属',
          icon: LucideIcons.calendarDays,
          children: [
            Row(
              children: [
                Expanded(
                  child: EditablePillRow(
                    label: '今天',
                    icon: LucideIcons.calendar,
                  ),
                ),
                SizedBox(width: 10),
                Expanded(
                  child: EditablePillRow(
                    label: '5月第2批次',
                    icon: LucideIcons.tag,
                  ),
                ),
              ],
            ),
          ],
        ),
        SizedBox(height: 12),
        EditSectionCard(
          title: '付款方式',
          icon: LucideIcons.creditCard,
          children: [
            Row(
              children: [
                Expanded(
                  child: PaymentOption(
                    label: '现金',
                    icon: LucideIcons.banknote,
                    color: AppColors.blue,
                    selected: true,
                  ),
                ),
                SizedBox(width: 8),
                Expanded(
                  child: PaymentOption(
                    label: '微信',
                    icon: LucideIcons.messageCircle,
                    color: AppColors.greenDark,
                  ),
                ),
                SizedBox(width: 8),
                Expanded(
                  child: PaymentOption(
                    label: '赊账',
                    icon: LucideIcons.receipt,
                    color: AppColors.amber,
                  ),
                ),
              ],
            ),
            SizedBox(height: 14),
            Text(
              '备注',
              style: TextStyle(
                color: AppColors.ink,
                fontSize: 15,
                height: 21 / 15,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
            ),
            SizedBox(height: 8),
            EditablePillRow(
              label: '饲料采购',
              icon: LucideIcons.pencil,
              color: AppColors.blue,
            ),
          ],
        ),
      ],
    );
  }
}
