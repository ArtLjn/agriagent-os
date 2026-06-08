# Flutter Mobile App UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 Flutter App，并让首页、工作台、芽芽、账单、我的五个核心页面与 `docs/ui/flutter-app-concept/index.html` 的移动端 UI 高度一致。

**Architecture:** 在仓库根目录创建 `mobile-app/` Flutter 工程，使用纯 Flutter 组件复刻现有 HTML 高保真稿。UI 层先用 mock 数据完整还原视觉，再通过 Repository/Service 层接入后端能力；API 路径只能出现在数据层代码中，不能出现在用户可见 UI 文案中。

**Tech Stack:** Flutter stable、Dart、Riverpod、Dio、GoRouter、Lucide 风格图标、Flutter widget/golden tests。

---

## 视觉基准与硬性约束

- 唯一视觉基准文件：`docs/ui/flutter-app-concept/index.html`
- 设计说明文件：`docs/ui/flutter-app-concept/README.md`
- 不再使用 Figma，同步实现时以 HTML 静态稿为准。
- App 中聊天助手统一叫 `芽芽`，不要显示 `AI 助手`。
- 底部中间 Tab 显示 `芽芽`，可以特殊浮起，但不能溢出、贴底、遮挡文字。
- 不要使用紫色 AI 配色；禁止使用 `#8559f6`、`#f3efff`、`purple`、`violet` 作为芽芽主色。
- UI 不展示 API 路径，例如 `/agent/chat`、`/costs`、`/weather/forecast` 只能存在于 API 客户端代码，不得出现在页面文本。
- 整体风格是现代经营工具，不走土味农业风；不要大面积绿色、稻穗、田园插画。

## 目标文件结构

创建或修改以下文件：

- Create: `mobile-app/pubspec.yaml`：Flutter 依赖、资源声明、测试依赖。
- Create: `mobile-app/lib/main.dart`：App 入口。
- Create: `mobile-app/lib/app/farm_manager_app.dart`：全局 App、路由、主题入口。
- Create: `mobile-app/lib/app/app_router.dart`：五个主 Tab 路由。
- Create: `mobile-app/lib/theme/app_colors.dart`：设计色板，必须从 HTML token 翻译。
- Create: `mobile-app/lib/theme/app_text_styles.dart`：字号、字重、行高。
- Create: `mobile-app/lib/theme/app_theme.dart`：Material theme。
- Create: `mobile-app/lib/features/shell/app_shell.dart`：五 Tab 容器和底部导航。
- Create: `mobile-app/lib/features/shell/bottom_tab_bar.dart`：完全复刻 HTML 底栏。
- Create: `mobile-app/lib/features/home/home_screen.dart`：今日概览页。
- Create: `mobile-app/lib/features/workbench/workbench_screen.dart`：工作台页。
- Create: `mobile-app/lib/features/yaya/yaya_screen.dart`：芽芽聊天页。
- Create: `mobile-app/lib/features/billing/billing_screen.dart`：账单页。
- Create: `mobile-app/lib/features/profile/profile_screen.dart`：我的页。
- Create: `mobile-app/lib/shared/widgets/phone_safe_scaffold.dart`：页面安全区和背景布局。
- Create: `mobile-app/lib/shared/widgets/card_panel.dart`：卡片容器。
- Create: `mobile-app/lib/shared/widgets/app_icon_tile.dart`：功能宫格图标。
- Create: `mobile-app/lib/shared/widgets/status_header.dart`：页面标题栏。
- Create: `mobile-app/lib/data/api/api_client.dart`：Dio 客户端。
- Create: `mobile-app/lib/data/repositories/dashboard_repository.dart`：首页经营汇总数据。
- Create: `mobile-app/lib/data/repositories/workbench_repository.dart`：工作台入口数据。
- Create: `mobile-app/lib/data/repositories/yaya_repository.dart`：芽芽对话数据。
- Create: `mobile-app/lib/data/repositories/billing_repository.dart`：账单数据。
- Create: `mobile-app/lib/data/repositories/profile_repository.dart`：我的页数据。
- Create: `mobile-app/test/features/shell/bottom_tab_bar_test.dart`：底栏布局测试。
- Create: `mobile-app/test/features/yaya/yaya_copy_test.dart`：芽芽命名和禁紫测试。
- Create: `mobile-app/test/features/home/home_screen_test.dart`：首页关键文案测试。
- Create: `mobile-app/test/features/billing/billing_screen_test.dart`：账单关键模块测试。
- Create: `mobile-app/test/golden/app_screens_golden_test.dart`：五屏 golden 截图测试。
- Create: `mobile-app/README.md`：启动、测试、视觉验收说明。

---

### Task 1: 创建 Flutter 工程骨架

**Files:**
- Create: `mobile-app/`
- Modify: `mobile-app/pubspec.yaml`
- Create: `mobile-app/README.md`

- [ ] **Step 1: 确认当前没有 Flutter App 目录**

Run:

```bash
test ! -d mobile-app && echo "mobile-app can be created"
```

Expected:

```text
mobile-app can be created
```

- [ ] **Step 2: 创建 Flutter 工程**

Run:

```bash
flutter create mobile-app --org com.farmmanager --project-name farm_manager_app --platforms=ios,android
```

Expected: 输出包含 `All done!`，并生成 `mobile-app/pubspec.yaml`。

- [ ] **Step 3: 修改 `mobile-app/pubspec.yaml` 依赖**

将依赖调整为：

```yaml
name: farm_manager_app
description: Farm Manager Flutter mobile app.
publish_to: "none"
version: 0.1.0+1

environment:
  sdk: ">=3.4.0 <4.0.0"

dependencies:
  flutter:
    sdk: flutter
  flutter_localizations:
    sdk: flutter
  cupertino_icons: ^1.0.8
  dio: ^5.7.0
  flutter_riverpod: ^2.6.1
  go_router: ^14.6.2
  lucide_icons_flutter: ^1.2.6

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^5.0.0
  golden_toolkit: ^0.15.0

flutter:
  uses-material-design: true
```

- [ ] **Step 4: 安装依赖**

Run:

```bash
cd mobile-app && flutter pub get
```

