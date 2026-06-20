import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/profile_repository.dart';
import '../../data/repositories/yaya_repository.dart';
import '../../shared/assets/app_assets.dart';
import '../../shared/widgets/reference_page.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'yaya_controller.dart';

part 'yaya_panel_widgets.dart';
part 'yaya_robot_widgets.dart';

class YayaScreen extends StatefulWidget {
  const YayaScreen({
    super.key,
    required this.repository,
    this.profileRepository,
  });

  final YayaRepository repository;
  final ProfileRepository? profileRepository;

  @override
  State<YayaScreen> createState() => _YayaScreenState();
}

class _YayaScreenState extends State<YayaScreen> {
  late final YayaController controller =
      YayaController(repository: widget.repository);
  bool drawerOpen = false;
  String userNickname = '农友';

  void _openDrawer() => setState(() => drawerOpen = true);

  void _closeDrawer() => setState(() => drawerOpen = false);

  void _openSkills() {
    _closeDrawer();
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => YayaSkillsPage(repository: widget.repository),
      ),
    );
  }

  void _startNewConversation() {
    _closeDrawer();
    controller.startNewConversation();
  }

  @override
  void initState() {
    super.initState();
    controller.loadConversations().catchError((Object _) {});
    _loadUserNickname();
  }

  Future<void> _loadUserNickname() async {
    final profileRepository = widget.profileRepository;
    if (profileRepository == null) return;
    try {
      final user = await profileRepository.getProfile();
      final nickname = user.nickname.trim();
      if (!mounted || nickname.isEmpty) return;
      setState(() => userNickname = nickname);
    } catch (_) {
      // 芽芽页不能因为资料接口失败影响聊天主流程。
    }
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        return LayoutBuilder(
          builder: (context, constraints) {
            final drawerWidth = constraints.maxWidth * 0.8;
            return Stack(
              fit: StackFit.expand,
              children: [
                SafeArea(
                  child: _YayaHomePage(
                    controller: controller,
                    onMenuPressed: _openDrawer,
                    onSkillsPressed: _openSkills,
                    onNewConversationPressed: _startNewConversation,
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
                                filter:
                                    ImageFilter.blur(sigmaX: 10, sigmaY: 10),
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
                      conversations: controller.conversations,
                      userNickname: userNickname,
                      onConversationTap: (sessionId) {
                        _closeDrawer();
                        controller.openConversation(sessionId);
                      },
                      onNewConversationTap: _startNewConversation,
                    ),
                  ),
                ],
              ],
            );
          },
        );
      },
    );
  }
}

class _YayaHomePage extends StatelessWidget {
  const _YayaHomePage({
    required this.controller,
    required this.onMenuPressed,
    required this.onSkillsPressed,
    required this.onNewConversationPressed,
  });

  final YayaController controller;
  final VoidCallback onMenuPressed;
  final VoidCallback onSkillsPressed;
  final VoidCallback onNewConversationPressed;

