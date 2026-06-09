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
    pendingAction = null;
    messages.add(YayaMessageViewModel.user(trimmed));
    final assistantIndex = messages.length;
    messages.add(const YayaMessageViewModel(role: 'assistant', content: ''));
    notifyListeners();
    try {
      await for (final event in repository.streamMessage(
        trimmed,
        sessionId: activeSessionId,
      )) {
        if (event.done) break;
        if (event.error != null && event.error!.isNotEmpty) {
          errorMessage = event.error;
          _removeEmptyAssistant(assistantIndex);
          notifyListeners();
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
        notifyListeners();
      }
    } catch (_) {
      errorMessage = '芽芽暂时没有回应，请稍后再试';
      _removeEmptyAssistant(assistantIndex);
    } finally {
      sending = false;
      notifyListeners();
    }
  }

  void _removeEmptyAssistant(int assistantIndex) {
    if (assistantIndex < messages.length &&
        messages[assistantIndex].content.isEmpty) {
      messages.removeAt(assistantIndex);
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

  factory YayaMessageViewModel.fromConversation(ConversationMessage message) {
    return YayaMessageViewModel(role: message.role, content: message.content);
  }

  final String role;
  final String content;

  YayaMessageViewModel copyWith({String? content}) {
    return YayaMessageViewModel(role: role, content: content ?? this.content);
  }
}