Expected: `exit code 0`。如果 `lucide_icons_flutter` 版本不可用，先运行 `flutter pub add lucide_icons_flutter`，然后保留解析出的版本号。

- [ ] **Step 5: 创建 `mobile-app/README.md`**

写入：

```markdown
# Farm Manager Flutter App

视觉基准：`../docs/ui/flutter-app-concept/index.html`

## 运行

```bash
flutter run
```

## 测试

```bash
flutter test
```

## 视觉验收

- 五个 Tab：首页、工作台、芽芽、账单、我的。
- 芽芽页面和底部 Tab 统一叫“芽芽”。
- 页面 UI 不展示任何 API 路径。
- 芽芽主色使用蓝青系，不使用紫色。
```

- [ ] **Step 6: 提交骨架**

Run:

```bash
git add mobile-app
git commit -m "feat: scaffold flutter mobile app"
```

Expected: commit 成功。

---

### Task 2: 建立设计 Token 和主题

**Files:**
- Create: `mobile-app/lib/theme/app_colors.dart`
- Create: `mobile-app/lib/theme/app_text_styles.dart`
- Create: `mobile-app/lib/theme/app_theme.dart`
- Modify: `mobile-app/lib/main.dart`
- Create: `mobile-app/lib/app/farm_manager_app.dart`

- [ ] **Step 1: 创建色板测试**

Create: `mobile-app/test/theme/app_colors_test.dart`

```dart
import 'package:farm_manager_app/theme/app_colors.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('芽芽主题不使用紫色', () {
    expect(AppColors.teal.value, isNot(equals(0xFF8559F6)));
    expect(AppColors.tealSoft.value, isNot(equals(0xFFF3EFFF)));
  });

  test('核心色值与 HTML 设计稿一致', () {
    expect(AppColors.background, const Color(0xFFF6F8FB));
    expect(AppColors.surface, Colors.white);
    expect(AppColors.ink, const Color(0xFF101828));
    expect(AppColors.blue, const Color(0xFF4078FF));
    expect(AppColors.cyan, const Color(0xFF0EA5B8));
    expect(AppColors.teal, const Color(0xFF0891B2));
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd mobile-app && flutter test test/theme/app_colors_test.dart
```

Expected: FAIL，提示找不到 `AppColors`。

- [ ] **Step 3: 创建 `app_colors.dart`**

```dart
import 'package:flutter/material.dart';

class AppColors {
  const AppColors._();

  static const background = Color(0xFFF6F8FB);
  static const surface = Color(0xFFFFFFFF);
  static const surface2 = Color(0xFFEEF3F8);
  static const surface3 = Color(0xFFF8FAFC);
  static const ink = Color(0xFF101828);
  static const muted = Color(0xFF667085);
  static const subtle = Color(0xFF98A2B3);
  static const line = Color(0xFFE4EAF2);
  static const blue = Color(0xFF4078FF);
  static const blueSoft = Color(0xFFEDF4FF);
  static const cyan = Color(0xFF0EA5B8);
  static const cyanSoft = Color(0xFFE8FBFF);
  static const teal = Color(0xFF0891B2);
  static const tealSoft = Color(0xFFE7F8FB);
  static const green = Color(0xFF16A36A);
  static const greenSoft = Color(0xFFEAF8F0);
  static const amber = Color(0xFFEF9B2D);
  static const amberSoft = Color(0xFFFFF4E5);
  static const navy = Color(0xFF172033);
}
```

- [ ] **Step 4: 创建 `app_text_styles.dart`**

```dart
import 'package:flutter/material.dart';
import 'app_colors.dart';

class AppTextStyles {
  const AppTextStyles._();

  static const title = TextStyle(
    fontSize: 23,
    height: 1.05,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  static const sectionTitle = TextStyle(
    fontSize: 16,
    height: 1.2,
    fontWeight: FontWeight.w800,
    color: AppColors.ink,
    letterSpacing: 0,
  );

  static const body = TextStyle(
    fontSize: 13,
    height: 20 / 13,
    fontWeight: FontWeight.w500,
    color: AppColors.muted,
    letterSpacing: 0,
  );

  static const small = TextStyle(
    fontSize: 11,
    height: 16 / 11,
    fontWeight: FontWeight.w600,
    color: AppColors.muted,
    letterSpacing: 0,
  );

  static const tab = TextStyle(
    fontSize: 10,
    height: 1.2,
    fontWeight: FontWeight.w700,
    letterSpacing: 0,
  );
}
```

- [ ] **Step 5: 创建 `app_theme.dart`**

```dart
import 'package:flutter/material.dart';
import 'app_colors.dart';

class AppTheme {
  const AppTheme._();

  static ThemeData light() {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: AppColors.blue,
        primary: AppColors.blue,
        secondary: AppColors.cyan,
        surface: AppColors.surface,
      ),
      scaffoldBackgroundColor: AppColors.background,
      fontFamily: 'System',
    );
  }
}
```

- [ ] **Step 6: 创建 App 入口**

Modify: `mobile-app/lib/main.dart`

```dart
import 'package:flutter/material.dart';
import 'app/farm_manager_app.dart';

void main() {
  runApp(const FarmManagerApp());
}
```

Create: `mobile-app/lib/app/farm_manager_app.dart`

```dart
import 'package:flutter/material.dart';
import '../features/shell/app_shell.dart';
import '../theme/app_theme.dart';

class FarmManagerApp extends StatelessWidget {
  const FarmManagerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Farm Manager',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      home: const AppShell(),
    );
  }
}
```

- [ ] **Step 7: 运行主题测试**

Run:

```bash
cd mobile-app && flutter test test/theme/app_colors_test.dart
```

Expected: PASS。

- [ ] **Step 8: 提交主题**

Run:

```bash
git add mobile-app/lib/theme mobile-app/lib/main.dart mobile-app/lib/app mobile-app/test/theme
git commit -m "feat: add flutter design tokens"
```

---

### Task 3: 实现共享 UI 组件

**Files:**
- Create: `mobile-app/lib/shared/widgets/card_panel.dart`
- Create: `mobile-app/lib/shared/widgets/status_header.dart`
- Create: `mobile-app/lib/shared/widgets/app_icon_tile.dart`
- Create: `mobile-app/lib/shared/widgets/chip_label.dart`
- Create: `mobile-app/lib/shared/widgets/phone_safe_scaffold.dart`
- Test: `mobile-app/test/shared/widgets/shared_widgets_test.dart`

