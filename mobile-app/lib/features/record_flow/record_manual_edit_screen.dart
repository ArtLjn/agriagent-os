import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../shared/widgets/card_panel.dart';
import '../../theme/app_colors.dart';
import '../../theme/app_text_styles.dart';
import 'record_flow_controller.dart';
import 'record_flow_widgets.dart';
import 'record_save_success_screen.dart';

class RecordManualEditScreen extends StatefulWidget {
  const RecordManualEditScreen({
    super.key,
    required this.controller,
    required this.draft,
    this.onGoHome,
    this.onGoLedger,
    this.onRecordAgain,
  });

  final RecordFlowController controller;
  final RecordDraft draft;
  final VoidCallback? onGoHome;
  final VoidCallback? onGoLedger;
  final VoidCallback? onRecordAgain;

  @override
  State<RecordManualEditScreen> createState() => _RecordManualEditScreenState();
}

class _RecordManualEditScreenState extends State<RecordManualEditScreen> {
  final Map<String, TextEditingController> _controllers = {};
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final keys = {
      ...widget.draft.fields.keys,
      ...widget.draft.missingFields,
    }.where((key) => key.isNotEmpty).toList();
    if (keys.isEmpty) keys.add('note');
    for (final key in keys) {
      _controllers[key] = TextEditingController(
        text: '${widget.draft.fields[key] ?? ''}',
      );
    }
  }

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving) return;
    final fields = Map<String, Object?>.from(widget.draft.fields);
    final missing = <String>[];
    for (final entry in _controllers.entries) {
      final value = entry.value.text.trim();
      if (value.isEmpty && widget.draft.missingFields.contains(entry.key)) {
        missing.add(entry.key);
      } else if (value.isNotEmpty) {
        fields[entry.key] = value;
      } else {
        fields.remove(entry.key);
      }
    }
    if (missing.isNotEmpty) {
      setState(() => _error = '还有字段需要补充：${missing.join('、')}');
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final result = await widget.controller.save(
        widget.draft.copyWith(fields: fields, missingFields: const []),
      );
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => RecordSaveSuccessScreen(
            result: result,
            onGoHome: widget.onGoHome,
            onGoLedger: widget.onGoLedger,
            onRecordAgain: widget.onRecordAgain,
          ),
        ),
      );
    } on UnsupportedRecordSceneException catch (error) {
      _setError('暂不支持保存该记录类型：${error.scene}');
    } catch (_) {
      _setError('保存失败，请检查后再试');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _setError(String message) {
    if (!mounted) return;
    setState(() => _error = message);
  }

  @override
  Widget build(BuildContext context) {
    return FlowScaffold(
      title: '改一下',
      subtitle: '补全字段后再保存',
      bottomPadding: 150,
      bottomBar: StickyActionBar(
        children: [
          Expanded(
            child: FlowButton(
              label: _saving ? '保存中' : '保存修改',
              icon: LucideIcons.circleCheckBig,
              onTap: _save,
            ),
          ),
        ],
      ),
      children: [
        const ContextPill(),
        const SizedBox(height: 12),
        _SceneCard(scene: widget.draft.scene),
        const SizedBox(height: 12),
        EditSectionCard(
          title: '识别字段',
          icon: LucideIcons.listChecks,
          children: _controllers.entries
              .map(
                (entry) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _FieldEditor(
                    name: entry.key,
                    controller: entry.value,
                    requiredField:
                        widget.draft.missingFields.contains(entry.key),
                  ),
                ),
              )
              .toList(),
        ),
        if (widget.draft.originalText.isNotEmpty) ...[
          const SizedBox(height: 12),
          EditSectionCard(
            title: '用户原话',
            icon: LucideIcons.messageSquareText,
            children: [
              Text(
                widget.draft.originalText,
                style: AppTextStyles.body.copyWith(color: AppColors.ink2),
              ),
            ],
          ),
        ],
        if (_error != null) ...[
          const SizedBox(height: 12),
          FlowHintCard(text: _error!),
        ],
      ],
    );
  }
}

class _SceneCard extends StatelessWidget {
  const _SceneCard({required this.scene});

  final String scene;

  @override
  Widget build(BuildContext context) {
    return CardPanel(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          const Icon(LucideIcons.sparkles, color: AppColors.blue, size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              scene.isEmpty ? '待确认记录类型' : scene,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.sectionTitle.copyWith(fontSize: 16),
            ),
          ),
        ],
      ),
    );
  }
}

class _FieldEditor extends StatelessWidget {
  const _FieldEditor({
    required this.name,
    required this.controller,
    required this.requiredField,
  });

  final String name;
  final TextEditingController controller;
  final bool requiredField;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      decoration: InputDecoration(
        labelText: requiredField ? '$name（必填）' : name,
        filled: true,
        fillColor: AppColors.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.lineSoft),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.lineSoft),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.blue),
        ),
      ),
    );
  }
}
