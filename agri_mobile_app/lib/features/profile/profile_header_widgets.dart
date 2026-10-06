part of 'profile_screen.dart';

class _ProfileCard extends StatelessWidget {
  const _ProfileCard({required this.model});
  final ProfileViewModel model;

  @override
  Widget build(BuildContext context) {
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      CircleAvatar(
        radius: 32,
        backgroundColor: AppColors.blueSoft,
        child: Text(
            model.nickname.isEmpty ? '农' : model.nickname.characters.first,
            style: AppTextStyles.title
                .copyWith(color: AppColors.blue, fontSize: 28)),
      ),
      const SizedBox(width: 20),
      Expanded(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(model.nickname, style: AppTextStyles.title.copyWith(fontSize: 24)),
        const SizedBox(height: 8),
        Text(model.phone,
            style: AppTextStyles.body.copyWith(color: AppColors.muted)),
        const SizedBox(height: 12),
        Wrap(
            spacing: 8,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(model.role, style: AppTextStyles.small),
              const Text('·', style: AppTextStyles.small),
              Text(model.status,
                  style: AppTextStyles.small.copyWith(
                      color: model.status == '正常'
                          ? AppColors.greenDark
                          : AppColors.muted)),
            ]),
      ])),
    ]);
  }
}