  @override
  Widget build(BuildContext context) {
    final hasMessages = controller.messages.isNotEmpty;
    return Stack(
      fit: StackFit.expand,
      children: [
        Positioned.fill(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 156),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 430),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _YayaHeader(
                      onMenuPressed: onMenuPressed,
                      onNewConversationPressed: onNewConversationPressed,
                    ),
                    if (hasMessages) ...[
                      const SizedBox(height: 18),
                      _MessageList(
                        messages: controller.messages,
                        errorMessage: controller.errorMessage,
                        onPendingAction: controller.respondToPendingAction,
                      ),
                    ] else ...[
                      const SizedBox(height: 54),
                      const _YayaHero(),
                      const SizedBox(height: 26),
                      _SuggestionPills(onSelected: controller.send),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: Container(
            color: AppColors.background,
            padding: const EdgeInsets.fromLTRB(8, 10, 8, 12),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _ModeChips(
                  onSelected: controller.send,
                  onSkillsPressed: onSkillsPressed,
                ),
                const SizedBox(height: 8),
                AssistantInputBar(
                  sending: controller.sending,
                  onSubmit: controller.send,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _MessageList extends StatelessWidget {
  const _MessageList({
    required this.messages,
    required this.errorMessage,
    required this.onPendingAction,
  });

  final List<YayaMessageViewModel> messages;
  final String? errorMessage;
  final ValueChanged<String> onPendingAction;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final message in messages) ...[
          _MessageBubble(
            message: message,
            onPendingAction: onPendingAction,
          ),
          const SizedBox(height: 12),
        ],
        if (errorMessage != null) _ErrorBanner(message: errorMessage!),
      ],
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({
    required this.message,
    required this.onPendingAction,
  });

  final YayaMessageViewModel message;
  final ValueChanged<String> onPendingAction;

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    final content = message.content.isEmpty ? '芽芽正在思考...' : message.content;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 320),
        padding: const EdgeInsets.fromLTRB(14, 11, 14, 11),
        decoration: BoxDecoration(
          color: isUser ? AppColors.blue : AppColors.surface,
          borderRadius: BorderRadius.circular(18),
          border: isUser ? null : Border.all(color: AppColors.line),
          boxShadow: const [
            BoxShadow(
              color: Color(0x08000000),
              blurRadius: 16,
              offset: Offset(0, 8),
            ),
          ],
        ),
        child: isUser
            ? Text(
                content,
                style: AppTextStyles.body.copyWith(
                  color: Colors.white,
                  height: 1.45,
                ),
              )
            : Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  MarkdownBody(
                    data: content,
                    selectable: false,
                    styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context))
                        .copyWith(
                      p: AppTextStyles.body.copyWith(
                        color: AppColors.ink,
                        height: 1.45,
                      ),
                      strong: AppTextStyles.body.copyWith(
                        color: AppColors.ink,
                        fontWeight: FontWeight.w800,
                        height: 1.45,
                      ),
                      listBullet: AppTextStyles.body.copyWith(
                        color: AppColors.ink,
                        height: 1.45,
                      ),
                      blockSpacing: 6,
                      listIndent: 16,
                    ),
                  ),
                  if (message.pendingAction != null) ...[
                    const SizedBox(height: 12),
                    _PendingActionCard(
                      pendingAction: message.pendingAction!,
                      onConfirm: () => onPendingAction('确认'),
                      onCancel: () => onPendingAction('取消'),
                    ),
                  ],
                ],
              ),
      ),
    );
  }
}

class _PendingActionCard extends StatelessWidget {
  const _PendingActionCard({
    required this.pendingAction,
    required this.onConfirm,
    required this.onCancel,
  });

  final Map<String, dynamic> pendingAction;
  final VoidCallback onConfirm;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final contextData = _mapValue(pendingAction['context']);
    final originalInput = '${contextData?['original_input'] ?? ''}'.trim();
    final notes = _stringList(contextData?['notes'])
        .where((note) => originalInput.isEmpty || !note.contains(originalInput))
        .toList();
    final params = _mapValue(pendingAction['params']) ??
        _mapValue(contextData?['extracted_params']);

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 10),
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.lineSoft),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 26,
                height: 26,
                decoration: BoxDecoration(
                  color: AppColors.amberSoft,
                  borderRadius: BorderRadius.circular(9),
                ),
                child: const Icon(
                  LucideIcons.hourglass,
                  size: 15,
                  color: AppColors.amber,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '待确认执行',
                  style: AppTextStyles.body.copyWith(
                    color: AppColors.ink,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          if (originalInput.isNotEmpty || notes.isNotEmpty) ...[
            const SizedBox(height: 10),
            _PendingContextBox(
              originalInput: originalInput,
              notes: notes,
            ),
          ],
          if (params != null && params.isNotEmpty) ...[
            const SizedBox(height: 10),
            _PendingParamList(params: params),
          ],
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              _PendingActionButton(
                label: '取消',
                color: AppColors.muted,
                background: AppColors.lineSoft,
                onTap: onCancel,
              ),
              const SizedBox(width: 8),
              _PendingActionButton(
                label: '确认',
                color: Colors.white,
                background: AppColors.greenDark,
                onTap: onConfirm,
              ),
            ],
          ),
        ],
      ),
    );
  }

  static Map<String, dynamic>? _mapValue(Object? value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return Map<String, dynamic>.from(value);
    return null;
  }

  static List<String> _stringList(Object? value) {
    if (value is! List) return const [];
    return value
        .map((item) => '$item')
        .where((item) => item.isNotEmpty)
        .toList();
  }
}

class _PendingContextBox extends StatelessWidget {
  const _PendingContextBox({
    required this.originalInput,
    required this.notes,
  });

