# Mobile API Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Flutter 移动端接入 `http://localhost:8099` 后端，完成认证会话、个人页、芽芽、首页/账本只读数据和记录流保存闭环。

**Architecture:** 先建立可恢复的认证会话层，再在页面内使用轻量 controller/view model 绑定真实数据。Repository 继续负责后端路径调用，页面只消费 view model，不显示 API 路径。记录流按后端 `scene/draft/missing_fields/warnings` 保守映射保存目标，无法安全映射时停在确认/编辑页。

**Tech Stack:** Flutter、Dart、Dio、flutter_secure_storage、flutter_test、现有 Flutter widget/golden tests。

---

## 文件结构

- Create: `mobile-app/lib/data/session/session_store.dart`
  - 负责 token 持久化、读取、清除。
- Create: `mobile-app/lib/data/session/app_session.dart`
  - 负责组合 `ApiClient`、`AuthRepository` 和 `SessionStore`，提供登录、注册、恢复、退出。
- Create: `mobile-app/lib/shared/state/async_view_state.dart`
  - 页面通用 loading/data/empty/error 状态。
- Modify: `mobile-app/lib/data/api/api_client.dart`
  - 增加 `baseUrl` 暴露、`health()`、统一错误文案辅助方法。
- Modify: `mobile-app/lib/app/app_dependencies.dart`
  - 扩展依赖接口，暴露 session、repository 和退出登录。
- Modify: `mobile-app/lib/features/auth/auth_flow.dart`
  - 启动时恢复 token，登录失败不放行进入主应用。
- Modify: `mobile-app/lib/features/shell/app_shell.dart`
  - 将 dependencies 传入首页、芽芽、账本、我的、记录页。
- Create: `mobile-app/lib/features/profile/profile_controller.dart`
  - 加载 profile/settings/version 并映射页面模型。
- Modify: `mobile-app/lib/features/profile/profile_screen.dart`
  - 展示真实个人资料、设置、版本、退出登录。
- Create: `mobile-app/lib/features/yaya/yaya_controller.dart`
  - 非流式聊天、历史会话、消息加载。
- Modify: `mobile-app/lib/features/yaya/yaya_screen.dart`
  - 接入真实发送、历史抽屉和会话消息。
- Create: `mobile-app/lib/features/home/home_controller.dart`
  - 加载每日建议、天气、作业单、未结人工摘要。
- Modify: `mobile-app/lib/features/home/home_screen.dart`
  - 真实数据绑定和空/错/加载状态。
- Create: `mobile-app/lib/features/billing/billing_controller.dart`
  - 加载成本列表、年度汇总、欠款提醒。
- Modify: `mobile-app/lib/features/billing/billing_screen.dart`
  - 真实账本只读数据绑定。
- Create: `mobile-app/lib/features/record_flow/record_flow_controller.dart`
  - smart-fill 解析、draft 映射、保存目标选择。
- Modify: `mobile-app/lib/features/workbench/workbench_screen.dart`
  - 将 AI 记录入口改为提交自然语言后进入确认页。
- Modify: `mobile-app/lib/features/record_flow/record_ai_confirm_screen.dart`
  - 使用解析结果展示确认页。
- Modify: `mobile-app/lib/features/record_flow/record_manual_edit_screen.dart`
  - 支持编辑 draft 必填字段。
- Modify: `mobile-app/lib/features/record_flow/record_save_success_screen.dart`
  - 展示真实保存结果。
- Modify: `mobile-app/pubspec.yaml`
  - 增加 `flutter_secure_storage` 依赖。
- Modify/Create tests under `mobile-app/test/...`
  - 覆盖 session、auth、profile、Yaya、home、billing、record flow、API 路径隐藏和本地后端联通。

---

### Task 1: 后端联通和 Session 地基

**Files:**
- Modify: `mobile-app/pubspec.yaml`
- Modify: `mobile-app/lib/data/api/api_client.dart`
- Create: `mobile-app/lib/data/session/session_store.dart`
- Create: `mobile-app/lib/data/session/app_session.dart`
- Test: `mobile-app/test/data/session/app_session_test.dart`
- Test: `mobile-app/test/data/api/backend_connectivity_test.dart`

- [ ] **Step 1: 增加 token 存储依赖**

Run:

```bash
cd mobile-app && flutter pub add flutter_secure_storage
```

Expected: `pubspec.yaml` 出现 `flutter_secure_storage`，`flutter pub get` 成功。

- [ ] **Step 2: 编写 session 失败测试**

Create `mobile-app/test/data/session/app_session_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/session/app_session.dart';
import 'package:farm_manager_app/data/session/session_store.dart';
import 'package:flutter_test/flutter_test.dart';

import '../repositories/app_api_integration_test.dart'
    show RecordingAdapter, tokenResponse;

void main() {
  test('登录成功后保存 token 并写入 Authorization header', () async {
    final store = MemorySessionStore();
    final adapter = RecordingAdapter({'/auth/login': tokenResponse});
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final client = ApiClient(dio: dio);
    final session = AppSession(client: client, store: store);

    await session.login(phone: '13800138000', password: 'password');

    expect(await store.readToken(), 'token-1');
    expect(client.dio.options.headers['Authorization'], 'Bearer token-1');
  });

  test('启动恢复 token 后可直接带鉴权请求', () async {
    final store = MemorySessionStore(initialToken: 'restored-token');
    final client = ApiClient(
      dio: Dio(BaseOptions(baseUrl: 'http://localhost:8099')),
    );
    final session = AppSession(client: client, store: store);

    final restored = await session.restore();

    expect(restored, true);
    expect(client.dio.options.headers['Authorization'], 'Bearer restored-token');
  });

  test('退出登录会清除本地 token 和请求头', () async {
    final store = MemorySessionStore(initialToken: 'token-1');
    final client = ApiClient(
      dio: Dio(BaseOptions(baseUrl: 'http://localhost:8099')),
    )..setAccessToken('token-1');
    final session = AppSession(client: client, store: store);

    await session.logout();

    expect(await store.readToken(), isNull);
    expect(client.dio.options.headers.containsKey('Authorization'), false);
  });
}
```

- [ ] **Step 3: 运行 session 测试确认失败**

Run:

```bash
cd mobile-app && flutter test test/data/session/app_session_test.dart
```

Expected: FAIL，提示找不到 `AppSession` 或 `SessionStore`。

- [ ] **Step 4: 实现 token 存储**

