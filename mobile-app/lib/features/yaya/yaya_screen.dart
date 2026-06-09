import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

part 'yaya_panel_widgets.dart';
part 'yaya_robot_widgets.dart';

class YayaScreen extends StatefulWidget {
  const YayaScreen({super.key});

  @override
  State<YayaScreen> createState() => _YayaScreenState();
}

class _YayaScreenState extends State<YayaScreen> {
  bool drawerOpen = false;

  void _openDrawer() => setState(() => drawerOpen = true);

  void _closeDrawer() => setState(() => drawerOpen = false);

  void _openSkills() {
    _closeDrawer();
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const YayaSkillsPage(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final drawerWidth = constraints.maxWidth * 0.8;
        return Stack(
          fit: StackFit.expand,
          children: [
            SafeArea(
              child: _YayaHomePage(
                onMenuPressed: _openDrawer,
                onSkillsPressed: _openSkills,
              ),
            ),
            if (drawerOpen) ...[
              Positioned.fill(
                child: Row(
                  children: [
                    SizedBox(width: drawerWidth),
                    Expanded(
                      child: GestureDetector(
                        onTap: _closeDrawer,
                        behavior: HitTestBehavior.opaque,
                        child: ClipRect(
                          child: BackdropFilter(
                            filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                            child: Container(
                              color: AppColors.ink.withValues(alpha: 0.18),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              AnimatedPositioned(
                duration: const Duration(milliseconds: 260),
                curve: Curves.easeOutCubic,
                left: 0,
                top: 0,
                bottom: 0,
                width: drawerWidth,
                child: YayaHistoryDrawer(
                  onClose: _closeDrawer,
                  onSkillsPressed: _openSkills,
                ),
              ),
            ],
          ],
        );
      },
    );
  }
}

class _YayaHomePage extends StatelessWidget {
  const _YayaHomePage({
    required this.onMenuPressed,
    required this.onSkillsPressed,
  });

  final VoidCallback onMenuPressed;
  final VoidCallback onSkillsPressed;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        Positioned.fill(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 164),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 430),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _YayaHeader(onMenuPressed: onMenuPressed),
                    const SizedBox(height: 64),
                    const _YayaHero(),
                    const SizedBox(height: 28),
                    const _SuggestionPills(),
                  ],
                ),
              ),
            ),
          ),
        ),
        Positioned(
          left: 20,
          right: 20,
          bottom: 14,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 430),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _ModeChips(onSkillsPressed: onSkillsPressed),
                  const SizedBox(height: 10),
                  const AssistantInputBar(),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _YayaHeader extends StatelessWidget {
  const _YayaHeader({required this.onMenuPressed});

  final VoidCallback onMenuPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 64,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: _HeaderIconButton(
              icon: LucideIcons.menu,
              onPressed: onMenuPressed,
            ),
          ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const FarmBrandMark(size: 30),
              const SizedBox(width: 8),
              Text(
                '农场管家',
                style: AppTextStyles.title.copyWith(fontSize: 18),
              ),
            ],
          ),
          const Align(
            alignment: Alignment.centerRight,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _HeaderIconButton(icon: LucideIcons.volume2),
                SizedBox(width: 2),
                _HeaderIconButton(icon: LucideIcons.plus),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _YayaHero extends StatelessWidget {
  const _YayaHero();

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const SizedBox(width: 8),
        const YayaMascot(size: 118),
        const SizedBox(width: 20),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text.rich(
                TextSpan(
                  text: '周末愉快，我是',
                  children: [
                    TextSpan(
                      text: '芽芽',
                      style: AppTextStyles.title.copyWith(
                        color: AppColors.blue,
                        fontSize: 24,
                      ),
                    ),
                  ],
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.title.copyWith(fontSize: 24),
              ),
              const SizedBox(height: 10),
              Text(
                '有问题，直接问我',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.body.copyWith(
                  color: AppColors.muted,
                  fontSize: 15,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class YayaSkillsPage extends StatelessWidget {
  const YayaSkillsPage({super.key});

  static const _recommendedCards = [
    _SkillSpec(
      icon: LucideIcons.notebookText,
      title: '今日简报',
      subtitle: '查看今天待办与风险',
      color: AppColors.blue,
      background: AppColors.blueSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.walletCards,
      title: '智能记账',
      subtitle: '一句话生成账本记录',
      color: AppColors.greenDark,
      background: AppColors.greenSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.clipboardPenLine,
      title: '农事记录',
      subtitle: '记录作业与备注',
      color: AppColors.amber,
      background: AppColors.amberSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.handCoins,
      title: '工资结算',
      subtitle: '生成工人工资记录',
      color: AppColors.purple,
      background: AppColors.purpleSoft,
    ),
  ];

  static const _listSkills = [
    _SkillSpec(
      icon: LucideIcons.layers3,
      title: '批次管理',
      subtitle: '创建和更新种植批次',
      color: AppColors.blue,
      background: AppColors.blueSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.chartPie,
      title: '成本分析',
      subtitle: '看本月收支变化',
      color: AppColors.greenDark,
      background: AppColors.greenSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.fileChartColumn,
      title: '生成报告',
      subtitle: '自动生成经营周报',
      color: AppColors.purple,
      background: AppColors.purpleSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.cloudSun,
      title: '天气提醒',
      subtitle: '查看天气和风险',
      color: AppColors.amber,
      background: AppColors.amberSoft,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 430),
            child: CustomScrollView(
              slivers: [
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 0),
                  sliver: SliverToBoxAdapter(
                    child: _SkillsHeader(
                      onBack: () => Navigator.of(context).maybePop(),
                    ),
                  ),
                ),
                const SliverPadding(
                  padding: EdgeInsets.fromLTRB(20, 12, 20, 0),
                  sliver: SliverToBoxAdapter(child: _SkillsSearchBox()),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
                  sliver: SliverToBoxAdapter(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(20),
                      child: Image.asset(
                        AppAssets.yayaSkillsBanner,
                        key: const ValueKey('yaya-skills-banner'),
                        height: 160,
                        width: double.infinity,
                        fit: BoxFit.cover,
                      ),
                    ),
                  ),
                ),
                const SliverPadding(
                  padding: EdgeInsets.fromLTRB(20, 18, 20, 0),
                  sliver: SliverToBoxAdapter(child: _SkillCategoryChips()),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
                  sliver: SliverGrid.builder(
                    itemCount: _recommendedCards.length,
                    gridDelegate:
                        const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                      childAspectRatio: 1.38,
                    ),
                    itemBuilder: (context, index) => _SkillCard(
                      spec: _recommendedCards[index],
                    ),
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 120),
                  sliver: SliverToBoxAdapter(
                    child: _RecommendedSkillList(skills: _listSkills),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SkillsHeader extends StatelessWidget {
  const _SkillsHeader({required this.onBack});

  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 64,
      child: Row(
        children: [
          _HeaderIconButton(
            icon: LucideIcons.arrowLeft,
            onPressed: onBack,
          ),
          Expanded(
            child: Text(
              '全部技能',
              textAlign: TextAlign.center,
              style: AppTextStyles.title.copyWith(fontSize: 20),
            ),
          ),
          const SizedBox(width: 44),
        ],
      ),
    );
  }
}

class _SkillsSearchBox extends StatelessWidget {
  const _SkillsSearchBox();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 52,
      padding: const EdgeInsets.symmetric(horizontal: 17),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(26),
        border: Border.all(color: AppColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x08000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        children: [
          const Icon(LucideIcons.search, size: 20, color: AppColors.subtle),
          const SizedBox(width: 10),
          Text(
            '搜索技能',
            style: AppTextStyles.body.copyWith(color: AppColors.subtle),
          ),
        ],
      ),
    );
  }
}

class _SkillCategoryChips extends StatelessWidget {
  const _SkillCategoryChips();

  @override
  Widget build(BuildContext context) {
    const labels = ['推荐', '记录', '经营', '生产', '设置'];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (var index = 0; index < labels.length; index++) ...[
            _CategoryChip(label: labels[index], selected: index == 0),
            if (index != labels.length - 1) const SizedBox(width: 10),
          ],
        ],
      ),
    );
  }
}

