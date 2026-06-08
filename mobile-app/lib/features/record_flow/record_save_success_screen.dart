import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'record_flow_widgets.dart';

class RecordSaveSuccessScreen extends StatelessWidget {
  const RecordSaveSuccessScreen({
    super.key,
    this.onGoHome,
    this.onGoLedger,
    this.onRecordAgain,
  });

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
          '已同步到账本和最近记录',
          textAlign: TextAlign.center,
          style: AppTextStyles.body.copyWith(
            color: AppColors.muted,
            fontSize: 14,
          ),
        ),
        const SizedBox(height: 20),
        const SuccessSummaryCard(),
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