- [ ] **Step 1: 创建共享组件测试**

```dart
import 'package:farm_manager_app/shared/widgets/app_icon_tile.dart';
import 'package:farm_manager_app/shared/widgets/card_panel.dart';
import 'package:farm_manager_app/shared/widgets/chip_label.dart';
import 'package:farm_manager_app/theme/app_colors.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

void main() {
  testWidgets('CardPanel 使用 18 圆角和边框', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: CardPanel(child: Text('卡片'))));
    final decorated = tester.widget<DecoratedBox>(find.byType(DecoratedBox).first);
    final decoration = decorated.decoration as BoxDecoration;
    expect(decoration.borderRadius, BorderRadius.circular(18));
    expect(decoration.color, AppColors.surface);
  });

  testWidgets('AppIconTile 显示图标和标题', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: AppIconTile(icon: LucideIcons.bot, label: '芽芽'),
    ));
    expect(find.text('芽芽'), findsOneWidget);
  });

  testWidgets('ChipLabel 显示短标签', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ChipLabel.blue('芽芽今日汇总')));
    expect(find.text('芽芽今日汇总'), findsOneWidget);
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd mobile-app && flutter test test/shared/widgets/shared_widgets_test.dart
```

Expected: FAIL，提示组件不存在。

- [ ] **Step 3: 创建 `card_panel.dart`**

```dart
import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';

class CardPanel extends StatelessWidget {
  const CardPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.background = AppColors.surface,
    this.borderColor = AppColors.line,
  });

  final Widget child;
  final EdgeInsets padding;
  final Color background;
  final Color borderColor;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: borderColor),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0D101828),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Padding(padding: padding, child: child),
    );
  }
}
```

- [ ] **Step 4: 创建 `chip_label.dart`**

```dart
import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class ChipLabel extends StatelessWidget {
  const ChipLabel({
    super.key,
    required this.text,
    required this.background,
    required this.foreground,
  });

  const ChipLabel.blue(String text, {super.key})
      : text = text,
        background = AppColors.blueSoft,
        foreground = AppColors.blue;

  const ChipLabel.teal(String text, {super.key})
      : text = text,
        background = AppColors.tealSoft,
        foreground = AppColors.teal;

  final String text;
  final Color background;
  final Color foreground;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 26),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: AppTextStyles.small.copyWith(
          color: foreground,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}
```

- [ ] **Step 5: 创建 `app_icon_tile.dart`**

```dart
import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';

enum IconTone { blue, cyan, teal, green, amber }

class AppIconTile extends StatelessWidget {
  const AppIconTile({
    super.key,
    required this.icon,
    required this.label,
    this.tone = IconTone.blue,
  });

  final IconData icon;
  final String label;
  final IconTone tone;

  Color get foreground => switch (tone) {
        IconTone.blue => AppColors.blue,
        IconTone.cyan => AppColors.cyan,
        IconTone.teal => AppColors.teal,
        IconTone.green => AppColors.green,
        IconTone.amber => AppColors.amber,
      };

  Color get background => switch (tone) {
        IconTone.blue => AppColors.blueSoft,
        IconTone.cyan => AppColors.cyanSoft,
        IconTone.teal => AppColors.tealSoft,
        IconTone.green => AppColors.greenSoft,
        IconTone.amber => AppColors.amberSoft,
      };

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 70,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: background,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Icon(icon, size: 22, color: foreground),
          ),
          const SizedBox(height: 7),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppColors.ink,
              fontSize: 11,
              height: 15 / 11,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 6: 创建 `status_header.dart`**

```dart
import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class StatusHeader extends StatelessWidget {
  const StatusHeader({
    super.key,
    required this.title,
    required this.subtitle,
    required this.trailingIcon,
    this.leadingIcon,
    this.center = false,
  });

  final String title;
  final String subtitle;
  final IconData trailingIcon;
  final IconData? leadingIcon;
  final bool center;

  @override
  Widget build(BuildContext context) {
    final titleBlock = Column(
      crossAxisAlignment: center ? CrossAxisAlignment.center : CrossAxisAlignment.start,
      children: [
        Text(title, style: AppTextStyles.title),
        const SizedBox(height: 5),
        Text(subtitle, style: AppTextStyles.small.copyWith(fontSize: 12)),
      ],
    );

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          if (leadingIcon != null) HeaderAction(icon: leadingIcon!) else titleBlock,
          if (leadingIcon != null) titleBlock,
          HeaderAction(icon: trailingIcon),
        ],
      ),
    );
  }
}

class HeaderAction extends StatelessWidget {
  const HeaderAction({super.key, required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 38,
      height: 38,
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(13),
      ),
      child: Icon(icon, size: 18, color: AppColors.blue),
    );
  }
}
```

- [ ] **Step 7: 创建 `phone_safe_scaffold.dart`**

```dart
import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';