class _CategoryChip extends StatelessWidget {
  const _CategoryChip({required this.label, this.selected = false});

  final String label;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 38,
      constraints: const BoxConstraints(minWidth: 58),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: selected ? AppColors.blue : AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: selected ? AppColors.blue : AppColors.line),
      ),
      child: Text(
        label,
        style: AppTextStyles.body.copyWith(
          color: selected ? Colors.white : AppColors.muted,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _HeaderIconButton extends StatelessWidget {
  const _HeaderIconButton({
    required this.icon,
    this.onPressed,
  });

  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 44,
      height: 44,
      child: IconButton(
        onPressed: onPressed,
        icon: Icon(icon),
        iconSize: 22,
        color: AppColors.ink,
        padding: EdgeInsets.zero,
        splashRadius: 22,
      ),
    );
  }
}

class YayaHistoryDrawer extends StatelessWidget {
  const YayaHistoryDrawer({
    super.key,
    required this.onClose,
    required this.onSkillsPressed,
  });

  final VoidCallback onClose;
  final VoidCallback onSkillsPressed;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: Container(
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.only(
            topRight: Radius.circular(28),
            bottomRight: Radius.circular(28),
          ),
          boxShadow: [
            BoxShadow(
              color: Color(0x1A111827),
              blurRadius: 28,
              offset: Offset(10, 0),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: const BorderRadius.only(
            topRight: Radius.circular(28),
            bottomRight: Radius.circular(28),
          ),
          child: Column(
            children: [
              _DrawerHeader(onClose: onClose),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(18, 12, 18, 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const _NewChatCard(),
                      const SizedBox(height: 12),
                      _DrawerSkillEntry(onTap: onSkillsPressed),
                      const SizedBox(height: 22),
                      const _RecentChatHeader(),
                      const SizedBox(height: 14),
                      const _ChatSection(
                        title: '今天',
                        items: [
                          _ChatItemSpec('今天适合干什么', '09:42', '天气建议', true),
                          _ChatItemSpec('本月成本怎么看', '08:16', '经营分析', false),
                        ],
                      ),
                      const SizedBox(height: 18),
                      const _ChatSection(
                        title: '7天内',
                        items: [
                          _ChatItemSpec('春茬西瓜授粉安排', '周五', '生产', false),
                          _ChatItemSpec('人工工资怎么结', '周三', '工资', false),
                          _ChatItemSpec('欠款风险提醒', '周二', '风险', false),
                        ],
                      ),
                      const SizedBox(height: 18),
                      const _ChatSection(
                        title: '30天内',
                        items: [
                          _ChatItemSpec('生成5月周报', '5月28日', '报告', false),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const _DrawerUserBar(),
            ],
          ),
        ),
      ),
    );
  }
}

class _DrawerHeader extends StatelessWidget {
  const _DrawerHeader({required this.onClose});

  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 10, 12, 4),
      child: SizedBox(
        height: 58,
        child: Row(
          children: [
            _HeaderIconButton(icon: LucideIcons.menu, onPressed: onClose),
            const SizedBox(width: 6),
            const YayaMascot(size: 34),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '芽芽',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.sectionTitle.copyWith(fontSize: 17),
                  ),
                  Row(
                    children: [
                      Container(
                        width: 7,
                        height: 7,
                        decoration: const BoxDecoration(
                          color: AppColors.green,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 5),
                      Text(
                        '在线',
                        style: AppTextStyles.small.copyWith(
                          color: AppColors.muted,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const _HeaderIconButton(icon: LucideIcons.search),
            const _HeaderIconButton(icon: LucideIcons.squarePen),
          ],
        ),
      ),
    );
  }
}

class _NewChatCard extends StatelessWidget {
  const _NewChatCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 92,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF1473FF), Color(0xFF35C879)],
        ),
        borderRadius: BorderRadius.circular(22),
        boxShadow: const [
          BoxShadow(
            color: Color(0x1A1473FF),
            blurRadius: 22,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(16),
            ),
            child: const Icon(LucideIcons.plus, color: Colors.white, size: 24),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '新对话',
                  style: AppTextStyles.sectionTitle.copyWith(
                    color: Colors.white,
                    fontSize: 17,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '让芽芽帮你分析农场问题',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.small.copyWith(
                    color: Colors.white.withValues(alpha: 0.84),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