Create `mobile-app/lib/data/session/session_store.dart`:

```dart
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract class SessionStore {
  Future<String?> readToken();
  Future<void> writeToken(String token);
  Future<void> clearToken();
}

class SecureSessionStore implements SessionStore {
  const SecureSessionStore({
    FlutterSecureStorage storage = const FlutterSecureStorage(),
  }) : _storage = storage;

  static const _tokenKey = 'farm_manager.access_token';

  final FlutterSecureStorage _storage;

  @override
  Future<String?> readToken() => _storage.read(key: _tokenKey);

  @override
  Future<void> writeToken(String token) {
    return _storage.write(key: _tokenKey, value: token);
  }

  @override
  Future<void> clearToken() => _storage.delete(key: _tokenKey);
}

class MemorySessionStore implements SessionStore {
  MemorySessionStore({String? initialToken}) : _token = initialToken;

  String? _token;

  @override
  Future<String?> readToken() async => _token;

  @override
  Future<void> writeToken(String token) async {
    _token = token;
  }

  @override
  Future<void> clearToken() async {
    _token = null;
  }
}
```

- [ ] **Step 5: 实现会话协调器**

Create `mobile-app/lib/data/session/app_session.dart`:

```dart
import '../api/api_client.dart';
import '../api/api_models.dart';
import '../repositories/auth_repository.dart';
import 'session_store.dart';

class AppSession {
  AppSession({
    required this.client,
    required this.store,
    AuthRepository? auth,
  }) : auth = auth ?? AuthRepository(client);

  final ApiClient client;
  final SessionStore store;
  final AuthRepository auth;

  Future<bool> restore() async {
    final token = await store.readToken();
    client.setAccessToken(token);
    return token != null && token.isNotEmpty;
  }

  Future<AuthSession> login({
    required String phone,
    required String password,
  }) async {
    final session = await auth.login(phone: phone, password: password);
    await store.writeToken(session.token);
    client.setAccessToken(session.token);
    return session;
  }

  Future<AuthSession> register({
    required String phone,
    required String password,
    required String nickname,
  }) async {
    final session = await auth.register(
      phone: phone,
      password: password,
      nickname: nickname,
    );
    await store.writeToken(session.token);
    client.setAccessToken(session.token);
    return session;
  }

  Future<void> logout() async {
    await store.clearToken();
    client.setAccessToken(null);
  }
}
```

- [ ] **Step 6: 增加 ApiClient 联通辅助**

Modify `mobile-app/lib/data/api/api_client.dart`:

```dart
class ApiClient {
  ApiClient({Dio? dio})
      : dio = dio ??
            Dio(BaseOptions(
              baseUrl: const String.fromEnvironment(
                'API_BASE_URL',
                defaultValue: 'http://localhost:8099',
              ),
            ));

  final Dio dio;

  String get baseUrl => dio.options.baseUrl;

  Future<bool> health() async {
    final response = await dio.get('/health');
    return response.statusCode != null &&
        response.statusCode! >= 200 &&
        response.statusCode! < 300;
  }

  static String userMessageFor(Object error) {
    if (error is DioException && error.response?.statusCode == 401) {
      return '登录已过期，请重新登录';
    }
    if (error is DioException && error.type == DioExceptionType.connectionError) {
      return '无法连接服务器，请确认后端已启动';
    }
    return '请求失败，请稍后重试';
  }
}
```

Keep the existing methods in the file and add the new members without removing
`getMap`, `postMap`, `putMap`, `patchMap`, `asMap`, or `asList`.

- [ ] **Step 7: 编写本地后端联通测试**

Create `mobile-app/test/data/api/backend_connectivity_test.dart`:

```dart
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('默认后端地址指向 localhost:8099', () {
    final client = ApiClient();
    expect(client.baseUrl, 'http://localhost:8099');
  });
}
```

- [ ] **Step 8: 运行 session 和 api 测试**

Run:

```bash
cd mobile-app && flutter test test/data/session/app_session_test.dart test/data/api/backend_connectivity_test.dart
```

Expected: PASS。

- [ ] **Step 9: 手动检查 localhost:8099 健康接口**

Run:

```bash
curl -fsS http://localhost:8099/health
```

Expected: 输出包含 `ok`、`healthy` 或 JSON 健康状态；如果连接失败，先启动后端：

```bash
cd backend && poetry run uvicorn app.main:app --host 0.0.0.0 --port 8099
```

- [ ] **Step 10: 提交 Task 1**

Run:

```bash
git add mobile-app/pubspec.yaml mobile-app/pubspec.lock mobile-app/lib/data/api/api_client.dart mobile-app/lib/data/session mobile-app/test/data/session/app_session_test.dart mobile-app/test/data/api/backend_connectivity_test.dart
git commit -m "feat: add mobile session foundation"
```

Expected: commit 成功。

---

### Task 2: AuthFlow 恢复、失败拦截和退出登录

**Files:**
- Modify: `mobile-app/lib/app/app_dependencies.dart`
- Modify: `mobile-app/lib/features/auth/auth_flow.dart`
- Modify: `mobile-app/lib/features/shell/app_shell.dart`
- Modify: `mobile-app/test/support/fake_app_dependencies.dart`
- Modify: `mobile-app/test/features/auth/auth_flow_test.dart`

- [ ] **Step 1: 改写 AuthFlow 测试预期**

Modify `mobile-app/test/features/auth/auth_flow_test.dart`:

```dart
testWidgets('登录接口失败时停留在登录页并展示错误', (tester) async {
  final dependencies = FakeAppDependencies(loginError: Exception('401'));
  await pumpAuthFlow(tester, dependencies: dependencies);

  await tester.tap(find.text('登录'));
  await tester.pumpAndSettle();

  expect(dependencies.loginCalls, 1);
  expect(dependencies.overviewLoads, 0);
  expect(find.text('登录失败，请检查账号或稍后重试'), findsOneWidget);
  expect(find.text('首页'), findsNothing);
});

testWidgets('启动恢复 token 成功时直接进入主应用', (tester) async {
  final dependencies = FakeAppDependencies(restoreResult: true);
  await pumpAuthFlow(tester, dependencies: dependencies);
  await tester.pumpAndSettle();

  expect(dependencies.restoreCalls, 1);
  expect(find.text('首页'), findsWidgets);
  expect(find.text('手机号'), findsNothing);
});

testWidgets('退出登录后回到登录页', (tester) async {
  final dependencies = FakeAppDependencies(restoreResult: true);
  await pumpAuthFlow(tester, dependencies: dependencies);
  await tester.pumpAndSettle();

  await tester.tap(find.text('我的'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('退出登录'));
  await tester.pumpAndSettle();

  expect(dependencies.logoutCalls, 1);
  expect(find.text('手机号'), findsOneWidget);
});
```

