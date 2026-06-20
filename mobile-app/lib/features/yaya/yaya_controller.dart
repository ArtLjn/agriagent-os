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
  List<String> lastSkills = const [];
  Map<String, dynamic>? pendingAction;
  bool _disposed = false;

  Future<void> loadConversations() async {
    final loaded = await repository.loadConversations();
    if (_disposed) return;
    conversations
      ..clear()
      ..addAll(loaded);
    _safeNotify();
  }

  Future<void> openConversation(String sessionId) async {
    if (sending) {
      errorMessage = '请等待芽芽回复完成后再切换会话';
      _safeNotify();
      return;
    }
    activeSessionId = sessionId;
    final loaded = await repository.loadMessages(sessionId);
    if (_disposed) return;
    messages
      ..clear()
      ..addAll(loaded.map(YayaMessageViewModel.fromConversation));
    _safeNotify();
  }

  void startNewConversation() {
    if (sending) {
      errorMessage = '请等待芽芽回复完成后再新建对话';
      _safeNotify();
      return;
    }
    activeSessionId = null;
    errorMessage = null;
    pendingAction = null;
    lastSkills = const [];
    messages.clear();
    _safeNotify();
  }

  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || sending) return;
    sending = true;
    errorMessage = null;
    pendingAction = null;
    activeSessionId ??= _newSessionId();
    final sessionId = activeSessionId;
    messages.add(YayaMessageViewModel.user(trimmed));
    final assistantIndex = messages.length;
    messages.add(const YayaMessageViewModel(role: 'assistant', content: ''));
    _safeNotify();
    try {
      await for (final event in repository.streamMessage(
        trimmed,
        sessionId: sessionId,
      )) {
        if (_disposed) break;
        if (event.done) break;
        if (event.error != null && event.error!.isNotEmpty) {
          errorMessage = event.error;
          _removeEmptyAssistant(assistantIndex);
          _safeNotify();
          break;
        }
        final content = event.content;
        if (content != null && content.isNotEmpty) {
          final current = messages[assistantIndex];
          messages[assistantIndex] = current.copyWith(
            content: current.content + content,
          );
        }
        if (event.skills.isNotEmpty) lastSkills = event.skills;
        if (event.pendingAction != null) {
          pendingAction = event.pendingAction;
          final current = messages[assistantIndex];
          messages[assistantIndex] = current.copyWith(
            pendingAction: event.pendingAction,
          );
        }
        _safeNotify();
      }
    } catch (_) {
      if (_disposed) return;
      errorMessage = '芽芽暂时没有回应，请稍后再试';
      _removeEmptyAssistant(assistantIndex);
    } finally {
      if (!_disposed) {
        sending = false;
        await _refreshConversationsSilently();
        _safeNotify();
      }
    }
  }

  Future<void> respondToPendingAction(String text) async {
    if (pendingAction == null) return;
    pendingAction = null;
    for (var index = 0; index < messages.length; index++) {
      final message = messages[index];
      if (message.pendingAction != null) {
        messages[index] = message.copyWith(clearPendingAction: true);
      }
    }
    _safeNotify();
    await send(text);
  }

  void _removeEmptyAssistant(int assistantIndex) {
    if (assistantIndex < messages.length &&
        messages[assistantIndex].content.isEmpty) {
      messages.removeAt(assistantIndex);
    }
  }

  void _safeNotify() {
    if (!_disposed) notifyListeners();
  }

  Future<void> _refreshConversationsSilently() async {
    try {
      final loaded = await repository.loadConversations();
      if (_disposed) return;
      conversations
        ..clear()
        ..addAll(loaded);
    } catch (_) {
      return;
    }
  }

  String _newSessionId() {
    return 'app-${DateTime.now().microsecondsSinceEpoch}';
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}

class YayaMessageViewModel {
  const YayaMessageViewModel({
    required this.role,
    required this.content,
    this.pendingAction,
  });

  factory YayaMessageViewModel.user(String content) {
    return YayaMessageViewModel(role: 'user', content: content);
  }

  factory YayaMessageViewModel.fromConversation(ConversationMessage message) {
    return YayaMessageViewModel(
      role: message.role,
      content: message.content,
      pendingAction: message.pendingAction,
    );
  }

  final String role;
  final String content;
  final Map<String, dynamic>? pendingAction;

  YayaMessageViewModel copyWith({
    String? content,
    Map<String, dynamic>? pendingAction,
    bool clearPendingAction = false,
  }) {
    return YayaMessageViewModel(
      role: role,
      content: content ?? this.content,
      pendingAction:
          clearPendingAction ? null : pendingAction ?? this.pendingAction,
    );
  }
}
