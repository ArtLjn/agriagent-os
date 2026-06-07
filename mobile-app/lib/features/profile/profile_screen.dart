import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/section_heading.dart';
import '../../shared/widgets/status_header.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Column(
        children: [
          const StatusHeader(
            title: '我的',
            subtitle: '账号、农场、偏好与服务',
            trailingIcon: LucideIcons.settings,
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 112),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ProfileTopCard(),
                  SizedBox(height: 14),
                  ProfileListCard(
                    title: '常用设置',
                    rows: [
                      ProfileRowSpec(
                        LucideIcons.building2,
                        AppColors.blue,
                        AppColors.blueSoft,
                        '账号与农场资料',
                        '昵称、手机号、农场信息',
                      ),
                      ProfileRowSpec(
                        LucideIcons.bot,
                        AppColors.teal,
                        AppColors.tealSoft,
                        '芽芽偏好',
                        '提醒频率、语气、默认作物',
                      ),
                      ProfileRowSpec(
                        LucideIcons.bell,
                        AppColors.cyan,
                        AppColors.cyanSoft,
                        '消息提醒',
                        '天气、作业、账单提醒',
                      ),
                      ProfileRowSpec(
                        LucideIcons.shieldCheck,
                        AppColors.green,
                        AppColors.greenSoft,
                        '账号安全',
                        '登录保护、成员权限',
                      ),
                    ],
                  ),
                  SizedBox(height: 14),
                  ProfileListCard(
                    title: '帮助与系统',
                    rows: [
                      ProfileRowSpec(
                        LucideIcons.circleHelp,
                        AppColors.amber,
                        AppColors.amberSoft,
                        '帮助中心',
                        '常见问题与操作指南',
                      ),
                      ProfileRowSpec(
                        LucideIcons.download,
                        AppColors.blue,
                        AppColors.blueSoft,
                        '版本信息',
                        '当前版本 1.0.0',
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ProfileTopCard extends StatelessWidget {
  const ProfileTopCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const CardPanel(
      padding: EdgeInsets.all(18),
      child: Column(
        children: [
          Row(
            children: [
              ProfileAvatar(),
              SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '刘文洁的农场',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                      color: AppColors.ink,
                      letterSpacing: 0,
                    ),
                  ),
                  SizedBox(height: 5),
                  Row(
                    children: [
                      Text('经营者', style: AppTextStyles.small),
                      Text(' · 2 个农场 · 12 个成员', style: AppTextStyles.small),
                    ],
                  ),
                ],
              ),
            ],
          ),
          SizedBox(height: 16),
          Row(
            children: [
              ProfileStat(value: '14 天', label: '芽芽连续运行'),
              SizedBox(width: 8),
              ProfileStat(value: '12', label: '成员'),
              SizedBox(width: 8),
              ProfileStat(value: '2', label: '农场'),
            ],
          ),
        ],
      ),
    );
  }
}

class ProfileAvatar extends StatelessWidget {
  const ProfileAvatar({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        color: AppColors.navy,
        borderRadius: BorderRadius.circular(18),
      ),
      child: const Center(
        child: Text(
          'L',
          style: TextStyle(
            color: Colors.white,
            fontSize: 22,
            fontWeight: FontWeight.w800,
            letterSpacing: 0,
          ),
        ),
      ),
    );
  }
}

class ProfileStat extends StatelessWidget {
  const ProfileStat({super.key, required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: AppColors.surface2,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w800,
                color: AppColors.ink,
                letterSpacing: 0,
              ),
            ),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.small.copyWith(fontSize: 10),
            ),
          ],
        ),
      ),
    );
  }
}

class ProfileListCard extends StatelessWidget {
  const ProfileListCard({super.key, required this.title, required this.rows});

  final String title;
  final List<ProfileRowSpec> rows;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeading(title: title),
          const SizedBox(height: 12),
          ...rows.indexed.map((entry) {
            final row = ProfileRow(row: entry.$2);
            if (entry.$1 == rows.length - 1) return row;
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: row,
            );
          }),
        ],
      ),
    );
  }
}

class ProfileRow extends StatelessWidget {
  const ProfileRow({super.key, required this.row});

  final ProfileRowSpec row;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: row.background,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(row.icon, size: 18, color: row.color),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                row.title,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink,
                  letterSpacing: 0,
                ),
              ),
              Text(row.subtitle, style: AppTextStyles.small),
            ],
          ),
        ),
      ],
    );
  }
}

class ProfileRowSpec {
  const ProfileRowSpec(
    this.icon,
    this.color,
    this.background,
    this.title,
    this.subtitle,
  );

  final IconData icon;
  final Color color;
  final Color background;
  final String title;
  final String subtitle;
}
