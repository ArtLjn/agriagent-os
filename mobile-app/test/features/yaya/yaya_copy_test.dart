import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/api/api_models.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/data/repositories/yaya_repository.dart';
import 'package:farm_manager_app/features/yaya/yaya_screen.dart';
import 'package:farm_manager_app/shared/assets/app_assets.dart';
import 'package:farm_manager_app/theme/app_colors.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  final repository = _YayaCopyRepository();

  Widget yayaScreen() {
    return MaterialApp(
      home: YayaScreen(repository: repository),
    );
  }

  testWidgets('聊天助手统一叫芽芽', (tester) async {
    await tester.pumpWidget(yayaScreen());

    expect(find.textContaining('芽芽'), findsWidgets);
    expect(find.textContaining('AI 会'), findsNothing);
    expect(find.textContaining('我是芽芽'), findsOneWidget);
    expect(find.textContaining('/agent/chat'), findsNothing);
  });

  testWidgets('芽芽首页是轻量聊天助手布局', (tester) async {
    await tester.pumpWidget(yayaScreen());

    expect(find.byIcon(LucideIcons.menu), findsOneWidget);
    expect(find.byIcon(LucideIcons.volume2), findsOneWidget);
    expect(find.byIcon(LucideIcons.plus), findsWidgets);
    expect(find.text('今日简报'), findsNothing);
    expect(find.text('待确认'), findsNothing);
    expect(find.text('风险'), findsNothing);
    expect(find.text('今日待办'), findsNothing);
    expect(find.text('今天适合干什么'), findsWidgets);
    expect(find.text('本月成本怎么看'), findsOneWidget);
    expect(find.text('生成周报'), findsOneWidget);
    expect(find.text('深度思考'), findsOneWidget);
    expect(find.text('经营分析'), findsOneWidget);
    expect(find.text('生成报告'), findsOneWidget);
    expect(find.text('全部技能'), findsOneWidget);
    expect(find.text('发消息或按住说话...'), findsOneWidget);
  });

  testWidgets('底部输入框在真机宽度下接近占满可用宽度', (tester) async {
    await tester.binding.setSurfaceSize(const Size(375, 812));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(yayaScreen());

    final inputBar = find.byType(AssistantInputBar);
    expect(inputBar, findsOneWidget);
    expect(tester.getSize(inputBar).width, greaterThanOrEqualTo(355));
  });

  testWidgets('点击快捷提示词会直接发送问题', (tester) async {
    final repository = _TrackingYayaRepository();
    await tester.pumpWidget(
      MaterialApp(home: YayaScreen(repository: repository)),
    );
    await tester.pump();

    await tester.tap(find.text('今天适合干什么'));
    await tester.pumpAndSettle();

    expect(repository.sentMessages, ['今天适合干什么']);
    expect(find.text('收到'), findsOneWidget);
  });

  testWidgets('从芽芽首页进入全部技能页会加载接口技能', (tester) async {
    final repository = _SkillsYayaRepository();
    await tester.pumpWidget(
      MaterialApp(home: YayaScreen(repository: repository)),
    );
    await tester.pump();

    await tester.tap(find.text('全部技能'));
    await tester.pumpAndSettle();

    expect(repository.loadSkillsCalls, 1);
    expect(find.text('智能记账'), findsOneWidget);
    expect(find.text('赊账汇总'), findsNothing);
  });

  testWidgets('点击菜单打开历史聊天抽屉', (tester) async {
    await tester.pumpWidget(yayaScreen());
    await tester.pump();

    await tester.tap(find.byIcon(LucideIcons.menu));
    await tester.pumpAndSettle();

    expect(find.text('新对话'), findsOneWidget);
    expect(find.text('最近对话'), findsOneWidget);
    expect(find.text('7天内'), findsOneWidget);
    expect(find.text('农友'), findsOneWidget);
    expect(find.text('张三'), findsNothing);
    expect(find.textContaining('检测到工具调用格式异常'), findsOneWidget);
    expect(find.text('对话'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('历史聊天抽屉关闭和卸载不会触发生命周期断言', (tester) async {
    await tester.pumpWidget(yayaScreen());
    await tester.pump();

    await tester.tap(find.byIcon(LucideIcons.menu));
    await tester.pumpAndSettle();
    await tester.tapAt(const Offset(360, 260));
    await tester.pumpAndSettle();
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
  });

  testWidgets('历史聊天抽屉底部展示用户昵称', (tester) async {
    final adapter = RecordingAdapter({
      '/auth/me': {...userResponse, 'nickname': '李伟刚'},
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;

    await tester.pumpWidget(
      MaterialApp(
        home: YayaScreen(
          repository: _YayaCopyRepository(),
          profileRepository: ProfileRepository(ApiClient(dio: dio)),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(LucideIcons.menu));
    await tester.pumpAndSettle();

    expect(find.text('李伟刚'), findsOneWidget);
    expect(find.text('农友'), findsNothing);
  });

  testWidgets('点击新对话入口会清空当前聊天内容', (tester) async {
    await tester.pumpWidget(yayaScreen());
    await tester.pump();

    await tester.tap(find.byIcon(LucideIcons.menu));
    await tester.pumpAndSettle();
    await tester.tap(find.textContaining('检测到工具调用格式异常'));
    await tester.pumpAndSettle();
    expect(find.text('建议傍晚浇水'), findsOneWidget);

    await tester.tap(find.byIcon(LucideIcons.plus).first);
    await tester.pumpAndSettle();

    expect(find.text('建议傍晚浇水'), findsNothing);
    expect(find.textContaining('我是芽芽'), findsOneWidget);
  });

  testWidgets('芽芽回复支持 Markdown 渲染', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: YayaScreen(repository: _MarkdownYayaRepository()),
      ),
    );
    await tester.pump();

    await tester.enterText(find.byType(TextField), '我的欠款');
    await tester.tap(find.byIcon(LucideIcons.send));
    await tester.pumpAndSettle();

    expect(find.textContaining('普通赊账'), findsOneWidget);
    expect(find.textContaining('**普通赊账**'), findsNothing);
  });

  testWidgets('芽芽 pending 回复展示确认卡并可点击确认', (tester) async {
    final repository = _PendingYayaRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: YayaScreen(repository: repository),
      ),
    );
    await tester.pump();

    await tester.enterText(find.byType(TextField), '我想种大豆');
    await tester.tap(find.byIcon(LucideIcons.send));
    await tester.pumpAndSettle();

    expect(find.text('待确认执行'), findsOneWidget);
    expect(find.text('理解：您说的是「我想种大豆」'), findsOneWidget);
    expect(find.text('作物'), findsOneWidget);
    expect(find.text('大豆'), findsOneWidget);
    expect(find.text('确认'), findsOneWidget);
    expect(find.text('取消'), findsOneWidget);

    await tester.tap(find.text('确认'));
    await tester.pumpAndSettle();

    expect(repository.sentMessages, ['我想种大豆', '确认']);
    expect(find.text('已执行'), findsOneWidget);
  });

  testWidgets('全部技能页使用独立 banner 图片资产并展示接口技能', (tester) async {
    final repository = _SkillsYayaRepository();
    await tester.pumpWidget(
      MaterialApp(home: YayaSkillsPage(repository: repository)),
    );
    await tester.pumpAndSettle();

    expect(find.text('全部技能'), findsOneWidget);
    expect(find.text('搜索技能'), findsOneWidget);
    expect(find.byKey(const ValueKey('yaya-skills-banner')), findsOneWidget);
    final banner = tester.widget<Image>(
      find.byKey(const ValueKey('yaya-skills-banner')),
    );
    expect((banner.image as AssetImage).assetName, AppAssets.yayaSkillsBanner);
    expect(banner.fit, BoxFit.contain);
    expect(repository.loadSkillsCalls, 1);
    expect(find.text('今日简报'), findsOneWidget);
    expect(find.text('智能记账'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('天气提醒'),
      240,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('天气提醒'), findsOneWidget);
    expect(find.text('赊账汇总'), findsNothing);
  });

  test('芽芽主色不是紫色', () {
    expect(AppColors.teal.toARGB32(), isNot(0xFF8559F6));
  });
}

class _YayaCopyRepository extends YayaRepository {
  _YayaCopyRepository() : super(ApiClient());

  @override
  Future<List<ConversationSummary>> loadConversations({int limit = 20}) async {
    return const [
      ConversationSummary(
        id: 1,
        sessionId: 's1',
        title: '检测到工具调用格式异常，正在重新处理，请稍等',
        preview: '睢宁县未来3天天气如下：6月8日多云转阴，建议避开午后高温安排作业。',
        status: 'active',
        category: '对话',
      ),
    ];
  }

  @override
  Future<List<ConversationMessage>> loadMessages(String sessionId) async {
    return const [
      ConversationMessage(
        id: 1,
        role: 'assistant',
        content: '建议傍晚浇水',
      ),
    ];
  }

  @override
  Stream<YayaStreamEvent> streamMessage(
    String message, {
    int? cycleId,
    String? sessionId,
  }) async* {
    yield const YayaStreamEvent(content: '收到');
    yield const YayaStreamEvent(done: true);
  }
}

class _SkillsYayaRepository extends _YayaCopyRepository {
  int loadSkillsCalls = 0;

  @override
  Future<List<YayaSkill>> loadSkills() async {
    loadSkillsCalls += 1;
    return const [
      YayaSkill(
        key: 'get_farm_status',
        title: '今日简报',
        description: '查看今天待办与风险',
        category: '推荐',
        icon: 'clipboard-list',
        iconColor: 'blue',
        recommended: true,
        enabled: true,
      ),
      YayaSkill(
        key: 'create_cost_record',
        title: '智能记账',
        description: '一句话生成账本记录',
        category: '记录',
        icon: 'receipt-yuan',
        iconColor: 'green',
        recommended: true,
        enabled: true,
      ),
      YayaSkill(
        key: 'get_weather_forecast',
        title: '天气提醒',
        description: '查看天气和风险',
        category: '推荐',
        icon: 'cloud-sun',
        iconColor: 'amber',
        recommended: false,
        enabled: true,
      ),
    ];
  }
}

class _MarkdownYayaRepository extends YayaRepository {
  _MarkdownYayaRepository() : super(ApiClient());

  @override
  Future<List<ConversationSummary>> loadConversations({int limit = 20}) async {
    return const [];
  }

  @override
  Stream<YayaStreamEvent> streamMessage(
    String message, {
    int? cycleId,
    String? sessionId,
  }) async* {
    yield const YayaStreamEvent(content: '**普通赊账**：130.00 元');
    yield const YayaStreamEvent(done: true);
  }
}

class _TrackingYayaRepository extends YayaRepository {
  _TrackingYayaRepository() : super(ApiClient());

  final List<String> sentMessages = [];

  @override
  Future<List<ConversationSummary>> loadConversations({int limit = 20}) async {
    return const [];
  }

  @override
  Stream<YayaStreamEvent> streamMessage(
    String message, {
    int? cycleId,
    String? sessionId,
  }) async* {
    sentMessages.add(message);
    yield const YayaStreamEvent(content: '收到');
    yield const YayaStreamEvent(done: true);
  }
}

class _PendingYayaRepository extends YayaRepository {
  _PendingYayaRepository() : super(ApiClient());

  final List<String> sentMessages = [];

  @override
  Future<List<ConversationSummary>> loadConversations({int limit = 20}) async {
    return const [];
  }

  @override
  Stream<YayaStreamEvent> streamMessage(
    String message, {
    int? cycleId,
    String? sessionId,
  }) async* {
    sentMessages.add(message);
    if (message == '确认') {
      yield const YayaStreamEvent(content: '已执行');
      yield const YayaStreamEvent(done: true);
      return;
    }
    yield const YayaStreamEvent(
      content: '🌱 确认创建茬口：大豆 理解：您说的是「我想种大豆」 确认吗？',
      pendingAction: {
        'action_id': 'a1',
        'skill_name': 'create_crop_cycle',
        'params': {'作物': '大豆'},
        'context': {
          'original_input': '我想种大豆',
          'notes': ['理解：您说的是「我想种大豆」'],
        },
      },
    );
    yield const YayaStreamEvent(done: true);
  }
}