class PhoneSafeScaffold extends StatelessWidget {
  const PhoneSafeScaffold({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(child: child),
    );
  }
}
```

- [ ] **Step 8: 运行共享组件测试**

Run:

```bash
cd mobile-app && flutter test test/shared/widgets/shared_widgets_test.dart
```

Expected: PASS。

- [ ] **Step 9: 提交共享组件**

Run:

```bash
git add mobile-app/lib/shared mobile-app/test/shared
git commit -m "feat: add shared flutter ui primitives"
```

---

### Task 4: 实现五 Tab Shell 和底部导航

**Files:**
- Create: `mobile-app/lib/features/shell/app_shell.dart`
- Create: `mobile-app/lib/features/shell/bottom_tab_bar.dart`
- Create: `mobile-app/test/features/shell/bottom_tab_bar_test.dart`

- [ ] **Step 1: 创建底栏测试**

```dart
import 'package:farm_manager_app/features/shell/app_shell.dart';
import 'package:farm_manager_app/features/shell/bottom_tab_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('底部导航包含五个 Tab 且中间是芽芽', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: AppShell()));

    expect(find.text('首页'), findsOneWidget);
    expect(find.text('工作台'), findsOneWidget);
    expect(find.text('芽芽'), findsOneWidget);
    expect(find.text('账单'), findsOneWidget);
    expect(find.text('我的'), findsOneWidget);
    expect(find.text('AI'), findsNothing);
  });

  testWidgets('芽芽按钮不会贴到底部边缘', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: SizedBox(
      width: 375,
      height: 812,
      child: Align(
        alignment: Alignment.bottomCenter,
        child: AppBottomTabBar(selectedIndex: 2, onChanged: (_) {}),
      ),
    ))));

    final bar = tester.getRect(find.byType(AppBottomTabBar));
    final yaya = tester.getRect(find.text('芽芽'));
    expect(yaya.bottom, lessThan(bar.bottom - 4));
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd mobile-app && flutter test test/features/shell/bottom_tab_bar_test.dart
```

Expected: FAIL，提示 Shell/TabBar 不存在。

- [ ] **Step 3: 创建 `bottom_tab_bar.dart`**

```dart
import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class AppBottomTabBar extends StatelessWidget {
  const AppBottomTabBar({
    super.key,
    required this.selectedIndex,
    required this.onChanged,
  });

  final int selectedIndex;
  final ValueChanged<int> onChanged;

  static const _tabs = [
    _TabSpec('首页', LucideIcons.layoutDashboard),
    _TabSpec('工作台', LucideIcons.briefcaseBusiness),
    _TabSpec('芽芽', LucideIcons.bot),
    _TabSpec('账单', LucideIcons.receipt),
    _TabSpec('我的', LucideIcons.user),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 335,
      height: 66,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.96),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.line),
        boxShadow: const [
          BoxShadow(
            color: Color(0x1F101828),
            blurRadius: 40,
            offset: Offset(0, 16),
          ),
        ],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: List.generate(_tabs.length, (index) {
          final spec = _tabs[index];
          final selected = selectedIndex == index;
          if (index == 2) {
            return YayaTab(
              label: spec.label,
              icon: spec.icon,
              selected: selected,
              onTap: () => onChanged(index),
            );
          }
          return NormalTab(
            label: spec.label,
            icon: spec.icon,
            selected: selected,
            onTap: () => onChanged(index),
          );
        }),
      ),
    );
  }
}

class NormalTab extends StatelessWidget {
  const NormalTab({
    super.key,
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppColors.blue : AppColors.muted;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        width: 55,
        height: 48,
        decoration: BoxDecoration(
          color: selected ? AppColors.blueSoft : Colors.transparent,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 18, color: color),
            const SizedBox(height: 4),
            Text(label, style: AppTextStyles.tab.copyWith(color: color)),
          ],
        ),
      ),
    );
  }
}

class YayaTab extends StatelessWidget {
  const YayaTab({
    super.key,
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Transform.translate(
      offset: const Offset(0, -11),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: SizedBox(
          width: 55,
          height: 60,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.white, width: 4),
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: selected
                        ? const [AppColors.blue, AppColors.cyan]
                        : const [Colors.white, Color(0xFFEAF2FF), Color(0xFFDFE9FF)],
                  ),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x3D4078FF),
                      blurRadius: 28,
                      offset: Offset(0, 12),
                    ),
                  ],
                ),
                child: Icon(icon, size: 22, color: selected ? Colors.white : AppColors.blue),
              ),
              Text(label, style: AppTextStyles.tab.copyWith(color: AppColors.blue)),
            ],
          ),
        ),
      ),
    );
  }
}

class _TabSpec {
  const _TabSpec(this.label, this.icon);