Remove the old test named `登录接口失败时仍放行进入主应用方便调试页面`.

- [ ] **Step 2: 运行 AuthFlow 测试确认失败**

Run:

```bash
cd mobile-app && flutter test test/features/auth/auth_flow_test.dart
```

Expected: FAIL，提示 `restoreResult`、`restoreCalls`、`logoutCalls` 或退出入口不存在。

- [ ] **Step 3: 扩展 AppDependencies**

Modify `mobile-app/lib/app/app_dependencies.dart`:

```dart
abstract class AppDependencies {
  Future<bool> restoreSession();
  Future<void> logout();
  Future<void> login({required String phone, required String password});
  Future<void> register({
    required String phone,
    required String password,
    required String nickname,
  });
  Future<void> loadAppOverview();
}
```

In `BackendAppDependencies`, add an `AppSession` field and delegate:

```dart
BackendAppDependencies._(this.client)
    : session = AppSession(client: client, store: const SecureSessionStore()),
      auth = AuthRepository(client),
      profile = ProfileRepository(client),
      dashboard = DashboardRepository(client),
      billing = BillingRepository(client),
      workbench = WorkbenchRepository(client),
      yaya = YayaRepository(client);

final AppSession session;

@override
Future<bool> restoreSession() => session.restore();

@override
Future<void> logout() => session.logout();

@override
Future<void> login({required String phone, required String password}) async {
  await session.login(phone: phone, password: password);
}

@override
Future<void> register({
  required String phone,
  required String password,
  required String nickname,
}) async {
  await session.register(phone: phone, password: password, nickname: nickname);
}
```

Import:

```dart
import '../data/session/app_session.dart';
import '../data/session/session_store.dart';
```

- [ ] **Step 4: 扩展 FakeAppDependencies**

Modify `mobile-app/test/support/fake_app_dependencies.dart`:

```dart
class FakeAppDependencies implements AppDependencies {
  FakeAppDependencies({
    this.loginError,
    this.registerError,
    this.restoreResult = false,
  });

  final Object? loginError;
  final Object? registerError;
  final bool restoreResult;
  int restoreCalls = 0;
  int logoutCalls = 0;
  int loginCalls = 0;
  int registerCalls = 0;
  int overviewLoads = 0;

  @override
  Future<bool> restoreSession() async {
    restoreCalls += 1;
    return restoreResult;
  }

  @override
  Future<void> logout() async {
    logoutCalls += 1;
  }
}
```

Keep the existing login/register/loadAppOverview fields and methods.

- [ ] **Step 5: 修改 AuthFlow 启动恢复逻辑**

Modify `mobile-app/lib/features/auth/auth_flow.dart`:

```dart
enum AuthStep { restoring, login, register, setup, app }

class _AuthFlowState extends State<AuthFlow> {
  late AuthStep step = widget.initialStep == AuthStep.login
      ? AuthStep.restoring
      : widget.initialStep;

  @override
  void initState() {
    super.initState();
    if (step == AuthStep.restoring) {
      _restore();
    }
  }

  Future<void> _restore() async {
    final restored = await widget.dependencies.restoreSession();
    if (!mounted) return;
    setState(() => step = restored ? AuthStep.app : AuthStep.login);
  }
}
```

Update the switch:

```dart
AuthStep.restoring => const Scaffold(
    body: Center(child: CircularProgressIndicator()),
  ),
```

Remove the login callback `try { ... } catch (_) {}` block so failures rethrow
to `LoginScreen`.

- [ ] **Step 6: 将退出登录回调传入 AppShell**

Modify `mobile-app/lib/features/shell/app_shell.dart`:

```dart
const ProfileScreen()
```

becomes:

```dart
ProfileScreen(onLogout: () async {
  await widget.dependencies.logout();
  if (!mounted) return;
  Navigator.of(context).pushAndRemoveUntil(
    MaterialPageRoute<void>(
      builder: (_) => AuthFlow(dependencies: widget.dependencies),
    ),
    (route) => false,
  );
}),
```

Add import:

```dart
import '../auth/auth_flow.dart';
```

- [ ] **Step 7: 给 ProfileScreen 增加退出入口**

Modify `mobile-app/lib/features/profile/profile_screen.dart` constructor:

```dart
class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key, this.onLogout});

  final Future<void> Function()? onLogout;
}
```

Add a button after `_CompleteProfileButton()`:

```dart
if (onLogout != null) ...[
  const SizedBox(height: 12),
  TextButton(
    onPressed: onLogout,
    child: const Text('退出登录'),
  ),
],
```

- [ ] **Step 8: 运行 AuthFlow 测试**

Run:

```bash
cd mobile-app && flutter test test/features/auth/auth_flow_test.dart
```

Expected: PASS。

- [ ] **Step 9: 提交 Task 2**

Run:

```bash
git add mobile-app/lib/app/app_dependencies.dart mobile-app/lib/features/auth/auth_flow.dart mobile-app/lib/features/shell/app_shell.dart mobile-app/lib/features/profile/profile_screen.dart mobile-app/test/support/fake_app_dependencies.dart mobile-app/test/features/auth/auth_flow_test.dart
git commit -m "fix: require valid mobile auth session"
```

Expected: commit 成功。

---

### Task 3: 个人页真实数据绑定

**Files:**
- Create: `mobile-app/lib/features/profile/profile_controller.dart`
- Modify: `mobile-app/lib/features/profile/profile_screen.dart`
- Test: `mobile-app/test/features/profile/profile_controller_test.dart`
- Modify: `mobile-app/test/features/profile/profile_screen_test.dart`

- [ ] **Step 1: 编写 profile controller 测试**