  final String originalInput;
  final List<String> notes;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 9, 10, 9),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (originalInput.isNotEmpty)
            Text(
              '理解：您说的是「$originalInput」',
              style: AppTextStyles.small.copyWith(
                color: AppColors.muted,
                height: 1.4,
              ),
            ),
          for (final note in notes)
            Padding(
              padding: EdgeInsets.only(top: originalInput.isEmpty ? 0 : 4),
              child: Text(
                note,
                style: AppTextStyles.small.copyWith(
                  color: AppColors.muted,
                  height: 1.4,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _PendingParamList extends StatelessWidget {
  const _PendingParamList({required this.params});

  final Map<String, dynamic> params;

  @override
  Widget build(BuildContext context) {
    final entries = params.entries
        .where((entry) => '${entry.value}'.trim().isNotEmpty)
        .take(4)
        .toList();
    return Column(
      children: [
        for (final entry in entries)
          Padding(
            padding: const EdgeInsets.only(bottom: 5),
            child: Row(
              children: [
                Text(
                  entry.key,
                  style: AppTextStyles.small.copyWith(color: AppColors.subtle),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '${entry.value}',
                    textAlign: TextAlign.right,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.small.copyWith(
                      color: AppColors.ink,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _PendingActionButton extends StatelessWidget {
  const _PendingActionButton({
    required this.label,
    required this.color,
    required this.background,
    required this.onTap,
  });

  final String label;
  final Color color;
  final Color background;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        height: 34,
        constraints: const BoxConstraints(minWidth: 68),
        alignment: Alignment.center,
        padding: const EdgeInsets.symmetric(horizontal: 14),
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          label,
          style: AppTextStyles.body.copyWith(
            color: color,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 2),
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
      decoration: BoxDecoration(
        color: AppColors.redSoft,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Text(
        message,
        style: AppTextStyles.body.copyWith(
          color: AppColors.red,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _YayaHeader extends StatelessWidget {
  const _YayaHeader({
    required this.onMenuPressed,
    required this.onNewConversationPressed,
  });

  final VoidCallback onMenuPressed;
  final VoidCallback onNewConversationPressed;

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
            children: const [FarmBrandLockup(height: 34)],
          ),
          Align(
            alignment: Alignment.centerRight,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const _HeaderIconButton(icon: LucideIcons.volume2),
                const SizedBox(width: 2),
                _HeaderIconButton(
                  icon: LucideIcons.plus,
                  onPressed: onNewConversationPressed,
                ),
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
    final greeting = _greetingText(DateTime.now());
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 2),
          child: YayaMascot(size: 76),
        ),
        const SizedBox(height: 22),
        Text.rich(
          TextSpan(
            text: '$greeting，我是',
            children: [
              TextSpan(
                text: '芽芽',
                style: AppTextStyles.title.copyWith(
                  color: AppColors.blue,
                  fontSize: 30,
                ),
              ),
            ],
          ),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.title.copyWith(fontSize: 30),
        ),
        const SizedBox(height: 8),
        Text(
          '有问题，直接问我',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: AppTextStyles.body.copyWith(
            color: AppColors.muted,
            fontSize: 17,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

String _greetingText(DateTime now) {
  final hour = now.hour;
  if (hour < 6) return '夜深了';
  if (hour < 11) return '早上好';
  if (hour < 14) return '中午好';
  if (hour < 18) return '下午好';
  return '晚上好';
}

class YayaSkillsPage extends StatefulWidget {
  const YayaSkillsPage({super.key, required this.repository});

  final YayaRepository repository;

  @override
  State<YayaSkillsPage> createState() => _YayaSkillsPageState();
}

class _YayaSkillsPageState extends State<YayaSkillsPage> {
  static const _categoryLabels = ['推荐', '记录', '经营', '生产', '设置'];

  static const _fallbackRecommendedCards = [
    _SkillSpec(
      icon: LucideIcons.notebookText,
      title: '今日简报',
      subtitle: '查看今天待办与风险',
      details: '获取当前农场综合状态，帮助你快速了解今天要关注的种植进度、农事记录、花费变化和天气风险。',
      examples: ['今天农场怎么样', '最近有什么风险'],
      category: '推荐',
      color: AppColors.blue,
      background: AppColors.blueSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.walletCards,
      title: '智能记账',
      subtitle: '一句话生成账本记录',
      details: '把买肥料、卖货收款、农资赊账等口语描述整理成账本记录，执行前会让你确认关键信息。',
      examples: ['买化肥花了200元', '今天卖西瓜收入3000'],
      category: '记录',
      color: AppColors.greenDark,
      background: AppColors.greenSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.clipboardPenLine,
      title: '农事记录',
      subtitle: '记录作业与备注',
      details: '把日常农活记录到对应茬口里，后续复盘生产过程、生成报告和分析投入时都能引用。',
      examples: ['今天6号棚浇水了', '记录一次打药'],
      category: '记录',
      color: AppColors.amber,
      background: AppColors.amberSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.handCoins,
      title: '工资结算',
      subtitle: '生成工人工资记录',
      details: '保存或更新独立工资记录，支持按工人、农活和金额管理未结清工资。',
      examples: ['张三今天工资120', '结清李四200元'],
      category: '记录',
      color: AppColors.purple,
      background: AppColors.purpleSoft,
    ),
  ];

  static const _fallbackListSkills = [
    _SkillSpec(
      icon: LucideIcons.layers3,
      title: '批次管理',
      subtitle: '创建和更新种植批次',
      details: '根据作物、季节、面积和地块信息创建种植批次，方便后续关联农事、账本和工人投入。',
      examples: ['春茬种西瓜', '6号棚开始种番茄'],
      category: '生产',
      color: AppColors.blue,
      background: AppColors.blueSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.chartPie,
      title: '成本分析',
      subtitle: '看本月收支变化',
      details: '分析农场收入、支出、利润和分类占比，帮助你判断哪个环节花费高。',
      examples: ['本月成本怎么看', '人工和肥料哪个花得多'],
      category: '经营',
      color: AppColors.greenDark,
      background: AppColors.greenSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.fileChartColumn,
      title: '生成报告',
      subtitle: '自动生成经营周报',
      details: '基于农事、账本和天气信息生成经营报告，方便阶段复盘。',
      examples: ['生成本周报告', '帮我总结这个月'],
      category: '经营',
      color: AppColors.purple,
      background: AppColors.purpleSoft,
    ),
    _SkillSpec(
      icon: LucideIcons.cloudSun,
      title: '天气提醒',
      subtitle: '查看天气和风险',
      details: '获取未来天气预报和灾害预警，用于安排浇水、打药、采收等对天气敏感的农事。',
      examples: ['明天适合打药吗', '最近有雨吗'],
      category: '推荐',
      color: AppColors.amber,
      background: AppColors.amberSoft,
    ),
  ];

  List<_SkillSpec> _skills = [
    ..._fallbackRecommendedCards,
    ..._fallbackListSkills,
  ];
  String _selectedCategory = '推荐';

  List<_SkillSpec> get _visibleSkills => _skills
      .where((skill) => skill.category == _selectedCategory)
      .toList(growable: false);

  @override
  void initState() {
    super.initState();
    _loadSkills();
  }

  Future<void> _loadSkills() async {
    try {
      final skills = await widget.repository.loadSkills();
      if (!mounted || skills.isEmpty) return;
      setState(() {
        _skills = skills
            .where((skill) => skill.enabled)
            .map(_skillSpecFromApi)
            .toList();
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _skills = [
          ..._fallbackRecommendedCards,
          ..._fallbackListSkills,
        ];
      });
    }
  }

  void _showSkillDetails(_SkillSpec skill) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => _SkillDetailsSheet(spec: skill),
    );
  }

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
                      child: AspectRatio(
                        aspectRatio: 2.4,
                        child: Image.asset(
                          AppAssets.yayaSkillsBanner,
                          key: const ValueKey('yaya-skills-banner'),
                          width: double.infinity,
                          fit: BoxFit.contain,
                          alignment: Alignment.center,
                        ),
                      ),
                    ),
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
                  sliver: SliverToBoxAdapter(
                    child: _SkillCategoryChips(
                      labels: _categoryLabels,
                      selected: _selectedCategory,
                      onSelected: (category) {
                        setState(() => _selectedCategory = category);
                      },
                    ),
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
                  sliver: SliverList.separated(
                    itemCount: _visibleSkills.length,
                    itemBuilder: (context, index) => _SkillCard(
                      spec: _visibleSkills[index],
                      onDetailsTap: () =>
                          _showSkillDetails(_visibleSkills[index]),
                    ),
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 12),
                  ),
                ),
                const SliverToBoxAdapter(child: SizedBox(height: 120)),
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
  const _SkillCategoryChips({
    required this.labels,
    required this.selected,
    required this.onSelected,
  });

  final List<String> labels;
  final String selected;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (var index = 0; index < labels.length; index++) ...[
            _CategoryChip(
              label: labels[index],
              selected: labels[index] == selected,
              onTap: () => onSelected(labels[index]),
            ),
            if (index != labels.length - 1) const SizedBox(width: 10),
          ],
        ],
      ),
    );
  }
}

class _CategoryChip extends StatelessWidget {
  const _CategoryChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      selected: selected,
      button: true,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Container(
          height: 38,
          constraints: const BoxConstraints(minWidth: 58),
          padding: const EdgeInsets.symmetric(horizontal: 16),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: selected ? AppColors.blue : AppColors.surface,
            borderRadius: BorderRadius.circular(20),
            border:
                Border.all(color: selected ? AppColors.blue : AppColors.line),
          ),
          child: Text(
            label,
            style: AppTextStyles.body.copyWith(
              color: selected ? Colors.white : AppColors.muted,
              fontWeight: FontWeight.w700,
            ),
          ),
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
    required this.conversations,
    required this.userNickname,
    required this.onConversationTap,
    required this.onNewConversationTap,
  });

  final VoidCallback onClose;
  final VoidCallback onSkillsPressed;
  final List<ConversationSummary> conversations;
  final String userNickname;
  final ValueChanged<String> onConversationTap;
  final VoidCallback onNewConversationTap;

  @override
  Widget build(BuildContext context) {
    final sections = _groupConversations(conversations);
    return SafeArea(
      bottom: false,
      child: DecoratedBox(
        decoration: const BoxDecoration(
          color: AppColors.surface,
          boxShadow: [
            BoxShadow(
              color: Color(0x21111827),
              blurRadius: 30,
              offset: Offset(12, 0),
            ),
          ],
        ),
        child: Column(
          children: [
            _DrawerHeader(
              onClose: onClose,
              onNewConversationTap: onNewConversationTap,
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(18, 12, 18, 24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _NewChatCard(onTap: onNewConversationTap),
                    const SizedBox(height: 12),
                    _DrawerSkillEntry(onTap: onSkillsPressed),
                    const SizedBox(height: 22),
                    const _RecentChatHeader(),
                    const SizedBox(height: 14),
                    if (conversations.isEmpty)
                      const _EmptyHistory()
                    else
                      for (final section in sections) ...[
                        _ChatSection(
                          title: section.title,
                          items: [
                            for (final item in section.items)
                              _ChatItemSpec(
                                item.title.isEmpty ? '芽芽对话' : item.title,
                                item.preview,
                                item.category,
                                false,
                                item.sessionId,
                              ),
                          ],
                          onTap: onConversationTap,
                        ),
                        if (section != sections.last)
                          const SizedBox(height: 18),
                      ],
                  ],
                ),
              ),
            ),
            _DrawerUserBar(nickname: userNickname),
          ],
        ),
      ),
    );
  }
}

List<_ConversationSectionSpec> _groupConversations(
  List<ConversationSummary> conversations,
) {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final sevenDaysAgo = today.subtract(const Duration(days: 6));
  final todayItems = <ConversationSummary>[];
  final recentItems = <ConversationSummary>[];
  final earlierItems = <ConversationSummary>[];

  for (final item in conversations) {
    final activeAt = item.lastActiveAt ?? item.createdAt;
    if (activeAt == null) {
      recentItems.add(item);
      continue;
    }
    final day = DateTime(activeAt.year, activeAt.month, activeAt.day);
    if (!day.isBefore(today)) {
      todayItems.add(item);
    } else if (!day.isBefore(sevenDaysAgo)) {
      recentItems.add(item);
    } else {
      earlierItems.add(item);
    }
  }

  return [
    if (todayItems.isNotEmpty)
      _ConversationSectionSpec(title: '今天', items: todayItems),
    if (recentItems.isNotEmpty)
      _ConversationSectionSpec(title: '7天内', items: recentItems),
    if (earlierItems.isNotEmpty)
      _ConversationSectionSpec(title: '更早', items: earlierItems),
  ];
}

class _ConversationSectionSpec {
  const _ConversationSectionSpec({
    required this.title,
    required this.items,
  });

  final String title;
  final List<ConversationSummary> items;
}

class _DrawerHeader extends StatelessWidget {
  const _DrawerHeader({
    required this.onClose,
    required this.onNewConversationTap,
  });

  final VoidCallback onClose;
  final VoidCallback onNewConversationTap;

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
            _HeaderIconButton(
              icon: LucideIcons.squarePen,
              onPressed: onNewConversationTap,
            ),
          ],
        ),
      ),
    );
  }
}

class _NewChatCard extends StatelessWidget {
  const _NewChatCard({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        height: 92,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            stops: [0, 0.62, 1],
            colors: [
              Color(0xFFF5FBF2),
              Color(0xFFEAF6EF),
              Color(0xFFFFFBF0),
            ],
          ),
          border: Border.all(color: Color(0xFFDCEBDF)),
          borderRadius: BorderRadius.circular(24),
          boxShadow: const [
            BoxShadow(
              color: Color(0x120F3D2E),
              blurRadius: 18,
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
                color: Color(0xFFE0F1E7),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: Color(0xFFC9E3D1)),
              ),
              child: const Icon(LucideIcons.plus,
                  color: AppColors.greenDark, size: 24),
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
                      color: AppColors.ink,
                      fontSize: 17,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '让芽芽帮你分析农场问题',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.small.copyWith(
                      color: AppColors.muted,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
