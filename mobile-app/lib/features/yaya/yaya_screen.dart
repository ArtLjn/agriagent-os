import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/status_header.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class YayaScreen extends StatelessWidget {
  const YayaScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Stack(
        children: [
          Column(
            children: [
              const StatusHeader(
                title: '芽芽',
                subtitle: '你的农场智能助手',
                leadingIcon: LucideIcons.menu,
                trailingIcon: LucideIcons.plus,
                center: true,
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 140),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const ContextPromptCard(),
                      const SizedBox(height: 20),
                      _TimeDivider('今天 07:30'),
                      const SizedBox(height: 20),
                      const ChatList(),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const Positioned(
            left: 16,
            right: 16,
            bottom: 24,
            child: ChatComposer(),
          ),
        ],
      ),
    );
  }
}

class ContextPromptCard extends StatelessWidget {
  const ContextPromptCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(18),
      background: AppColors.blueSoft,
      borderColor: const Color(0x1A4078FF),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: AppColors.blue.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child:
                    const Icon(LucideIcons.sparkles, size: 18, color: AppColors.blue),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '今天可以这样问',
                      style: AppTextStyles.sectionTitle.copyWith(fontSize: 15),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '芽芽会读取你的经营上下文',
                      style: AppTextStyles.small.copyWith(color: AppColors.muted),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          const ContextPills(),
        ],
      ),
    );
  }
}

class ContextPills extends StatelessWidget {
  const ContextPills({super.key});

  @override
  Widget build(BuildContext context) {
    return const Row(
      children: [
        Expanded(child: PromptPill('安排今天作业')),
        SizedBox(width: 8),
        Expanded(child: PromptPill('分析成本')),
        SizedBox(width: 8),
        Expanded(child: PromptPill('生成周报')),
      ],
    );
  }
}

class PromptPill extends StatelessWidget {
  const PromptPill(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return PressableScale(
      child: Container(
        height: 36,
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.7),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: AppColors.blue.withValues(alpha: 0.1),
          ),
        ),
        child: Center(
          child: Text(
            text,
            style: AppTextStyles.small.copyWith(
              color: AppColors.blue,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ),
    );
  }
}

class _TimeDivider extends StatelessWidget {
  const _TimeDivider(this.label);

  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Expanded(child: Divider(height: 1, color: AppColors.lineSoft)),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Text(
            label,
            style: AppTextStyles.small.copyWith(color: AppColors.subtle),
          ),
        ),
        const Expanded(child: Divider(height: 1, color: AppColors.lineSoft)),
      ],
    );
  }
}

class ChatList extends StatelessWidget {
  const ChatList({super.key});

  @override
  Widget build(BuildContext context) {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ChatBubble(
          text: '早上好。我看了今天的天气和作业单，东棚授粉复核适合放在上午完成。',
          fromUser: false,
          time: '07:30',
        ),
        SizedBox(height: 16),
        ChatBubble(
          text: '如果晚上降温，哪些棚要先处理？',
          fromUser: true,
          time: '07:31',
        ),
        SizedBox(height: 16),
        ChatBubble(
          text: '优先处理东棚 1-6 号，其次是番茄试种棚。建议傍晚前完成覆盖，并把人工结算一起确认。',
          fromUser: false,
          time: '07:32',
        ),
      ],
    );
  }
}

class ChatBubble extends StatelessWidget {
  const ChatBubble({
    super.key,
    required this.text,
    required this.fromUser,
    required this.time,
  });

  final String text;
  final bool fromUser;
  final String time;

  @override
  Widget build(BuildContext context) {
    final bubble = Container(
      constraints: const BoxConstraints(maxWidth: 270),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: fromUser ? const Color(0xFFDCEEFF) : AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: fromUser
            ? null
            : Border.all(color: AppColors.lineSoft),
        boxShadow: fromUser
            ? null
            : const [
                BoxShadow(
                  color: Color(0x08000000),
                  blurRadius: 8,
                  offset: Offset(0, 2),
                ),
              ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!fromUser)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 18,
                    height: 18,
                    decoration: BoxDecoration(
                      color: AppColors.blueSoft,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Icon(
                      LucideIcons.sparkles,
                      size: 10,
                      color: AppColors.blue,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    '芽芽',
                    style: AppTextStyles.small.copyWith(
                      color: AppColors.ink,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ],
              ),
            ),
          Text(
            text,
            style: TextStyle(
              color: fromUser ? AppColors.ink2 : AppColors.ink,
              fontSize: 14,
              height: 20 / 14,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: 6),
          Align(
            alignment: Alignment.centerRight,
            child: Text(
              time,
              style: AppTextStyles.small.copyWith(
                color: AppColors.subtle,
                fontSize: 11,
              ),
            ),
          ),
        ],
      ),
    );

    if (fromUser) {
      return Align(alignment: Alignment.centerRight, child: bubble);
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 32,
          height: 32,
          margin: const EdgeInsets.only(top: 2, right: 10),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [AppColors.blue, Color(0xFF6B9FFF)],
            ),
            borderRadius: BorderRadius.circular(16),
          ),
          child: const Center(
            child: Icon(
              LucideIcons.sparkles,
              size: 16,
              color: Colors.white,
            ),
          ),
        ),
        bubble,
      ],
    );
  }
}

class ChatComposer extends StatelessWidget {
  const ChatComposer({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 52),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.lineSoft),
        boxShadow: const [
          BoxShadow(
            color: Color(0x14092642),
            blurRadius: 20,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.surface2,
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(
              LucideIcons.mic,
              size: 18,
              color: AppColors.muted,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '输入问题或说"帮我安排今天"',
              style: AppTextStyles.body.copyWith(
                fontWeight: FontWeight.w500,
                color: AppColors.subtle,
              ),
            ),
          ),
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.blue,
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(
              LucideIcons.arrowUp,
              size: 18,
              color: Colors.white,
            ),
          ),
        ],
      ),
    );
  }
}

class PressableScale extends StatefulWidget {
  const PressableScale({super.key, required this.child, this.onTap});

  final Widget child;
  final VoidCallback? onTap;

  @override
  State<PressableScale> createState() => _PressableScaleState();
}

class _PressableScaleState extends State<PressableScale> {
  bool _pressed = false;

  void _setPressed(bool value) {
    if (_pressed == value) return;
    setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: widget.onTap,
      onTapDown: (_) => _setPressed(true),
      onTapCancel: () => _setPressed(false),
      onTapUp: (_) => _setPressed(false),
      child: AnimatedScale(
        scale: _pressed ? 0.97 : 1,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOutCubic,
        child: widget.child,
      ),
    );
  }
}