Create `mobile-app/test/features/profile/profile_controller_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/features/profile/profile_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../data/repositories/app_api_integration_test.dart'
    show RecordingAdapter, userResponse, settingsResponse, versionResponse;

void main() {
  test('加载个人资料、设置和版本并映射为页面模型', () async {
    final adapter = RecordingAdapter({
      '/auth/me': userResponse,
      '/settings': settingsResponse,
      '/api/app/version': versionResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = ProfileController(
      repository: ProfileRepository(ApiClient(dio: dio)),
    );

    final model = await controller.load();

    expect(model.nickname, '农友');
    expect(model.phone, '13800138000');
    expect(model.city, '寿光');
    expect(model.weatherCity, '寿光');
    expect(model.versionLabel, '版本 0.1.0');
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd mobile-app && flutter test test/features/profile/profile_controller_test.dart
```

Expected: FAIL，提示找不到 `ProfileController`。

- [ ] **Step 3: 实现 ProfileController**

Create `mobile-app/lib/features/profile/profile_controller.dart`:

```dart
import '../../data/repositories/profile_repository.dart';

class ProfileController {
  ProfileController({required this.repository});

  final ProfileRepository repository;

  Future<ProfileViewModel> load() async {
    final results = await Future.wait([
      repository.getProfile(),
      repository.getSettings(),
      repository.checkVersion(),
    ]);
    final user = results[0] as dynamic;
    final settings = results[1] as dynamic;
    final version = results[2] as dynamic;
    final city = settings.defaultCity ?? '未设置';
    return ProfileViewModel(
      nickname: user.nickname.isEmpty ? '农友' : user.nickname,
      phone: user.phone.isEmpty ? '未绑定手机号' : user.phone,
      role: user.role.isEmpty ? '用户' : user.role,
      status: user.status.isEmpty ? '未知' : user.status,
      city: city,
      weatherCity: city,
      versionLabel: version.latestVersion.isEmpty
          ? '版本未知'
          : '版本 ${version.latestVersion}',
    );
  }
}

class ProfileViewModel {
  const ProfileViewModel({
    required this.nickname,
    required this.phone,
    required this.role,
    required this.status,
    required this.city,
    required this.weatherCity,
    required this.versionLabel,
  });

  final String nickname;
  final String phone;
  final String role;
  final String status;
  final String city;
  final String weatherCity;
  final String versionLabel;
}
```

- [ ] **Step 4: 修改 ProfileScreen 接收 repository 并展示数据**

Modify constructor:

```dart
class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    super.key,
    required this.repository,
    this.onLogout,
  });

  final ProfileRepository repository;
  final Future<void> Function()? onLogout;
}
```

In state, load controller:

```dart
late final controller = ProfileController(repository: widget.repository);
late final Future<ProfileViewModel> profileFuture = controller.load();
```

Render `FutureBuilder<ProfileViewModel>` and pass model to cards:

```dart
FutureBuilder<ProfileViewModel>(
  future: profileFuture,
  builder: (context, snapshot) {
    if (snapshot.connectionState != ConnectionState.done) {
      return const Center(child: CircularProgressIndicator());
    }
    if (snapshot.hasError) {
      return const Text('个人资料加载失败，请稍后重试');
    }
    final model = snapshot.data!;
    return ReferencePage(
      headerTrailing: const HeaderIconButton(icon: LucideIcons.settings),
      children: [
        const SizedBox(height: 14),
        _ProfileCard(model: model),
        const SizedBox(height: 14),
        _LocationWeatherCard(model: model),
        const SizedBox(height: 14),
        const _AiPreferenceCard(),
        const SizedBox(height: 14),
        _SystemSettingsCard(model: model),
        const SizedBox(height: 28),
        const _CompleteProfileButton(),
        if (widget.onLogout != null) ...[
          const SizedBox(height: 12),
          TextButton(onPressed: widget.onLogout, child: const Text('退出登录')),
        ],
      ],
    );
  },
)
```

Keep current layout, replace hard-coded city/version/phone/nickname values with
`ProfileViewModel` fields.

- [ ] **Step 5: 更新 AppShell 传入 ProfileRepository**

Modify `mobile-app/lib/features/shell/app_shell.dart`:

```dart
ProfileScreen(
  repository: widget.dependencies.profile,
  onLogout: () async {
    await widget.dependencies.logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(
        builder: (_) => AuthFlow(dependencies: widget.dependencies),
      ),
      (route) => false,
    );
  },
),
```

If `AppDependencies` does not yet expose `profile`, add:

```dart
ProfileRepository get profile;
```

and implement it on `BackendAppDependencies` and `FakeAppDependencies`.

- [ ] **Step 6: 运行个人页测试**

Run:

```bash
cd mobile-app && flutter test test/features/profile/profile_controller_test.dart test/features/profile/profile_screen_test.dart
```

Expected: PASS。

- [ ] **Step 7: 提交 Task 3**

Run:

```bash
git add mobile-app/lib/features/profile mobile-app/lib/features/shell/app_shell.dart mobile-app/lib/app/app_dependencies.dart mobile-app/test/features/profile mobile-app/test/support/fake_app_dependencies.dart
git commit -m "feat: bind mobile profile to backend"
```

Expected: commit 成功。

---

### Task 4: 芽芽非流式聊天和历史会话

**Files:**
- Create: `mobile-app/lib/features/yaya/yaya_controller.dart`
- Modify: `mobile-app/lib/features/yaya/yaya_screen.dart`
- Modify: `mobile-app/lib/features/shell/app_shell.dart`
- Test: `mobile-app/test/features/yaya/yaya_controller_test.dart`
- Modify: `mobile-app/test/features/yaya/yaya_copy_test.dart`

- [ ] **Step 1: 编写 YayaController 测试**

Create `mobile-app/test/features/yaya/yaya_controller_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/yaya_repository.dart';
import 'package:farm_manager_app/features/yaya/yaya_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../data/repositories/app_api_integration_test.dart'
    show RecordingAdapter, conversationResponse, messageResponse;

void main() {
  test('发送消息会追加用户消息和芽芽回复', () async {
    final adapter = RecordingAdapter({
      '/agent/chat': {'reply': '建议傍晚浇水'},
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = YayaController(
      repository: YayaRepository(ApiClient(dio: dio)),
    );

    await controller.send('今天浇水吗');

    expect(controller.messages.map((item) => item.content), [
      '今天浇水吗',
      '建议傍晚浇水',
    ]);
    expect(adapter.find('POST', '/agent/chat').data, {
      'message': '今天浇水吗',
    });
  });

  test('加载历史会话和消息', () async {
    final adapter = RecordingAdapter({
      '/agent/conversations': [conversationResponse],
      '/agent/conversations/s1/messages': [messageResponse],
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = YayaController(
      repository: YayaRepository(ApiClient(dio: dio)),
    );

    await controller.loadConversations();
    await controller.openConversation('s1');

    expect(controller.conversations.single.title, '问答');
    expect(controller.messages.single.content, '建议傍晚浇水');
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd mobile-app && flutter test test/features/yaya/yaya_controller_test.dart
```

