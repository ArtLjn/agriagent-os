part of 'yaya_screen.dart';

class YayaMascot extends StatelessWidget {
  const YayaMascot({super.key, required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: AppColors.surface,
        boxShadow: [
          BoxShadow(
            color: AppColors.blue.withValues(alpha: 0.08),
            blurRadius: size * 0.22,
            offset: Offset(0, size * 0.08),
          ),
        ],
      ),
      child: ClipOval(
        child: Image.asset(
          AppAssets.yayaMascotLogo,
          fit: BoxFit.cover,
        ),
      ),
    );
  }
}