  final String label;
  final IconData icon;
}
```

- [ ] **Step 4: 创建 `app_shell.dart`**

```dart
import 'package:flutter/material.dart';
import '../billing/billing_screen.dart';
import '../home/home_screen.dart';
import '../profile/profile_screen.dart';
import '../workbench/workbench_screen.dart';
import '../yaya/yaya_screen.dart';
import 'bottom_tab_bar.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int selectedIndex = 0;

  static const pages = [
    HomeScreen(),
    WorkbenchScreen(),
    YayaScreen(),
    BillingScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          IndexedStack(index: selectedIndex, children: pages),
          Positioned(
            left: 20,
            right: 20,
            bottom: 26,
            child: AppBottomTabBar(
              selectedIndex: selectedIndex,
              onChanged: (index) => setState(() => selectedIndex = index),
            ),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 5: 创建临时页面占位，保证 Shell 可编译**

每个页面先创建最小占位：

```dart
import 'package:flutter/material.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) => const Center(child: Text('今日概览'));
}
```

对应创建：

- `mobile-app/lib/features/home/home_screen.dart`
- `mobile-app/lib/features/workbench/workbench_screen.dart`，文本 `工作台`
- `mobile-app/lib/features/yaya/yaya_screen.dart`，文本 `芽芽`
- `mobile-app/lib/features/billing/billing_screen.dart`，文本 `账单`
- `mobile-app/lib/features/profile/profile_screen.dart`，文本 `我的`

- [ ] **Step 6: 运行底栏测试**

Run:

```bash
cd mobile-app && flutter test test/features/shell/bottom_tab_bar_test.dart
```

Expected: PASS。

- [ ] **Step 7: 提交 Shell**

Run:

```bash
git add mobile-app/lib/features mobile-app/test/features/shell
git commit -m "feat: add mobile tab shell"
```

---

### Task 5: 实现首页 今日概览

**Files:**
- Modify: `mobile-app/lib/features/home/home_screen.dart`
- Test: `mobile-app/test/features/home/home_screen_test.dart`

- [ ] **Step 1: 创建首页测试**

```dart
import 'package:farm_manager_app/features/home/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('首页展示芽芽汇总、天气、待处理事项', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: HomeScreen()));

    expect(find.text('今日概览'), findsOneWidget);
    expect(find.text('芽芽汇总了天气、建议、作业和账单'), findsOneWidget);
    expect(find.text('芽芽今日汇总'), findsOneWidget);
    expect(find.text('今天先做东棚授粉复核，傍晚前处理降温风险。'), findsOneWidget);
    expect(find.text('24℃'), findsOneWidget);
    expect(find.text('8℃'), findsOneWidget);
    expect(find.text('良好'), findsOneWidget);
    expect(find.text('今天要处理'), findsOneWidget);
  });

  testWidgets('首页不展示 API 路径', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: HomeScreen()));
    expect(find.textContaining('/'), findsNothing);
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd mobile-app && flutter test test/features/home/home_screen_test.dart
```

Expected: FAIL，当前页面只有占位。

- [ ] **Step 3: 实现首页**

`home_screen.dart` 要复刻 HTML 中首页结构：

```dart
import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import '../../shared/widgets/card_panel.dart';
import '../../shared/widgets/chip_label.dart';
import '../../shared/widgets/status_header.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Column(
        children: [
          const StatusHeader(
            title: '今日概览',
            subtitle: '芽芽汇总了天气、建议、作业和账单',
            trailingIcon: LucideIcons.scanLine,
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 112),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: const [
                  HomeHeroCard(),
                  SizedBox(height: 14),
                  TodayTasksCard(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class HomeHeroCard extends StatelessWidget {
  const HomeHeroCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(18),
      borderColor: const Color(0x294078FF),
      child: Stack(
        children: [
          Positioned(
            right: 0,
            top: 52,
            child: Container(
              width: 62,
              height: 62,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(24),
                gradient: const LinearGradient(colors: [Colors.white, Color(0xFFE9F2FF)]),
                boxShadow: const [
                  BoxShadow(color: Color(0x384078FF), blurRadius: 38, offset: Offset(0, 18)),
                ],
              ),
              child: const Icon(LucideIcons.sparkles, color: AppColors.blue),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  ChipLabel.blue('芽芽今日汇总'),
                  Text('07:30 更新', style: AppTextStyles.small),
                ],
              ),
              const SizedBox(height: 18),
              const SizedBox(
                width: 248,
                child: Text(
                  '今天先做东棚授粉复核，傍晚前处理降温风险。',
                  style: TextStyle(
                    fontSize: 23,
                    height: 31 / 23,
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
                    letterSpacing: 0,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                '已结合今日建议、天气预报、最近作业单和未结人工，给出今天的执行顺序。',
                style: AppTextStyles.body,
              ),
              const SizedBox(height: 16),
              Row(
                children: const [
                  WeatherItem(value: '24℃', label: '当前温度', color: AppColors.blue),
                  SizedBox(width: 8),
                  WeatherItem(value: '8℃', label: '夜间最低', color: AppColors.amber),
                  SizedBox(width: 8),
                  WeatherItem(value: '良好', label: '作业窗口', color: AppColors.green),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: const [
                  HomeButton(label: '查看建议', primary: true),
                  SizedBox(width: 10),
                  HomeButton(label: '查看天气', primary: false),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class WeatherItem extends StatelessWidget {
  const WeatherItem({super.key, required this.value, required this.label, required this.color});

  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        height: 62,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.78),
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: const Color(0x144078FF)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: color)),
            Text(label, style: AppTextStyles.small),
          ],
        ),
      ),
    );
  }
}

class HomeButton extends StatelessWidget {
  const HomeButton({super.key, required this.label, required this.primary});

  final String label;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 38,
      constraints: const BoxConstraints(minWidth: 92),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: BoxDecoration(
        color: primary ? AppColors.navy : Colors.white,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Center(
        child: Text(
          label,
          style: TextStyle(
            color: primary ? Colors.white : AppColors.blue,
            fontSize: 12,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
    );
  }
}

class TodayTasksCard extends StatelessWidget {
  const TodayTasksCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: const [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('今天要处理', style: AppTextStyles.sectionTitle),
              Text('全部', style: TextStyle(color: AppColors.blue, fontSize: 12, fontWeight: FontWeight.w800)),
            ],
          ),
          SizedBox(height: 12),
          TaskRow(icon: LucideIcons.clipboardCheck, tone: AppColors.blueSoft, color: AppColors.blue, title: '东棚 1-6 号授粉复核', subtitle: '10:30 · 3 人 · 来自作业单'),
          SizedBox(height: 12),
          TaskRow(icon: LucideIcons.triangleAlert, tone: AppColors.amberSoft, color: AppColors.amber, title: '夜间降温防护', subtitle: '最低 8℃ · 建议提前覆盖保温'),
          SizedBox(height: 12),
          TaskRow(icon: LucideIcons.walletCards, tone: AppColors.tealSoft, color: AppColors.teal, title: '昨日人工工资待确认', subtitle: '2 笔 · ¥860 · 可直接结算'),
        ],
      ),
    );
  }
}

class TaskRow extends StatelessWidget {
  const TaskRow({
    super.key,
    required this.icon,
    required this.tone,
    required this.color,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final Color tone;
  final Color color;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(color: tone, borderRadius: BorderRadius.circular(12)),
          child: Icon(icon, size: 18, color: color),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: AppColors.ink)),
              Text(subtitle, style: AppTextStyles.small),
            ],
          ),
        ),
      ],
    );
  }
}
```

- [ ] **Step 4: 运行首页测试**

Run:

```bash
cd mobile-app && flutter test test/features/home/home_screen_test.dart
```

Expected: PASS。

- [ ] **Step 5: 手动视觉检查首页**

Run:

```bash
cd mobile-app && flutter run -d chrome
```

Expected:

- 顶部标题 `今日概览`，副标题为 `芽芽汇总了天气、建议、作业和账单`
- 大卡首屏突出，天气三块不溢出
- 底部 Tab 不遮挡内容

- [ ] **Step 6: 提交首页**

Run:

```bash
git add mobile-app/lib/features/home mobile-app/test/features/home
git commit -m "feat: implement mobile home overview"
```

---

### Task 6: 实现工作台页面

**Files:**
- Modify: `mobile-app/lib/features/workbench/workbench_screen.dart`
- Test: `mobile-app/test/features/workbench/workbench_screen_test.dart`

- [ ] **Step 1: 创建工作台测试**

```dart
import 'package:farm_manager_app/features/workbench/workbench_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('工作台展示平台功能入口', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: WorkbenchScreen()));

    expect(find.text('工作台'), findsOneWidget);
    expect(find.text('平台所有功能的快捷入口'), findsOneWidget);
    expect(find.text('常用功能'), findsOneWidget);
    expect(find.text('新建作业'), findsOneWidget);
    expect(find.text('种植批次'), findsOneWidget);
    expect(find.text('工人工资'), findsOneWidget);
    expect(find.text('快速记账'), findsOneWidget);
    expect(find.text('生产管理'), findsOneWidget);
    expect(find.text('进行中的批次'), findsOneWidget);
  });

  testWidgets('工作台不展示 API 路径', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: WorkbenchScreen()));
    expect(find.textContaining('/'), findsNothing);
  });
}
```

- [ ] **Step 2: 实现工作台**

工作台布局必须对应 HTML：

- 顶部：`工作台` + `平台所有功能的快捷入口`
- 第一张卡：`常用功能`，4 列 2 行
- 第二张卡：`生产管理`，4 列 1 行
- 第三张卡：`进行中的批次`，两条批次进度

关键实现片段：

```dart
const commonTools = [
  ('新建作业', LucideIcons.filePlus2, IconTone.blue),
  ('种植批次', LucideIcons.layers3, IconTone.cyan),
  ('工人工资', LucideIcons.usersRound, IconTone.teal),
  ('快速记账', LucideIcons.receipt, IconTone.green),
  ('欠款管理', LucideIcons.handCoins, IconTone.amber),
  ('农事日志', LucideIcons.notebookTabs, IconTone.blue),
  ('天气预报', LucideIcons.cloudSun, IconTone.cyan),
  ('经营报告', LucideIcons.fileText, IconTone.teal),
];
```

网格使用：

```dart
GridView.count(
  crossAxisCount: 4,
  shrinkWrap: true,
  physics: const NeverScrollableScrollPhysics(),
  mainAxisSpacing: 12,
  crossAxisSpacing: 8,
  childAspectRatio: 0.82,
  children: commonTools.map((tool) {
    return AppIconTile(icon: tool.$2, label: tool.$1, tone: tool.$3);
  }).toList(),
)
```

- [ ] **Step 3: 运行工作台测试**

Run:

```bash
cd mobile-app && flutter test test/features/workbench/workbench_screen_test.dart
```

Expected: PASS。

- [ ] **Step 4: 提交工作台**

Run:

```bash
git add mobile-app/lib/features/workbench mobile-app/test/features/workbench
git commit -m "feat: implement mobile workbench"
```

---

### Task 7: 实现芽芽聊天页面

**Files:**
- Modify: `mobile-app/lib/features/yaya/yaya_screen.dart`
- Test: `mobile-app/test/features/yaya/yaya_copy_test.dart`

- [ ] **Step 1: 创建芽芽测试**

```dart
import 'package:farm_manager_app/features/yaya/yaya_screen.dart';
import 'package:farm_manager_app/theme/app_colors.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('聊天助手统一叫芽芽', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: YayaScreen()));

    expect(find.text('芽芽'), findsOneWidget);
    expect(find.text('AI 助手'), findsNothing);
    expect(find.textContaining('AI 会'), findsNothing);
    expect(find.text('芽芽会读取你的经营上下文'), findsOneWidget);
  });

  testWidgets('芽芽页面包含菜单、建议、聊天和输入框', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: YayaScreen()));

    expect(find.text('上下文：批次、作业、账单、天气'), findsOneWidget);
    expect(find.text('今天可以这样问'), findsOneWidget);
    expect(find.text('安排今天作业'), findsOneWidget);
    expect(find.text('分析成本'), findsOneWidget);
    expect(find.text('生成周报'), findsOneWidget);
    expect(find.text('输入问题或直接说“帮我安排今天”'), findsOneWidget);
  });

  test('芽芽主色不是紫色', () {
    expect(AppColors.teal.value, isNot(0xFF8559F6));
  });
}
```

- [ ] **Step 2: 实现芽芽页面**

页面结构必须对应 HTML：

- 左上角三条杠菜单按钮
- 标题 `芽芽`
- 副标题 `上下文：批次、作业、账单、天气`
- 提示卡：`今天可以这样问`、`芽芽会读取你的经营上下文`
- 三个建议 chip：`安排今天作业`、`分析成本`、`生成周报`
- 聊天气泡：两条芽芽消息、一条用户消息
- 底部输入框：`输入问题或直接说“帮我安排今天”`

关键样式：

```dart
const yayaGradient = LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: [AppColors.blue, AppColors.cyan],
);
```

禁止出现：

```dart
const Color(0xFF8559F6);
const Color(0xFFF3EFFF);
'AI 助手';
```

- [ ] **Step 3: 运行芽芽测试**

Run:

```bash
cd mobile-app && flutter test test/features/yaya/yaya_copy_test.dart
```

Expected: PASS。

- [ ] **Step 4: 手动检查中间 Tab**

Run:

```bash
cd mobile-app && flutter run -d chrome
```

Expected:

- 中间 Tab 文案为 `芽芽`
- 中间按钮为蓝青渐变，不是紫色
- 图标和文字不贴底、不溢出底栏

- [ ] **Step 5: 提交芽芽页面**

Run:

```bash
git add mobile-app/lib/features/yaya mobile-app/test/features/yaya
git commit -m "feat: implement yaya chat screen"
```

---

### Task 8: 实现账单页面

**Files:**
- Modify: `mobile-app/lib/features/billing/billing_screen.dart`
- Test: `mobile-app/test/features/billing/billing_screen_test.dart`

- [ ] **Step 1: 创建账单测试**

```dart
import 'package:farm_manager_app/features/billing/billing_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('账单展示经营收支核心模块', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: BillingScreen()));

    expect(find.text('账单'), findsOneWidget);
    expect(find.text('经营收支、人工、欠款的核心入口'), findsOneWidget);
    expect(find.text('本月净支出'), findsOneWidget);
    expect(find.text('¥18,426'), findsOneWidget);
    expect(find.text('记收入'), findsOneWidget);
    expect(find.text('智能记账'), findsOneWidget);
    expect(find.text('结人工'), findsOneWidget);
    expect(find.text('成本构成'), findsOneWidget);
    expect(find.text('最近流水'), findsOneWidget);
  });

  testWidgets('账单不展示 API 路径', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: BillingScreen()));
    expect(find.textContaining('/'), findsNothing);
  });
}
```

- [ ] **Step 2: 实现账单页面**

必须包含：

- 深色财务总览卡：`本月净支出`、`¥18,426`、收入/支出/欠款
- 三个快捷操作：`记收入`、`智能记账`、`结人工`
- 成本构成：人工、农资、水肥三条进度
- 最近流水：授粉人工、西瓜预售定金

账单主卡渐变：

```dart
const financeGradient = LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: [Color(0xFF182033), Color(0xFF29436F)],
);
```

人工相关颜色使用 `AppColors.teal`，不要使用紫色。

- [ ] **Step 3: 运行账单测试**

Run:

```bash
cd mobile-app && flutter test test/features/billing/billing_screen_test.dart
```

Expected: PASS。

- [ ] **Step 4: 提交账单页面**

Run:

```bash
git add mobile-app/lib/features/billing mobile-app/test/features/billing
git commit -m "feat: implement mobile billing screen"
```

---

### Task 9: 实现我的页面

**Files:**
- Modify: `mobile-app/lib/features/profile/profile_screen.dart`
- Test: `mobile-app/test/features/profile/profile_screen_test.dart`

- [ ] **Step 1: 创建我的页面测试**

```dart
import 'package:farm_manager_app/features/profile/profile_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('我的页面展示成熟产品常规设置入口', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ProfileScreen()));

    expect(find.text('我的'), findsOneWidget);
    expect(find.text('账号、设置和系统偏好'), findsOneWidget);
    expect(find.text('经营者'), findsOneWidget);
    expect(find.text('芽芽连续运行'), findsOneWidget);
    expect(find.text('芽芽偏好'), findsOneWidget);
    expect(find.text('消息提醒'), findsOneWidget);
    expect(find.text('账号安全'), findsOneWidget);
    expect(find.text('帮助中心'), findsOneWidget);
  });
}
```

- [ ] **Step 2: 实现我的页面**

必须包含：

- 个人资料卡：头像、经营者、手机号或账号摘要
- 三个统计：例如 `3 个农场`、`14 天 芽芽连续运行`、`98% 数据同步`
- 常用设置列表：`芽芽偏好`、`消息提醒`、`账号安全`
- 帮助与系统：`帮助中心`、`版本信息`

- [ ] **Step 3: 运行我的页面测试**

Run:

```bash
cd mobile-app && flutter test test/features/profile/profile_screen_test.dart
```

Expected: PASS。

- [ ] **Step 4: 提交我的页面**

Run:

```bash
git add mobile-app/lib/features/profile mobile-app/test/features/profile
git commit -m "feat: implement mobile profile screen"
```

---

### Task 10: 接入后端数据层但保持 UI 文案干净

**Files:**
- Create: `mobile-app/lib/data/api/api_client.dart`
- Create: `mobile-app/lib/data/repositories/dashboard_repository.dart`
- Create: `mobile-app/lib/data/repositories/workbench_repository.dart`
- Create: `mobile-app/lib/data/repositories/yaya_repository.dart`
- Create: `mobile-app/lib/data/repositories/billing_repository.dart`
- Create: `mobile-app/lib/data/repositories/profile_repository.dart`
- Test: `mobile-app/test/data/api_path_visibility_test.dart`

- [ ] **Step 1: 创建 API 路径可见性测试**

```dart
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('API 路径只允许出现在 data 层', () {
    final lib = Directory('lib');
    final offenders = <String>[];

    for (final entity in lib.listSync(recursive: true)) {
      if (entity is! File || !entity.path.endsWith('.dart')) continue;
      if (entity.path.contains('/data/')) continue;
      final text = entity.readAsStringSync();
      if (RegExp(r'"/(agent|costs|debts|weather|planting|cycles|auth|settings|api)/').hasMatch(text)) {
        offenders.add(entity.path);
      }
    }

    expect(offenders, isEmpty, reason: 'API 路径不能出现在 UI 层: $offenders');
  });
}
```

- [ ] **Step 2: 创建 `api_client.dart`**

```dart
import 'package:dio/dio.dart';

class ApiClient {
  ApiClient({Dio? dio}) : dio = dio ?? Dio(BaseOptions(baseUrl: const String.fromEnvironment('API_BASE_URL')));

  final Dio dio;

  Future<Response<dynamic>> get(String path, {Map<String, dynamic>? query}) {
    return dio.get(path, queryParameters: query);
  }

  Future<Response<dynamic>> post(String path, {Object? data}) {
    return dio.post(path, data: data);
  }
}
```

- [ ] **Step 3: 创建 Repository 路径映射**

`dashboard_repository.dart`：

```dart
import '../api/api_client.dart';

class DashboardRepository {
  DashboardRepository(this.client);

  final ApiClient client;

  Future<void> loadOverview() async {
    await Future.wait([
      client.get('/agent/daily'),
      client.get('/weather/forecast'),
      client.get('/planting/work-orders'),
      client.get('/planting/labor/unsettled-summary'),
    ]);
  }
}
```

`workbench_repository.dart`：

```dart
import '../api/api_client.dart';

class WorkbenchRepository {
  WorkbenchRepository(this.client);

  final ApiClient client;

  Future<void> warmUp() async {
    await Future.wait([
      client.get('/cycles'),
      client.get('/planting/units'),
      client.get('/planting/workers'),
      client.get('/planting/operation-types'),
      client.get('/logs'),
    ]);
  }
}
```

`yaya_repository.dart`：

```dart
import '../api/api_client.dart';

class YayaRepository {
  YayaRepository(this.client);

  final ApiClient client;

  Future<void> sendMessage(String message) async {
    await client.post('/agent/chat', data: {'message': message});
  }

  Future<void> loadConversations() async {
    await client.get('/agent/conversations');
  }
}
```

`billing_repository.dart`：

```dart
import '../api/api_client.dart';

class BillingRepository {
  BillingRepository(this.client);

  final ApiClient client;

  Future<void> loadBillingSummary() async {
    await Future.wait([
      client.get('/costs'),
      client.get('/costs/summary/2026'),
      client.get('/debts'),
    ]);
  }
}
```

`profile_repository.dart`：

```dart
import '../api/api_client.dart';

class ProfileRepository {
  ProfileRepository(this.client);

  final ApiClient client;

  Future<void> loadProfile() async {
    await Future.wait([
      client.get('/auth/me'),
      client.get('/settings'),
      client.get('/api/app/version'),
    ]);
  }
}
```

- [ ] **Step 4: 运行 API 路径可见性测试**

Run:

```bash
cd mobile-app && flutter test test/data/api_path_visibility_test.dart
```

Expected: PASS。

- [ ] **Step 5: 提交数据层**

Run:

```bash
git add mobile-app/lib/data mobile-app/test/data
git commit -m "feat: add mobile data repositories"
```

---

### Task 11: Golden 截图与视觉验收

**Files:**
- Create: `mobile-app/test/golden/app_screens_golden_test.dart`
- Modify: `mobile-app/test/flutter_test_config.dart`

- [ ] **Step 1: 创建 golden 配置**

`mobile-app/test/flutter_test_config.dart`：

```dart
import 'dart:async';
import 'package:golden_toolkit/golden_toolkit.dart';

Future<void> testExecutable(FutureOr<void> Function() testMain) async {
  await loadAppFonts();
  return testMain();
}
```

- [ ] **Step 2: 创建五屏 golden 测试**

```dart
import 'package:farm_manager_app/features/shell/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:golden_toolkit/golden_toolkit.dart';

void main() {
  testGoldens('五个核心页面在 375x812 下稳定渲染', (tester) async {
    final builder = DeviceBuilder()
      ..overrideDevicesForAllScenarios(devices: [
        const Device(name: 'iphone-375', size: Size(375, 812)),
      ])
      ..addScenario(widget: const AppShell(), name: 'home');

    await tester.pumpDeviceBuilder(builder);
    await screenMatchesGolden(tester, 'farm_manager_mobile_home');
  });
}
```

如果需要分别覆盖五个 Tab，在 `AppShell` 增加仅测试使用的可选参数：

```dart
const AppShell({super.key, this.initialIndex = 0});
final int initialIndex;
```

并在 state 初始化时使用：

```dart
late int selectedIndex = widget.initialIndex;
```

- [ ] **Step 3: 生成 golden**

Run:

```bash
cd mobile-app && flutter test --update-goldens test/golden/app_screens_golden_test.dart
```

Expected: golden 图片生成到 `mobile-app/test/golden/goldens/` 或 golden_toolkit 默认目录。

- [ ] **Step 4: 对照 HTML 原稿人工检查**

打开：

```bash
open ../docs/ui/flutter-app-concept/index.html
```

然后运行 Flutter：

```bash
flutter run -d chrome
```

人工检查清单：

- 首页：大卡位置、天气三块、今天要处理卡片与 HTML 一致。
- 工作台：宫格 4 列，不挤压、不截断、不显示 API。
- 芽芽：标题为 `芽芽`，中间 Tab 为 `芽芽`，蓝青配色，无紫色。
- 账单：深色总览卡、三快捷操作、成本构成、最近流水都在。
- 我的：个人中心结构成熟克制，不土味农业风。
- 底栏：`首页 / 工作台 / 芽芽 / 账单 / 我的` 全部可见，选中态不贴底、不溢出。

- [ ] **Step 5: 运行全部 Flutter 测试**

Run:

```bash
cd mobile-app && flutter test
```

Expected: PASS。

- [ ] **Step 6: 提交 golden 与验收**

Run:

```bash
git add mobile-app/test mobile-app/lib
git commit -m "test: add mobile visual regression coverage"
```

---

### Task 12: 最终质量门

**Files:**
- Modify: `mobile-app/README.md`

- [ ] **Step 1: 运行格式化**

Run:

```bash
cd mobile-app && dart format lib test
```

Expected: 输出格式化的文件列表或 `0` 改动。

- [ ] **Step 2: 运行静态分析**

Run:

```bash
cd mobile-app && flutter analyze
```

Expected: `No issues found!`

- [ ] **Step 3: 运行测试**

Run:

```bash
cd mobile-app && flutter test
```

Expected: 全部 PASS。

- [ ] **Step 4: 扫描禁用文案和颜色**

Run:

```bash
rg -n "AI 助手|<span>AI</span>|#8559f6|#f3efff|purple|violet|/agent|/costs|/weather|/planting|/cycles|/auth|/settings|/api" mobile-app/lib
```

Expected:

- 不出现 `AI 助手`
- 不出现紫色 token
- API 路径只出现在 `mobile-app/lib/data/` 下

- [ ] **Step 5: 更新 README 验收结果**

在 `mobile-app/README.md` 增加：

```markdown
## 当前验收状态

- `flutter analyze`: 通过
- `flutter test`: 通过
- 底部 Tab: 首页 / 工作台 / 芽芽 / 账单 / 我的
- 芽芽配色: 蓝青系，不使用紫色
- UI 文案: 不展示 API 路径
```

- [ ] **Step 6: 最终提交**

Run:

```bash
git add mobile-app/README.md
git commit -m "docs: document flutter mobile validation"
```

---

## 后端能力映射

这些路径只允许出现在 `mobile-app/lib/data/`：

- 首页：经营建议、天气预报、作业提醒、未结人工
- 工作台：批次、作业、种植单元、工人、作业类型、农事日志
- 芽芽：聊天、流式聊天、历史会话、经营报告
- 账单：成本流水、年度汇总、批次利润、欠款
- 我的：用户资料、设置、版本

实现 UI 时页面只展示业务语言，例如 `天气预报`、`作业提醒`、`成本构成`，不要展示接口路径。

## 自检清单

- [ ] 新工程位于 `mobile-app/`，没有修改 `archive/FarmManagerMobile`。
- [ ] 五个页面均实现，不是空壳。
- [ ] 视觉尺寸以 375x812 为基准，内容不被底部导航遮挡。
- [ ] 底部 Tab 中间项叫 `芽芽`，不是 `AI`。
- [ ] 聊天页标题叫 `芽芽`，不是 `AI 助手`。
- [ ] 芽芽主色为蓝青系，不使用紫色。
- [ ] 页面不展示任何 API 路径。
- [ ] `flutter analyze` 通过。
- [ ] `flutter test` 通过。
- [ ] 已对照 `docs/ui/flutter-app-concept/index.html` 做人工视觉检查。