Expected: FAIL，提示找不到 `YayaController`。

- [ ] **Step 3: 实现 YayaController**

Create `mobile-app/lib/features/yaya/yaya_controller.dart`:

```dart
import 'package:flutter/foundation.dart';

import '../../data/api/api_models.dart';
import '../../data/repositories/yaya_repository.dart';

class YayaController extends ChangeNotifier {
  YayaController({required this.repository});

  final YayaRepository repository;
  final List<YayaMessageViewModel> messages = [];
  final List<ConversationSummary> conversations = [];
  bool sending = false;
  String? errorMessage;
  String? activeSessionId;

  Future<void> loadConversations() async {
    conversations
      ..clear()
      ..addAll(await repository.loadConversations());
    notifyListeners();
  }

  Future<void> openConversation(String sessionId) async {
    activeSessionId = sessionId;
    final loaded = await repository.loadMessages(sessionId);
    messages
      ..clear()
      ..addAll(loaded.map(YayaMessageViewModel.fromConversation));
    notifyListeners();
  }

  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || sending) return;
    sending = true;
    errorMessage = null;
    messages.add(YayaMessageViewModel.user(trimmed));
    notifyListeners();
    try {
      final reply = await repository.sendMessage(
        trimmed,
        sessionId: activeSessionId,
      );
      messages.add(YayaMessageViewModel.assistant(reply.reply));
    } catch (_) {
      errorMessage = '芽芽暂时没有回应，请稍后再试';
    } finally {
      sending = false;
      notifyListeners();
    }
  }
}

class YayaMessageViewModel {
  const YayaMessageViewModel({
    required this.role,
    required this.content,
  });

  factory YayaMessageViewModel.user(String content) {
    return YayaMessageViewModel(role: 'user', content: content);
  }

  factory YayaMessageViewModel.assistant(String content) {
    return YayaMessageViewModel(role: 'assistant', content: content);
  }

  factory YayaMessageViewModel.fromConversation(ConversationMessage message) {
    return YayaMessageViewModel(role: message.role, content: message.content);
  }

  final String role;
  final String content;
}
```

- [ ] **Step 4: 修改 YayaScreen 接收 repository**

Modify constructor:

```dart
class YayaScreen extends StatefulWidget {
  const YayaScreen({super.key, required this.repository});

  final YayaRepository repository;
}
```

In state:

```dart
late final YayaController controller =
    YayaController(repository: widget.repository);

@override
void initState() {
  super.initState();
  controller.loadConversations();
}

@override
void dispose() {
  controller.dispose();
  super.dispose();
}
```

Pass `controller` to `_YayaHomePage` and `YayaHistoryDrawer`.

- [ ] **Step 5: 将输入框接入发送**

Change `AssistantInputBar` to accept:

```dart
const AssistantInputBar({
  super.key,
  required this.onSubmit,
  this.sending = false,
});

final Future<void> Function(String text) onSubmit;
final bool sending;
```

Use a `TextEditingController`, call `await onSubmit(controller.text)`, then
clear text when submit completes without error.

- [ ] **Step 6: 历史抽屉使用真实会话**

Change `YayaHistoryDrawer` constructor:

```dart
const YayaHistoryDrawer({
  super.key,
  required this.onClose,
  required this.onSkillsPressed,
  required this.conversations,
  required this.onConversationTap,
});

final List<ConversationSummary> conversations;
final ValueChanged<String> onConversationTap;
```

Render empty state text `暂无历史会话` when list is empty. Render each item with
`title`, `preview`, `category`, and call `onConversationTap(item.sessionId)`.

- [ ] **Step 7: AppShell 传入 YayaRepository**

Modify `mobile-app/lib/features/shell/app_shell.dart`:

```dart
YayaScreen(repository: widget.dependencies.yaya),
```

Expose `YayaRepository get yaya;` from `AppDependencies` and implement in fake.

- [ ] **Step 8: 运行芽芽测试**

Run:

```bash
cd mobile-app && flutter test test/features/yaya/yaya_controller_test.dart test/features/yaya/yaya_copy_test.dart
```

Expected: PASS。

- [ ] **Step 9: 提交 Task 4**

Run:

```bash
git add mobile-app/lib/features/yaya mobile-app/lib/features/shell/app_shell.dart mobile-app/lib/app/app_dependencies.dart mobile-app/test/features/yaya mobile-app/test/support/fake_app_dependencies.dart
git commit -m "feat: connect yaya chat to backend"
```

Expected: commit 成功。

---

### Task 5: 首页和账本只读数据绑定

**Files:**
- Create: `mobile-app/lib/features/home/home_controller.dart`
- Modify: `mobile-app/lib/features/home/home_screen.dart`
- Create: `mobile-app/lib/features/billing/billing_controller.dart`
- Modify: `mobile-app/lib/features/billing/billing_screen.dart`
- Modify: `mobile-app/lib/features/shell/app_shell.dart`
- Test: `mobile-app/test/features/home/home_controller_test.dart`
- Test: `mobile-app/test/features/billing/billing_controller_test.dart`

- [ ] **Step 1: 编写首页 controller 测试**

Create `mobile-app/test/features/home/home_controller_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/dashboard_repository.dart';
import 'package:farm_manager_app/features/home/home_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../data/repositories/app_api_integration_test.dart'
    show RecordingAdapter, dailyAdviceResponse, weatherResponse,
         paginatedWorkOrdersResponse, unsettledLaborSummaryResponse;

void main() {
  test('首页模型整合建议、天气、作业和未结人工', () async {
    final adapter = RecordingAdapter({
      '/agent/daily': dailyAdviceResponse,
      '/weather/forecast': weatherResponse,
      '/planting/work-orders': paginatedWorkOrdersResponse,
      '/planting/labor/unsettled-summary': unsettledLaborSummaryResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = HomeController(
      repository: DashboardRepository(ApiClient(dio: dio)),
    );

    final model = await controller.load();

    expect(model.advicePreview, '注意控水');
    expect(model.weatherLabel, isNotEmpty);
    expect(model.workOrderCount, greaterThanOrEqualTo(0));
    expect(model.unsettledLaborLabel, isNotEmpty);
  });
}
```

