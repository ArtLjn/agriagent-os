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
      scene: 'ledger.record',
      text: text,
      idempotencyKey: DateTime.now().microsecondsSinceEpoch.toString(),
    );
    return RecordDraft(
      scene: result.scene,
      originalText: text,
      fields: Map<String, Object?>.from(result.draft),
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

  bool _isCostScene(String scene) =>
      _sceneKey(scene) == 'ledger.record' || _sceneKey(scene) == 'cost.record';

  bool _isDebtScene(String scene) => _sceneKey(scene) == 'debt.record';

  bool _isLogScene(String scene) =>
      _sceneKey(scene) == 'farm.log' || _sceneKey(scene) == 'log.record';

  bool _isWorkOrderScene(String scene) =>
      _sceneKey(scene) == 'work_order.create';

  bool _isWageScene(String scene) =>
      _sceneKey(scene) == 'wage.record' || _sceneKey(scene) == 'labor.wage';

  String _sceneKey(String scene) => scene.trim().toLowerCase();
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

  RecordDraft copyWith({
    String? scene,
    String? originalText,
    Map<String, Object?>? fields,
    List<String>? missingFields,
    List<String>? warnings,
  }) {
    return RecordDraft(
      scene: scene ?? this.scene,
      originalText: originalText ?? this.originalText,
      fields: fields ?? this.fields,
      missingFields: missingFields ?? this.missingFields,
      warnings: warnings ?? this.warnings,
    );
  }
}

class RecordSaveResult {
  const RecordSaveResult({
    required this.label,
    required this.json,
  });

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
