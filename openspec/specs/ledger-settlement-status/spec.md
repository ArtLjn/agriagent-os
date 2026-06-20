# ledger-settlement-status Specification

## Purpose
TBD - archived from change simplify-ledger-settlement-status. Update Purpose after review.

## Requirements
### Requirement: 账单记录必须区分发生金额和结算金额
系统 SHALL 在账单记录中区分账单发生金额、已结算金额和结算状态。

#### Scenario: 创建已结算支出
- **WHEN** 用户创建一条普通支出账单，金额为 100 元，且未标记赊账
- **THEN** 系统 MUST 保存 `amount=100`
- **AND** 系统 MUST 保存 `settled_amount=100`
- **AND** 系统 MUST 保存 `settlement_status="settled"`

#### Scenario: 创建未结赊账支出
- **WHEN** 用户创建一条支出账单，金额为 100 元，并标记“这笔先赊着”
- **THEN** 系统 MUST 保存 `amount=100`
- **AND** 系统 MUST 保存 `settled_amount=0`
- **AND** 系统 MUST 保存 `settlement_status="unsettled"`
- **AND** 系统 MUST 保留对方名称和预计结算日期

#### Scenario: 创建收入未收款
- **WHEN** 用户创建一条收入账单，金额为 200 元，并标记“对方先欠着”
- **THEN** 系统 MUST 保存 `amount=200`
- **AND** 系统 MUST 保存 `settled_amount=0`
- **AND** 系统 MUST 保存 `settlement_status="unsettled"`
- **AND** 系统 MUST 将其识别为未收款，而不是已收现金收入

### Requirement: 标记还款必须更新原未结账单
系统 SHALL 在用户标记还款或收款时更新原未结账单的已结算金额和结算状态。

#### Scenario: 全额结清赊账
- **WHEN** 一条未结支出账单金额为 100 元且用户标记还款 100 元
- **THEN** 系统 MUST 将原账单 `settled_amount` 更新为 100
- **AND** 系统 MUST 将原账单 `settlement_status` 更新为 `"settled"`
- **AND** 系统 MUST 设置 `settled_at`
- **AND** 系统 MUST NOT 创建普通收入记录表示本次还款

#### Scenario: 部分结清赊账
- **WHEN** 一条未结支出账单金额为 100 元且用户标记还款 40 元
- **THEN** 系统 MUST 将原账单 `settled_amount` 更新为 40
- **AND** 系统 MUST 将原账单 `settlement_status` 更新为 `"partial"`
- **AND** 系统 MUST 返回未结金额 60 元
- **AND** 系统 MUST NOT 将本次还款计入普通收入

#### Scenario: 收入收款
- **WHEN** 一条未收款收入账单金额为 200 元且用户标记收款 200 元
- **THEN** 系统 MUST 将原账单 `settled_amount` 更新为 200
- **AND** 系统 MUST 将原账单 `settlement_status` 更新为 `"settled"`
- **AND** 系统 MUST NOT 创建普通支出或普通收入记录表示本次收款

### Requirement: 账单汇总必须区分发生额和现金额
系统 SHALL 在账单汇总中分别计算发生额、已结现金额和未结余额。

#### Scenario: 赊账不计入已付现金
- **WHEN** 本月存在一条 100 元普通支出和一条 80 元未结赊账支出
- **THEN** 系统 MUST 汇总本月发生支出为 180 元
- **AND** 系统 MUST 汇总本月已付支出为 100 元
- **AND** 系统 MUST 汇总当前未付为 80 元

#### Scenario: 未收款收入不计入已收现金
- **WHEN** 本月存在一条 300 元普通收入和一条 200 元未收款收入
- **THEN** 系统 MUST 汇总本月发生收入为 500 元
- **AND** 系统 MUST 汇总本月已收收入为 300 元
- **AND** 系统 MUST 汇总当前未收为 200 元

#### Scenario: 还款后未付余额减少
- **WHEN** 一条 80 元未结赊账支出被标记还款 30 元
- **THEN** 系统 MUST 汇总当前未付为 50 元
- **AND** 系统 MUST NOT 因本次还款增加普通收入

### Requirement: 利润统计必须使用发生额
系统 SHALL 使用账单发生额计算利润，并排除还款或收款标记对普通收入/支出的污染。

#### Scenario: 赊账成本进入利润成本
- **WHEN** 某茬口存在一条 80 元未结赊账支出
- **THEN** 系统 MUST 将 80 元计入该茬口利润的总支出
- **AND** 系统 MUST 在现金汇总中将其显示为未付，而不是已付

#### Scenario: 还款不增加利润收入
- **WHEN** 用户对一条赊账支出标记还款 80 元
- **THEN** 系统 MUST NOT 将 80 元计入利润总收入
- **AND** 系统 MUST 只更新该账单的结算状态