- [ ] **Step 2: 编写账本 controller 测试**

Create `mobile-app/test/features/billing/billing_controller_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/features/billing/billing_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../data/repositories/app_api_integration_test.dart'
    show RecordingAdapter, paginatedCostsResponse, yearlySummaryResponse,
         debtsResponse;

void main() {
  test('账本模型整合汇总、最近交易和欠款提醒', () async {
    final adapter = RecordingAdapter({
      '/costs': paginatedCostsResponse,
      '/costs/summary/2026': yearlySummaryResponse,
      '/debts': debtsResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = BillingController(
      repository: BillingRepository(ApiClient(dio: dio)),
      year: 2026,
    );

    final model = await controller.load();

    expect(model.transactions, isNotEmpty);
    expect(model.summaryLabel, isNotEmpty);
    expect(model.receivableLabel, isNotEmpty);
  });
}
```

- [ ] **Step 3: 运行 controller 测试确认失败**

Run:

```bash
cd mobile-app && flutter test test/features/home/home_controller_test.dart test/features/billing/billing_controller_test.dart
```

Expected: FAIL，提示 controller 不存在。

- [ ] **Step 4: 实现 HomeController**

Create `mobile-app/lib/features/home/home_controller.dart`:

```dart
import '../../data/repositories/dashboard_repository.dart';

class HomeController {
  HomeController({required this.repository});

  final DashboardRepository repository;

  Future<HomeViewModel> load() async {
    final results = await Future.wait([
      repository.getDailyAdvice(),
      repository.getForecast(),
      repository.client.getMap('/planting/work-orders'),
      repository.getUnsettledLaborSummary(),
    ]);
    final advice = results[0] as dynamic;
    final weather = results[1] as Map<String, dynamic>;
    final workOrders = results[2] as Map<String, dynamic>;
    final labor = results[3] as Map<String, dynamic>;
    return HomeViewModel(
      advicePreview: advice.preview.isEmpty ? advice.advice : advice.preview,
      weatherLabel: _firstText(weather, ['summary', 'text', 'weather', 'location']),
      workOrderCount: (workOrders['total'] as num?)?.toInt() ??
          (workOrders['items'] as List<dynamic>? ?? []).length,
      unsettledLaborLabel: _firstText(
        labor,
        ['summary', 'total_amount', 'amount', 'unsettled_amount'],
      ),
    );
  }

  String _firstText(Map<String, dynamic> json, List<String> keys) {
    for (final key in keys) {
      final value = json[key];
      if (value != null && '$value'.isNotEmpty) return '$value';
    }
    return '暂无数据';
  }
}

class HomeViewModel {
  const HomeViewModel({
    required this.advicePreview,
    required this.weatherLabel,
    required this.workOrderCount,
    required this.unsettledLaborLabel,
  });

  final String advicePreview;
  final String weatherLabel;
  final int workOrderCount;
  final String unsettledLaborLabel;
}
```

- [ ] **Step 5: 实现 BillingController**

Create `mobile-app/lib/features/billing/billing_controller.dart`:

```dart
import '../../data/api/api_models.dart';
import '../../data/repositories/billing_repository.dart';

class BillingController {
  BillingController({required this.repository, required this.year});

  final BillingRepository repository;
  final int year;

  Future<BillingViewModel> load() async {
    final results = await Future.wait([
      repository.listCosts(size: 10),
      repository.getYearlySummary(year),
      repository.listDebts(size: 10),
    ]);
    final costs = results[0] as PageResult<ApiRecord>;
    final summary = results[1] as Map<String, dynamic>;
    final debts = results[2] as Map<String, dynamic>;
    return BillingViewModel(
      transactions: costs.items.map(BillingTransactionViewModel.fromRecord).toList(),
      summaryLabel: _money(summary['net_profit'] ?? summary['balance'] ?? summary['total']),
      receivableLabel: _money(debts['total_amount'] ?? debts['amount'] ?? debts['total']),
    );
  }

  String _money(Object? value) {
    if (value == null) return '¥0';
    return '¥$value';
  }
}

class BillingViewModel {
  const BillingViewModel({
    required this.transactions,
    required this.summaryLabel,
    required this.receivableLabel,
  });

  final List<BillingTransactionViewModel> transactions;
  final String summaryLabel;
  final String receivableLabel;
}

class BillingTransactionViewModel {
  const BillingTransactionViewModel({
    required this.title,
    required this.subtitle,
    required this.amount,
  });

  factory BillingTransactionViewModel.fromRecord(ApiRecord record) {
    final json = record.json;
    return BillingTransactionViewModel(
      title: '${json['category'] ?? json['name'] ?? json['title'] ?? '未命名交易'}',
      subtitle: '${json['date'] ?? json['created_at'] ?? '未记录日期'}',
      amount: '¥${json['amount'] ?? 0}',
    );
  }

  final String title;
  final String subtitle;
  final String amount;
}
```

- [ ] **Step 6: 页面接入 FutureBuilder**

Modify `HomeScreen` and `BillingScreen` constructors to accept repositories:

```dart
const HomeScreen({super.key, required this.repository});
final DashboardRepository repository;

const BillingScreen({super.key, required this.repository});
final BillingRepository repository;
```

Use `FutureBuilder` to render:

- loading: `CircularProgressIndicator`.
- error: `Text('数据加载失败，请稍后重试')`.
- data: existing static card layout with text values replaced by view model
  fields.
- empty list: `Text('暂无记录')`.

- [ ] **Step 7: AppShell 传入 repository**

Modify `mobile-app/lib/features/shell/app_shell.dart`:

```dart
HomeScreen(repository: widget.dependencies.dashboard),
BillingScreen(repository: widget.dependencies.billing),
```

Expose `DashboardRepository get dashboard;` and `BillingRepository get billing;`
from `AppDependencies` and fake dependencies.

- [ ] **Step 8: 运行首页和账本测试**

Run:

```bash
cd mobile-app && flutter test test/features/home test/features/billing
```

Expected: PASS。

- [ ] **Step 9: 提交 Task 5**

Run:

```bash
git add mobile-app/lib/features/home mobile-app/lib/features/billing mobile-app/lib/features/shell/app_shell.dart mobile-app/lib/app/app_dependencies.dart mobile-app/test/features/home mobile-app/test/features/billing mobile-app/test/support/fake_app_dependencies.dart
git commit -m "feat: bind mobile dashboard and billing data"
```

