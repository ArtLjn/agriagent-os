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

  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || sending) return;
    sending = true;
    errorMessage = null;
    pendingAction = null;
    messages.add(YayaMessageViewModel.user(trimmed));
    final assistantIndex = messages.length;
    messages.add(const YayaMessageViewModel(role: 'assistant', content: ''));
    _safeNotify();
    try {
      await for (final event in repository.streamMessage(
        trimmed,
        sessionId: activeSessionId,
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
        if (event.pendingAction != null) pendingAction = event.pendingAction;
        _safeNotify();
      }
    } catch (_) {
      if (_disposed) return;
      errorMessage = '芽芽暂时没有回应，请稍后再试';
      _removeEmptyAssistant(assistantIndex);
    } finally {
      if (!_disposed) {
        sending = false;
        _safeNotify();
      }
    }
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
  });

  factory YayaMessageViewModel.user(String content) {
    return YayaMessageViewModel(role: 'user', content: content);
  }

  factory YayaMessageViewModel.fromConversation(ConversationMessage message) {
    return YayaMessageViewModel(role: message.role, content: message.content);
  }

  final String role;
  final String content;

  YayaMessageViewModel copyWith({String? content}) {
    return YayaMessageViewModel(role: role, content: content ?? this.content);
  }
}
