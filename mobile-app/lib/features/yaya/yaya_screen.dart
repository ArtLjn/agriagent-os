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
                subtitle: '上下文：批次、作业、账单、天气',
                leadingIcon: LucideIcons.menu,
                trailingIcon: LucideIcons.plus,
                center: true,
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 160),
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      ContextPromptCard(),
                      SizedBox(height: 12),
                      Center(
                        child: Text(
                          '今天 07:30',
                          style: AppTextStyles.small,
                        ),
                      ),
                      SizedBox(height: 12),
                      ChatList(),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const Positioned(
            left: 16,
            right: 16,
            bottom: 88,
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
    return const CardPanel(
      padding: EdgeInsets.all(16),
      radius: 16,
      borderColor: Colors.transparent,
      background: Color(0xFFF0F7FF),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              SuggestionIcon(),
              SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('今天可以这样问', style: AppTextStyles.sectionTitle),
                    SizedBox(height: 4),
                    Text('芽芽会读取你的经营上下文，提供更精准的建议。', style: AppTextStyles.small),
                  ],
                ),
              ),
            ],
          ),
          SizedBox(height: 16),
          ContextPills(),
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
    return Container(
      height: 36,
      decoration: BoxDecoration(
        color: const Color(0xFFE8F0FF),
        borderRadius: BorderRadius.circular(18),
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
    );
  }
}

class SuggestionIcon extends StatelessWidget {
  const SuggestionIcon({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 34,
      height: 34,
      decoration: BoxDecoration(
        color: AppColors.blueSoft,
        borderRadius: BorderRadius.circular(9),
      ),
      child: const Icon(LucideIcons.sparkles, size: 18, color: AppColors.blue),
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
        SizedBox(height: 12),
        ChatBubble(
          text: '如果晚上降温，哪些棚要先处理？',
          fromUser: true,
          time: '07:31',
        ),
        SizedBox(height: 12),
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
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: fromUser ? const Color(0xFFDCEEFF) : AppColors.surface3,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!fromUser)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Text(
                '芽芽',
                style: AppTextStyles.small.copyWith(
                  color: AppColors.ink,
                  fontWeight: FontWeight.w900,
                ),
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
          const SizedBox(height: 5),
          Align(
            alignment: Alignment.centerRight,
            child: Text(time, style: AppTextStyles.small),
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
          width: 30,
          height: 30,
          margin: const EdgeInsets.only(top: 2, right: 9),
          decoration: BoxDecoration(
            color: AppColors.blueSoft,
            borderRadius: BorderRadius.circular(15),
          ),
          child:
              const Icon(LucideIcons.sparkles, size: 16, color: AppColors.blue),
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
      constraints: const BoxConstraints(minHeight: 56),
      padding: const EdgeInsets.fromLTRB(16, 12, 12, 12),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(
          top: BorderSide(color: AppColors.lineSoft),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '输入问题或直接说“帮我安排今天”',
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
              color: AppColors.surface2,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(LucideIcons.mic, size: 18, color: AppColors.ink),
          ),
        ],
      ),
    );
  }
}
