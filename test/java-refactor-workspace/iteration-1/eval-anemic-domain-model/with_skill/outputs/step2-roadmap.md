# Step 2：DDD 战术阶段化重构路线图

> ⚠️ **风险提示**：测试覆盖未知，按 < 50% 高风险处理。路线图首位强制插入"特征化测试"。如果用户在 Step 0 回应中确认覆盖已充分（pay/cancel/calculateTotal 主路径与异常路径均有用例），可跳过步骤 1。

> ⚠️ **过度设计警告（再次强调）**：本路线图**只覆盖 DDD 战术阶段 1-3**。阶段 4（聚合边界）、阶段 5（Domain/Application Service 拆分）、阶段 6（领域事件）**全部不在本次推荐范围**。理由见 step1-diagnosis.md §过度设计警告。如果用户后续陈述了足够的领域复杂度证据，再评估升级。

## DDD 战术分阶段映射（本次只做阶段 1-3）

| DDD 战术阶段 | 本次是否纳入 | 备注 |
|------------|-----------|------|
| 阶段 1：识别值对象（Money）| ✅ 纳入 | 低风险，红利明显 |
| 阶段 2：简单业务方法搬入实体（calculateTotal）| ✅ 纳入 | 低风险 |
| 阶段 3：状态机收敛到实体（pay/cancel + OrderStatus enum）| ✅ 纳入 | 中风险，是核心改造 |
| 阶段 4：识别聚合边界 | ⏸ 不纳入 | 领域复杂度不足，过度设计风险 |
| 阶段 5：Domain/Application Service 拆分 | ⏸ 不纳入 | 当前 `OrderService` 仅 3 个方法，不需拆 |
| 阶段 6：领域事件 | ⏸ 不纳入 | 没有跨聚合协作需求 |

## 推荐顺序

| 步骤 | 手法 | 对应诊断项 | 收益 | 风险 | 成本 | 优先级 | 备注 |
|-----|-----|----------|-----|-----|-----|-------|-----|
| 1 | 补特征化测试（pay 成功 / pay 不足额 / pay 非 DRAFT / cancel 各状态 / calculateTotal）| #1 #4 前置 | 4 | 1 | 1 | **高** | 全部后续步骤的安全网 |
| 2 | Replace Type Code with Enum：`Integer status` → `OrderStatus` 枚举（含 `canTransitionTo` 内联规则）| #2 | 5 | 2 | 2 | **高** | 不改字段语义，仅改类型；MyBatis 加 EnumTypeHandler |
| 3 | Introduce Value Object：`Money`（record + add/multiply + 同币种校验）| #3 | 5 | 2 | 2 | **高** | 不可变；按"先建类、后替换字段"两小步走 |
| 4 | Move Method：`calculateTotal` 从 `OrderService` 搬入 `Order.totalAmount(): Money` | #1 #5 | 4 | 2 | 1 | **高** | 顺手消除多余的 `orderMapper.selectById` |
| 5 | Move Method + Encapsulate Field：`pay/cancel` 搬入 `Order`；移除 `setStatus`；Service 改薄为"加载→调用→保存" | #1 #4 #6 | 5 | 3 | 3 | **中** | 本路线图的核心步骤；依赖 1-4 完成 |
| 6 | 收尾：去除 `Order` 上不再需要的 setter；补单元测试覆盖 `Order.pay/cancel/totalAmount` | #6 | 3 | 1 | 1 | 中 | 让封装真正生效 |

## 不推荐近期做

| 诊断项 / DDD 阶段 | 不推荐原因 | 重新评估时机 |
|---------|----------|-----------|
| 引入 `OrderRepository`（替代 `OrderMapper`）| DDD 阶段 4-5 范围；当前只有 3 个调用点，重命名收益低于风险 | 当 Service 调用点扩散到 ≥ 5 处或出现跨聚合查询时 |
| 聚合根设计（限制 `OrderItem` 只能从 Order 进出）| 当前 `OrderItem` 没有被外部直接 new/修改的证据，无收益 | 当出现"绕过 Order 直接改 OrderItem"的代码时 |
| 领域事件 `OrderPaidEvent` / `OrderCancelledEvent` | 当前没有需要解耦的下游消费方 | 当出现"支付完要通知库存/通知客服/审计"等场景时 |
| 把 `OrderService` 拆为 Domain Service + Application Service | 当前 Service 只有 3 个方法，没有领域规则散落问题 | 当 Service 长到 200+ 行或出现跨聚合编排时 |
| 多币种 `Money` 转换逻辑 | 用户提示中 currency 用法不明，未必真有多币种业务 | 待 `/req-reverse-eng` 澄清后 |

## 进度建议

- **本次会话内可详细展开**：步骤 1-3（即 step3-steps.md 提供 ≥ 2 步详细机械化）
- **下次专门排期**：步骤 4-5（需先确认 ORM 映射方案）
- **作为收尾**：步骤 6

## 引导用户走需求反向工程的建议

诊断 #7 指出：**部分支付是否允许 / SHIPPED 由谁触发 / 已 PAID 是否可 cancel / 多币种是否真存在** 这些规则当前不清楚。如果在阶段 3（状态机收敛）之前不澄清，会出现两种坏结果：

1. 把当前 Service 行为照搬进 Order（如允许 `pay` 时金额低于 amount 直接抛异常，但其实业务允许多次部分支付）→ **冻结了一个错误的不变量**，后续更难改
2. 自由发挥业务规则（如认为"已 PAID 不可 cancel"）→ **改变了原行为**，无安全网情况下高风险

**强烈建议在执行步骤 5 之前，先调用 `/req-reverse-eng` 完成以下澄清**：

- Order 状态机：穷举所有合法转换（DRAFT→PAID? PAID→SHIPPED 由谁触发？PAID→CANCELLED 是否允许且如何退款？）
- pay 的业务规则：必须等额？允许多付（找零）？允许少付（部分支付）？同币种校验？
- cancel 的业务规则：哪些状态可 cancel？已 PAID 单 cancel 是否触发退款？
- Money：是否真有多币种？还是 currency 字段实际恒为 CNY？

得到澄清结论后，在 step3-steps.md §步骤 5 的 mechanics 中固化为 Order 的不变量与异常类型。

## 待用户确认

1. 是否同意"只做阶段 1-3、暂不做阶段 4-6"的边界？
2. 是否同意在步骤 5 之前先走 `/req-reverse-eng` 澄清诊断 #7 的规则？
3. 步骤 2 与步骤 3 是否允许同 PR 合并（两者紧耦合，分两 PR 会让 Order 字段连续大改）？还是要严格一步一 PR？
4. 测试覆盖现状（决定步骤 1 工作量从 0 到 2-3h 不等）？

---

继续 Step 3 时，至少展开步骤 2、步骤 3（值类型化基础），并对步骤 5（核心 Move Method）给出机械化骨架。
