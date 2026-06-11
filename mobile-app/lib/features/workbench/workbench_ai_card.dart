part of 'workbench_screen.dart';

class _AiGeneratedCard extends StatelessWidget {
  const _AiGeneratedCard({required this.onEdit, required this.onSave});

  final VoidCallback onEdit;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      radius: 20,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Image.asset(
                AppAssets.recordAiSparkle,
                width: 28,
                height: 28,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => const Icon(
                  LucideIcons.sparkles,
                  size: 24,
                  color: AppColors.blue,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'AI待确认',
                  style: AppTextStyles.sectionTitle.copyWith(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppColors.ink2,
                  ),
                ),
              ),
              const StatusPill(
                text: '待确认',
                color: AppColors.purple,
                background: AppColors.purpleSoft,
              ),
            ],
          ),
          const SizedBox(height: 10),
          const _AiRecordField(
            icon: LucideIcons.fileText,
            label: '内容',
            value: '饲料采购',
          ),
          const SizedBox(height: 5),
          const _AiRecordField(
            icon: LucideIcons.badgeJapaneseYen,
            label: '金额',
            value: '¥3,680',
            valueColor: AppColors.blue,
            bigValue: true,
          ),
          const SizedBox(height: 5),
          const _AiRecordField(
            icon: LucideIcons.store,
            label: '供应商',
            value: 'XX饲料厂',
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
    this.valueColor = AppColors.ink2,
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
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: AppColors.blueSoft,
            borderRadius: BorderRadius.circular(11),
          ),
          child: Icon(
            icon,
            color: AppColors.blue,
            size: 17,
          ),
        ),
        const SizedBox(width: 12),
        SizedBox(
          width: 58,
          child: Text(
            label,
            style: AppTextStyles.small.copyWith(
              color: AppColors.muted,
              fontSize: 14,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: bigValue ? valueColor : AppColors.ink2,
              fontSize: bigValue ? 20 : 15.5,
              height: bigValue ? 26 / 20 : 22 / 15.5,
              fontWeight: bigValue ? FontWeight.w600 : FontWeight.w500,
              letterSpacing: 0,
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
        height: 44,
        decoration: BoxDecoration(
          color: AppColors.blue,
          borderRadius: BorderRadius.circular(15),
          boxShadow: const [
            BoxShadow(
              color: Color(0x1F1477FF),
              blurRadius: 12,
              offset: Offset(0, 5),
            ),
          ],
        ),
        child: Center(
          child: Text(
            label,
            style: AppTextStyles.sectionTitle.copyWith(
              color: Colors.white,
              fontSize: 15.5,
              fontWeight: FontWeight.w600,
            ),
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
        height: 44,
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: AppColors.blue),
        ),
        child: Center(
          child: Text(
            label,
            style: AppTextStyles.sectionTitle.copyWith(
              color: AppColors.blueDark,
              fontSize: 15.5,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ),
    );
  }
}