Expected: commit 成功。

---

### Task 6: 记录流 smart-fill 解析和保守保存

**Files:**
- Create: `mobile-app/lib/features/record_flow/record_flow_controller.dart`
- Modify: `mobile-app/lib/features/workbench/workbench_screen.dart`
- Modify: `mobile-app/lib/features/record_flow/record_ai_confirm_screen.dart`
- Modify: `mobile-app/lib/features/record_flow/record_manual_edit_screen.dart`
- Modify: `mobile-app/lib/features/record_flow/record_save_success_screen.dart`
- Modify: `mobile-app/lib/features/shell/app_shell.dart`
- Test: `mobile-app/test/features/record_flow/record_flow_controller_test.dart`
- Modify: `mobile-app/test/features/record_flow/record_flow_test.dart`

- [ ] **Step 1: 编写 record flow controller 测试**

Create `mobile-app/test/features/record_flow/record_flow_controller_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/workbench_repository.dart';
import 'package:farm_manager_app/features/record_flow/record_flow_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../data/repositories/app_api_integration_test.dart'
    show RecordingAdapter, smartFillParseResponse, costRecordResponse,
         logResponse, workOrderResponse, wageResponse;

void main() {
  test('smart-fill 解析结果映射到确认模型', () async {
    final adapter = RecordingAdapter({
      '/smart-fill/parse': smartFillParseResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final client = ApiClient(dio: dio);
    final controller = RecordFlowController(
      workbench: WorkbenchRepository(client),
      billing: BillingRepository(client),
    );

    final draft = await controller.parse('今天买肥料 200');

    expect(draft.originalText, '今天买肥料 200');
    expect(draft.scene, isNotEmpty);
    expect(adapter.find('POST', '/smart-fill/parse').data['text'], '今天买肥料 200');
  });

  test('成本场景保存到 costs', () async {
    final adapter = RecordingAdapter({
      'POST /costs': costRecordResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final client = ApiClient(dio: dio);
    final controller = RecordFlowController(
      workbench: WorkbenchRepository(client),
      billing: BillingRepository(client),
    );

    await controller.save(RecordDraft(
      scene: 'ledger.record',
      originalText: '买肥料 200',
      fields: {'amount': 200, 'category': '肥料', 'record_type': 'expense'},
      missingFields: const [],
      warnings: const [],
    ));

    expect(adapter.find('POST', '/costs').data, {
      'amount': 200,
      'category': '肥料',
      'record_type': 'expense',
    });
  });

  test('未知场景不会伪造保存目标', () async {
    final controller = RecordFlowController(
      workbench: WorkbenchRepository(ApiClient()),
      billing: BillingRepository(ApiClient()),
    );

    expect(
      () => controller.save(RecordDraft(
        scene: 'unknown',
        originalText: '随便记一下',
        fields: const {},
        missingFields: const [],
        warnings: const [],
      )),
      throwsA(isA<UnsupportedRecordSceneException>()),
    );
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd mobile-app && flutter test test/features/record_flow/record_flow_controller_test.dart
```

Expected: FAIL，提示找不到 `RecordFlowController`。

- [ ] **Step 3: 实现 RecordFlowController**

Create `mobile-app/lib/features/record_flow/record_flow_controller.dart`:

```dart
import '../../data/repositories/billing_repository.dart';
import '../../data/repositories/workbench_repository.dart';

class RecordFlowController {
  RecordFlowController({
    required this.workbench,
    required this.billing,
  });

  final WorkbenchRepository workbench;
  final BillingRepository billing;

  Future<RecordDraft> parse(String text) async {
    final result = await workbench.parseSmartFill(
      scene: 'auto.record',
      text: text,
      idempotencyKey: DateTime.now().microsecondsSinceEpoch.toString(),
    );
    return RecordDraft(
      scene: result.scene,
      originalText: text,
      fields: result.draft,
      missingFields: result.missingFields,
      warnings: result.warnings,
    );
  }

  Future<RecordSaveResult> save(RecordDraft draft) async {
    if (draft.missingFields.isNotEmpty) {
      throw MissingRecordFieldsException(draft.missingFields);
    }
    if (_isCostScene(draft.scene)) {
      final record = await billing.createCost(draft.fields);
      return RecordSaveResult(label: '已同步到账本', json: record.json);
    }
    if (_isDebtScene(draft.scene)) {
      final record = await billing.createDebt(draft.fields);
      return RecordSaveResult(label: '已保存赊账记录', json: record.json);
    }
    if (_isLogScene(draft.scene)) {
      final record = await workbench.createLog(draft.fields);
      return RecordSaveResult(label: '已同步到农事记录', json: record.json);
    }
    if (_isWorkOrderScene(draft.scene)) {
      final record = await workbench.createWorkOrder(draft.fields);
      return RecordSaveResult(label: '已创建作业单', json: record.json);
    }
    if (_isWageScene(draft.scene)) {
      final record = await workbench.saveWage(draft.fields);
      return RecordSaveResult(label: '已保存工资记录', json: record.json);
    }
    throw UnsupportedRecordSceneException(draft.scene);
  }

  bool _isCostScene(String scene) => scene.contains('ledger') || scene.contains('cost');
  bool _isDebtScene(String scene) => scene.contains('debt');
  bool _isLogScene(String scene) => scene.contains('log');
  bool _isWorkOrderScene(String scene) => scene.contains('work_order');
  bool _isWageScene(String scene) => scene.contains('wage') || scene.contains('labor');
}

class RecordDraft {
  const RecordDraft({
    required this.scene,
    required this.originalText,
    required this.fields,
    required this.missingFields,
    required this.warnings,
  });

  final String scene;
  final String originalText;
  final Map<String, Object?> fields;
  final List<String> missingFields;
  final List<String> warnings;
}

class RecordSaveResult {
  const RecordSaveResult({required this.label, required this.json});

  final String label;
  final Map<String, dynamic> json;
}

class MissingRecordFieldsException implements Exception {
  const MissingRecordFieldsException(this.fields);
  final List<String> fields;
}

class UnsupportedRecordSceneException implements Exception {
  const UnsupportedRecordSceneException(this.scene);
  final String scene;
}
```

- [ ] **Step 4: WorkbenchScreen 接入 controller**

