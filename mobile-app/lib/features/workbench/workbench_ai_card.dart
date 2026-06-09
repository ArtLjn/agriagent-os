part of 'workbench_screen.dart';

class _AiGeneratedCard extends StatelessWidget {
  const _AiGeneratedCard({required this.onEdit, required this.onSave});

  final VoidCallback onEdit;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(LucideIcons.sparkles, size: 24, color: AppColors.blue),
              const SizedBox(width: 8),
              const Expanded(
                child: Text('AI待确认', style: AppTextStyles.sectionTitle),
              ),
              const StatusPill(
                text: '待确认',
                color: AppColors.purple,
                background: AppColors.purpleSoft,
              ),
            ],
          ),
          const SizedBox(height: 8),
          const _AiRecordField(
            icon: LucideIcons.fileText,
            label: '入口',
            value: '智能识别',
          ),
          const SizedBox(height: 6),
          const _AiRecordField(
            icon: LucideIcons.messageSquareText,
            label: '示例',
            value: '今天买饲料 3680 元',
            valueColor: AppColors.blue,
            bigValue: true,
          ),
          const SizedBox(height: 6),
          const _AiRecordField(
            icon: LucideIcons.shieldCheck,
            label: '规则',
            value: '缺字段时先确认',
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _SecondaryButton(label: '改一下', onTap: onEdit)),
              const SizedBox(width: 12),
              Expanded(child: _PrimaryButton(label: '保存', onTap: onSave)),
            ],
          ),
        ],
      ),
    );
  }
}

class _AiRecordField extends StatelessWidget {
  const _AiRecordField({
    required this.icon,
    required this.label,
    required this.value,
    this.valueColor = AppColors.ink,
    this.bigValue = false,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color valueColor;
  final bool bigValue;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        IconBadge(
          icon: icon,
          color: AppColors.blue,
          background: AppColors.blueSoft,
          size: 30,
          iconSize: 16,
        ),
        const SizedBox(width: 10),
        SizedBox(
          width: 54,
          child: Text(
            label,
            style: AppTextStyles.small.copyWith(
              color: AppColors.muted,
              fontSize: 13,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.dateTitle.copyWith(
              color: valueColor,
              fontSize: bigValue ? 20 : 16,
            ),
          ),
        ),
      ],
    );
  }
}

class _PrimaryButton extends StatelessWidget {
  const _PrimaryButton({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 40,
        decoration: BoxDecoration(
          color: AppColors.blue,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Center(
          child: Text(
            label,
            style: AppTextStyles.sectionTitle.copyWith(color: Colors.white),
          ),
        ),
      ),
    );
  }
}

class _SecondaryButton extends StatelessWidget {
  const _SecondaryButton({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 40,
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFFBCC7D6)),
        ),
        child: Center(
          child: Text(
            label,
            style: AppTextStyles.sectionTitle.copyWith(
              color: AppColors.ink2,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ),
    );
  }
}
