import 'package:flutter/material.dart';
import '../../data/api/api_client.dart';

/// 与 Web 共用 Agent API，不在设备上保存第二份有效偏好。
class AssistantSettingsScreen extends StatefulWidget {
  const AssistantSettingsScreen({super.key, required this.client});
  final ApiClient client;
  @override
  State<AssistantSettingsScreen> createState() => _AssistantSettingsState();
}

class _AssistantSettingsState extends State<AssistantSettingsScreen> {
  Map<String, dynamic>? _settings;
  List<Map<String, dynamic>> _memories = [];
  String? _error;
  bool _busy = false;
  final _text = <String, TextEditingController>{
    'nickname': TextEditingController(),
    'assistant_name': TextEditingController(),
    'custom_instructions': TextEditingController(),
  };
  static const _choices = {
    'reply_style': {
      'default': '默认',
      'friendly': '亲和易懂',
      'professional': '专业严谨',
      'efficient': '高效务实'
    },
    'detail_level': {'concise': '简洁', 'balanced': '适中', 'detailed': '详细'},
    'display_format': {'auto': '自动', 'table': '优先表格', 'list': '优先列表'},
    'execution_detail_level': {'concise': '精简进度', 'detailed': '详细进度'},
  };
  static const _labels = {
    'reply_style': '回复风格',
    'detail_level': '详细程度',
    'display_format': '展示方式',
    'execution_detail_level': '执行过程'
  };

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final controller in _text.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final settings = await widget.client.getMap('/me/personalization');
      final items = <Map<String, dynamic>>[];
      var page = 1;
      while (true) {
        final result = await widget.client
            .getMap('/me/memories', query: {'page': page, 'page_size': 100});
        items.addAll((result['items'] as List)
            .map((e) => Map<String, dynamic>.from(e as Map)));
        if (items.length >= (result['total'] as num).toInt()) break;
        page++;
      }
      if (!mounted) return;
      for (final entry in _text.entries) {
        entry.value.text = '${settings[entry.key] ?? ''}';
      }
      setState(() {
        _settings = settings;
        _memories = items;
      });
    } catch (_) {
      if (mounted) setState(() => _error = '加载失败，请重试');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() async {
    if (_settings == null || _busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final values = <String, dynamic>{
      'expected_revision': _settings!['revision']
    };
    for (final key in [
      ..._choices.keys,
      'auto_learn_enabled',
      'use_saved_memories',
      'loading_greeting_enabled'
    ]) {
      values[key] = _settings![key];
    }
    for (final entry in _text.entries) {
      values[entry.key] = entry.value.text;
    }
    try {
      final updated =
          await widget.client.patchMap('/me/personalization', data: values);
      if (mounted) {
        setState(() => _settings = updated);
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('已保存，下一轮对话生效')));
      }
    } catch (_) {
      if (mounted) setState(() => _error = '保存失败，编辑内容已保留。若版本冲突，请重新加载后再保存。');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _editMemory([Map<String, dynamic>? record]) async {
    final controller =
        TextEditingController(text: record?['text'] as String? ?? '');
    final id = record?['memory_id'] ??
        'mobile-${DateTime.now().microsecondsSinceEpoch}';
    var scope = record?['scope'] as String? ?? 'user';
    String? error;
    bool saving = false;
    await showDialog<void>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
            builder: (context, setDialog) => AlertDialog(
                  title: Text(record == null ? '新增记忆' : '编辑记忆'),
                  content: Column(mainAxisSize: MainAxisSize.min, children: [
                    if (record == null)
                      DropdownButtonFormField<String>(
                        initialValue: scope,
                        decoration: const InputDecoration(labelText: '适用范围'),
                        items: const [
                          DropdownMenuItem(
                              value: 'user', child: Text('我的全部农场')),
                          DropdownMenuItem(
                              value: 'user_farm', child: Text('仅当前农场'))
                        ],
                        onChanged: saving
                            ? null
                            : (value) => setDialog(() => scope = value!),
                      ),
                    TextField(
                        controller: controller, maxLength: 500, maxLines: 4),
                    if (error != null)
                      Text(error!, style: const TextStyle(color: Colors.red)),
                  ]),
                  actions: [
                    TextButton(
                        onPressed:
                            saving ? null : () => Navigator.pop(dialogContext),
                        child: const Text('取消')),
                    FilledButton(
                        onPressed: saving
                            ? null
                            : () async {
                                if (controller.text.trim().isEmpty) return;
                                setDialog(() {
                                  saving = true;
                                  error = null;
                                });
                                try {
                                  if (record == null) {
                                    await widget.client
                                        .postMap('/me/memories', data: {
                                      'memory_id': id,
                                      'key': 'manual.$id',
                                      'scope': scope,
                                      'text': controller.text.trim()
                                    });
                                  } else {
                                    await widget.client
                                        .patchMap('/me/memories/$id', data: {
                                      'expected_revision': record['revision'],
                                      'text': controller.text.trim()
                                    });
                                  }
                                  if (dialogContext.mounted) {
                                    Navigator.pop(dialogContext);
                                  }
                                  await _load();
                                } catch (_) {
                                  if (dialogContext.mounted) {
                                    setDialog(() {
                                      error = '保存失败，请重试';
                                      saving = false;
                                    });
                                  }
                                }
                              },
                        child: const Text('保存'))
                  ],
                )));
    controller.dispose();
  }

  Future<void> _remove(String? id) async {
    final accepted = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
              title: Text(id == null ? '清空全部个人记忆？' : '删除这条记忆？'),
              content: const Text('删除后不再用于后续回答。个性化设置保留。'),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('取消')),
                TextButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('删除'))
              ],
            ));
    if (accepted != true || !mounted) return;
    try {
      if (id == null) {
        await widget.client.postMap('/me/memories/clear', data: {});
      } else {
        await widget.client.delete('/me/memories/$id');
      }
      await _load();
    } catch (_) {
      if (mounted) setState(() => _error = '删除失败，请重试');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('个性化与记忆'), actions: [
          IconButton(
              onPressed: _busy ? null : _load, icon: const Icon(Icons.refresh))
        ]),
        body: _settings == null && _busy
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null)
                    Text(_error!, style: const TextStyle(color: Colors.red)),
                  if (_settings != null) ...[
                    for (final entry in _text.entries)
                      Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: TextField(
                            controller: entry.value,
                            enabled: !_busy,
                            maxLength:
                                entry.key == 'custom_instructions' ? 500 : 20,
                            maxLines:
                                entry.key == 'custom_instructions' ? 3 : 1,
                            decoration: InputDecoration(
                                labelText: {
                              'nickname': '如何称呼你',
                              'assistant_name': '助手名称',
                              'custom_instructions': '自定义指令'
                            }[entry.key]),
                          )),
                    for (final entry in _choices.entries)
                      DropdownButtonFormField<String>(
                        key: ValueKey('${entry.key}-${_settings!["revision"]}'),
                        initialValue: _settings![entry.key] as String?,
                        decoration:
                            InputDecoration(labelText: _labels[entry.key]),
                        items: entry.value.entries
                            .map((e) => DropdownMenuItem(
                                value: e.key, child: Text(e.value)))
                            .toList(),
                        onChanged: _busy
                            ? null
                            : (value) =>
                                setState(() => _settings![entry.key] = value),
                      ),
                    for (final entry in {
                      'auto_learn_enabled': '自动学习偏好',
                      'use_saved_memories': '使用已保存记忆',
                      'loading_greeting_enabled': '加载欢迎语'
                    }.entries)
                      SwitchListTile(
                          title: Text(entry.value),
                          value: _settings![entry.key] == true,
                          onChanged: _busy
                              ? null
                              : (value) => setState(
                                  () => _settings![entry.key] = value)),
                    FilledButton(
                        onPressed: _busy ? null : _save,
                        child: const Text('保存设置')),
                    const Divider(),
                    Row(children: [
                      const Expanded(child: Text('已保存的记忆')),
                      TextButton(
                          onPressed: _busy ? null : () => _editMemory(),
                          child: const Text('新增')),
                      TextButton(
                          onPressed: _busy ? null : () => _remove(null),
                          child: const Text('清空'))
                    ]),
                    if (_memories.isEmpty)
                      const Padding(
                          padding: EdgeInsets.all(24),
                          child: Text('还没有记忆。可以主动添加，也可以开启自动学习。')),
                    for (final record in _memories)
                      Card(
                          child: ListTile(
                        title: Text('${record['text']}'),
                        subtitle: Text(
                            '${record['source_type'] == 'explicit' ? '手动保存' : '自动学习'} · ${record['status'] == 'candidate' ? '待确认' : '生效'} · ${record['scope'] == 'user' ? '个人' : '当前农场'}'),
                        onTap: () => _editMemory(record),
                        trailing:
                            Row(mainAxisSize: MainAxisSize.min, children: [
                          if (record['status'] == 'candidate')
                            IconButton(
                                icon: const Icon(Icons.check),
                                onPressed: () async {
                                  try {
                                    await widget.client.patchMap(
                                        '/me/memories/${record['memory_id']}',
                                        data: {
                                          'expected_revision':
                                              record['revision'],
                                          'status': 'active'
                                        });
                                    await _load();
                                  } catch (_) {
                                    if (mounted) {
                                      setState(() => _error = '确认失败，请重试');
                                    }
                                  }
                                }),
                          IconButton(
                              icon: const Icon(Icons.delete_outline),
                              onPressed: () =>
                                  _remove('${record['memory_id']}')),
                        ]),
                      )),
                  ],
                ],
              ),
      );
}
