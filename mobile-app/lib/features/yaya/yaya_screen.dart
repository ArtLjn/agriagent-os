import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/chip_label.dart';
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
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 184),
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      ContextPromptCard(),
                      SizedBox(height: 12),
                      ContextPills(),
                      SizedBox(height: 14),
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
            bottom: 104,
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
      child: Row(
        children: [
          SuggestionIcon(),
          SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('今天可以这样问', style: AppTextStyles.sectionTitle),
                SizedBox(height: 4),
                Text('芽芽会读取你的经营上下文', style: AppTextStyles.small),
              ],
            ),
          ),
          Icon(LucideIcons.chevronRight, size: 18, color: AppColors.subtle),
        ],
      ),
    );
  }
}

class ContextPills extends StatelessWidget {
  const ContextPills({super.key});

  @override
  Widget build(BuildContext context) {
    return const SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          ChipLabel.blue('安排今天作业'),
          SizedBox(width: 8),
          ChipLabel.teal('分析成本'),
          SizedBox(width: 8),
          ChipLabel.neutral('生成周报'),
        ],
      ),
    );
  }
}

class SuggestionIcon extends StatelessWidget {
  const SuggestionIcon({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 42,
      height: 42,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.tealSoft, AppColors.blueSoft],
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: const Icon(LucideIcons.sparkles, size: 19, color: AppColors.teal),
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
        ),
        SizedBox(height: 12),
        ChatBubble(text: '如果晚上降温，哪些棚要先处理？', fromUser: true),
        SizedBox(height: 12),
        ChatBubble(
          text: '优先处理东棚 1-6 号，其次是番茄试种棚。建议傍晚前完成覆盖，并把人工结算一起确认。',
          fromUser: false,
        ),
      ],
    );
  }
}

class ChatBubble extends StatelessWidget {
  const ChatBubble({super.key, required this.text, required this.fromUser});

  final String text;
  final bool fromUser;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: fromUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 300),
        padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 12),
        decoration: BoxDecoration(
          color: fromUser ? AppColors.blue : Colors.white,
          borderRadius: BorderRadius.only(
            topLeft: Radius.circular(fromUser ? 20 : 10),
            topRight: Radius.circular(fromUser ? 10 : 20),
            bottomLeft: const Radius.circular(20),
            bottomRight: const Radius.circular(20),
          ),
          border: fromUser ? null : Border.all(color: AppColors.lineSoft),
          boxShadow: fromUser
              ? const [
                  BoxShadow(
                    color: Color(0x224078FF),
                    blurRadius: 22,
                    offset: Offset(0, 10),
                  ),
                ]
              : const [
                  BoxShadow(
                    color: Color(0x0A101828),
                    blurRadius: 20,
                    offset: Offset(0, 10),
                  ),
                ],
        ),
        child: Text(
          text,
          style: TextStyle(
            color: fromUser ? Colors.white : AppColors.ink,
            fontSize: 13,
            height: 20 / 13,
            fontWeight: FontWeight.w500,
            letterSpacing: 0,
          ),
        ),
      ),
    );
  }
}

class ChatComposer extends StatelessWidget {
  const ChatComposer({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 56),
      padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.white.withValues(alpha: 0.9)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x1824405F),
            blurRadius: 28,
            offset: Offset(0, 14),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '输入问题或直接说“帮我安排今天”',
              style: AppTextStyles.body.copyWith(fontWeight: FontWeight.w500),
            ),
          ),
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.navy,
              borderRadius: BorderRadius.circular(15),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x24172033),
                  blurRadius: 18,
                  offset: Offset(0, 8),
                ),
              ],
            ),
            child:
                const Icon(LucideIcons.arrowUp, size: 18, color: Colors.white),
          ),
        ],
      ),
    );
  }
}