Modify constructor:

```dart
const WorkbenchScreen({
  super.key,
  required this.recordFlowController,
  this.onGoHome,
  this.onGoLedger,
  this.onRecordAgain,
});

final RecordFlowController recordFlowController;
```

Update `_VoiceInputCard` so tapping uses text input and calls:

```dart
final draft = await recordFlowController.parse('今天买饲料 3680 元');
Navigator.of(context).push(
  MaterialPageRoute(
    builder: (_) => RecordAiConfirmScreen(
      controller: recordFlowController,
      draft: draft,
      onGoHome: onGoHome,
      onGoLedger: onGoLedger,
      onRecordAgain: onRecordAgain,
    ),
  ),
);
```

For the first implementation keep the existing example sentence as default
input text, because voice capture is not in scope.

- [ ] **Step 5: 确认页展示 RecordDraft 并保存**

Modify `RecordAiConfirmScreen` constructor:

```dart
const RecordAiConfirmScreen({
  super.key,
  required this.controller,
  required this.draft,
  this.onGoHome,
  this.onGoLedger,
  this.onRecordAgain,
});

final RecordFlowController controller;
final RecordDraft draft;
```

Replace static rows with `draft.fields.entries`. On confirm:

```dart
final result = await controller.save(draft);
Navigator.of(context).push(
  MaterialPageRoute(
    builder: (_) => RecordSaveSuccessScreen(
      result: result,
      onGoHome: onGoHome,
      onGoLedger: onGoLedger,
      onRecordAgain: onRecordAgain,
    ),
  ),
);
```

If `MissingRecordFieldsException` or `UnsupportedRecordSceneException` occurs,
show `需要补充字段后再保存` and keep the user on the confirm page.

- [ ] **Step 6: 成功页展示真实保存结果**

Modify `RecordSaveSuccessScreen` constructor:

```dart
const RecordSaveSuccessScreen({
  super.key,
  required this.result,
  this.onGoHome,
  this.onGoLedger,
  this.onRecordAgain,
});

final RecordSaveResult result;
```

Replace static success subtitle with `result.label`. Render amount/category/date
from `result.json` using fallback text:

```dart
String field(String key, String fallback) {
  final value = result.json[key];
  return value == null || '$value'.isEmpty ? fallback : '$value';
}
```

- [ ] **Step 7: AppShell 创建 RecordFlowController**

Modify `mobile-app/lib/features/shell/app_shell.dart`:

```dart
late final recordFlowController = RecordFlowController(
  workbench: widget.dependencies.workbench,
  billing: widget.dependencies.billing,
);
```

Pass it to `WorkbenchScreen`.

Expose `WorkbenchRepository get workbench;` from `AppDependencies` and fake
dependencies.

- [ ] **Step 8: 更新记录流 widget 测试**

Modify `mobile-app/test/features/record_flow/record_flow_test.dart` to create a
fake controller or use `RecordingAdapter` responses, then assert:

```dart
expect(find.text('智能确认'), findsOneWidget);
expect(find.text('用户原话'), findsOneWidget);
expect(find.text('确认保存'), findsWidgets);
expect(find.textContaining('/smart-fill'), findsNothing);
```

- [ ] **Step 9: 运行记录流测试**

Run:

```bash
cd mobile-app && flutter test test/features/record_flow
```

Expected: PASS。

- [ ] **Step 10: 提交 Task 6**

Run:

```bash
git add mobile-app/lib/features/record_flow mobile-app/lib/features/workbench mobile-app/lib/features/shell/app_shell.dart mobile-app/lib/app/app_dependencies.dart mobile-app/test/features/record_flow mobile-app/test/support/fake_app_dependencies.dart
git commit -m "feat: connect record flow to smart fill"
```

Expected: commit 成功。

---

### Task 7: 全量回归和 localhost:8099 冒烟

**Files:**
- Modify: `mobile-app/README.md`
- Modify: `mobile-app/test/data/api_path_visibility_test.dart`

- [ ] **Step 1: 更新 README 运行说明**

Modify `mobile-app/README.md`:

```markdown
## 连接本地后端

默认后端地址是 `http://localhost:8099`。

```bash
curl -fsS http://localhost:8099/health
flutter run --dart-define=API_BASE_URL=http://localhost:8099
```

如果在 Android 模拟器里访问宿主机后端，需要使用：

```bash
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8099
```
```

- [ ] **Step 2: 扩展 API 路径隐藏测试**

Modify `mobile-app/test/data/api_path_visibility_test.dart` and include:

```dart
const forbiddenFragments = [
  '/auth',
  '/agent',
  '/costs',
  '/debts',
  '/weather',
  '/planting',
  '/smart-fill',
  'localhost:8099',
];
```

Assert no rendered text contains these fragments.

- [ ] **Step 3: 运行 Flutter 全量测试**

Run:

```bash
cd mobile-app && flutter test
```

Expected: PASS。

- [ ] **Step 4: 运行后端联通冒烟**

Run:

```bash
curl -fsS http://localhost:8099/health
```

Expected: HTTP 2xx。

- [ ] **Step 5: 手动运行移动端**

Run:

```bash
cd mobile-app && flutter run --dart-define=API_BASE_URL=http://localhost:8099
```

Expected:

- 登录失败不会进入主应用。
- 登录成功后进入首页。
- 首页、账本、我的、芽芽请求真实接口。
- 记录流解析失败时停留在确认/编辑页，不伪造保存数据。
- 页面不显示任何 API 路径。

- [ ] **Step 6: 运行项目 lint**

Run:

```bash
cd mobile-app && flutter analyze
```

Expected: `No issues found!`

- [ ] **Step 7: 提交 Task 7**

Run:

```bash
git add mobile-app/README.md mobile-app/test/data/api_path_visibility_test.dart
git commit -m "test: verify mobile backend integration"
```

Expected: commit 成功。

---

## 自审结果

- Spec 覆盖：认证、个人页、芽芽、首页/账本、记录流、错误状态、`localhost:8099` 验收均有对应任务。
- 范围控制：SSE、删除、结算、分类删除、模板管理、管理端接口均未纳入执行任务。
- 类型一致性：`AppSession`、`SessionStore`、`ProfileController`、`YayaController`、`HomeController`、`BillingController`、`RecordFlowController` 在任务中先定义后使用。
- 接口适配：记录流保存遇到未知 scene 或缺字段会停止，不伪造核心数据。
