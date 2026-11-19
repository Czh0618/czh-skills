# Step 1：重构诊断报告

**扫描范围**：`Order` / `OrderItem` / `OrderService`（用户提示中提供的代码片段）
**Java 版本（推定）**：17 | **框架（推定）**：Spring Boot 3.x + MyBatis | **测试覆盖**：未知（按 < 50% 高风险处理）
**扫描时间**：2026-05-19

## 问题清单

| # | 坏味道（Java 名）| 全局规则映射 | 位置 | 严重度 | 推荐手法 | 估算工作量 | 依赖前置 |
|---|----------------|------------|------|-------|---------|----------|---------|
| 1 | **贫血模型 Anemic Domain Model**：`Order` 仅有字段+getter/setter，`pay/cancel/calculateTotal` 三个业务规则全在 `OrderService` 中 | 晦涩性 / 僵化 | `Order.java` 整体 + `OrderService.pay/cancel/calculateTotal` | **高** | Move Method（将 pay/cancel/calculateTotal 从 Service 搬入 Order 实体），参见 `references/ddd-tactical.md` §Entity + §贫血→充血 阶段 2-3 | 3-4h | 需先补特征化测试 |
| 2 | **类型码 Type Code**：`Integer status`（0=DRAFT,1=PAID,2=SHIPPED,3=CANCELLED），含义靠注释维系 | 晦涩性 / 脆弱性 | `Order.status` 字段 + 所有 `getStatus()==N` 比较点（Service 4 处） | **高** | Replace Type Code with Enum（`OrderStatus`），参见 `references/refactoring-techniques.md` §8 | 1-1.5h | 与 #1 协同改造 |
| 3 | **数据泥团 + 基本类型偏执**：`BigDecimal amount` 与 `String currency` 总是同时出现，缺金额运算的封装 | 数据泥团 | `Order.amount/currency` 字段 + `calculateTotal` 中 `BigDecimal` 累加 | **高** | Introduce Value Object `Money`（不可变 record + add/multiply），参见 `references/ddd-tactical.md` §Value Object | 1.5-2h | 与 #1 协同改造（Order 字段类型变更） |
| 4 | **状态机散落 / 守卫规则散落**：`pay` 与 `cancel` 各自有状态校验（`status!=0` / `status==2 || status==3`），后续若新增"已退款""部分支付"等状态会产生**霰弹式修改** | 脆弱性 / 僵化 | `OrderService.pay` L?-L? + `OrderService.cancel` L?-L? | 中 | Move Method（守卫与转换都搬入 `Order.pay/cancel`），状态合法转换可用枚举内联 `canTransitionTo()` | 含在 #1 中 | 依赖 #2 完成 |
| 5 | **晦涩性 `calculateTotal(orderId)` 还多查一次 DB**：明明 `Order` 持有 `items`，却让 Service 通过 `orderMapper.selectById` 再装载——徒增 IO，且把"算总价"这件领域行为留在 Service | 晦涩性 / 冗余 | `OrderService.calculateTotal` | 中 | Move Method 到 `Order.totalAmount(): Money`；Service 调用 `repo.findById(id).totalAmount()` | 30m | 依赖 #1, #3 |
| 6 | **可变实体 + setter 全开**：`Order` 暴露 `setStatus/setAmount/...`，任何外部代码都能绕过业务规则直接赋值 | 脆弱性 | `Order` 全部 setter | 中 | Encapsulate Field：去掉 setter，状态变更只通过 `pay/cancel` 等行为方法 | 含在 #1 中 | - |
| 7 | **领域规则不明确**：`pay` 部分支付是否允许？`SHIPPED` 状态由谁触发？`cancel` 已 PAID 单是否允许（提示代码里允许）？退款流程？多币种是否真存在？ | 晦涩性（需求模糊）| 全局 | 高（**阻塞**充分 DDD 化）| **不是重构手法能解决的**——建议先走 `/req-reverse-eng` 把状态机/不变量摸清，再决定 DDD 改造深度 | 用户决策 | - |

## 总体观察

1. **三个核心坏味道协同出现**：贫血模型（#1）+ 类型码（#2）+ Money 缺失（#3）。Fowler/Evans 视角下这是教科书级的"该上 DDD 战术模式"信号，但三者改动**强耦合**——值对象与枚举的改造会顺带触发实体接口变化，建议作为**一组阶段化提交**而非孤立步骤。
2. **当前展示的领域复杂度仍偏低**：只有 4 个状态、3 个用例。完全 DDD 化（聚合根边界、Repository、Domain Event）大概率属于**过度设计**。建议落到**阶段 1-3**（值对象 + 行为搬入实体 + 状态机收敛）即可，**阶段 4-6 暂缓**——直到 #7 的领域规则被澄清后再评估。参见 `references/ddd-tactical.md` §过度设计警告。
3. **测试覆盖未知导致路线图首步必须是特征化测试**：`pay/cancel` 的 4 个状态转换路径如果没有用例锁定，"setStatus(1)" 这种最朴素的语义被改成 `order.pay(money)` 时极易出现等价行为偏移（如异常类型变了、异常时机提前/延后）。
4. **持久化层会被牵动**：`Order.status: Integer` 改 enum、`amount/currency` 改 `Money` 之后，MyBatis 端需要 `TypeHandler` 或拆字段映射。这部分在 Step 3 内会显式给出。

## ⚠️ 过度设计警告（DDD 化决策点）

按 `references/ddd-tactical.md` §过度设计警告 的判定清单：

| 判定问题 | 当前回答 |
|---------|---------|
| 业务规则是否复杂到需要"领域专家"参与？ | **未知**——展示代码看不出 |
| 是否多个业务领域纠缠？ | 否（只有 Order 一个聚合） |
| 业务规则是否经常变化？ | **未知** |
| 当前贫血模型是否已经导致维护痛苦？ | **未知**（用户只说"看了 DDD 资料想试试"，未陈述痛点）|

**≥ 2 项为"是"才值得引入完整 DDD 战术模式**。目前只有 0-1 项明确为"是"。

**建议**：
- 落到**阶段 1-3**（值对象 + Move Method + 状态机枚举）几乎无副作用，是基础重构红利
- **阶段 4-6**（聚合边界、Repository 重命名、Domain Event）**暂缓**，等领域规则澄清后再评估
- 如果用户的真实诉求是"我想学 DDD 在真实项目中怎么落地"——这属于**教学**而非**生产改造**，建议另起一个 sandbox 分支练习，避免主干被半成品 DDD 改造拖累

## 待用户确认

1. 是否同意将本轮重构限定在 **DDD 战术阶段 1-3**（值对象 / Move Method / 状态机枚举），**暂不**做聚合根 / Repository 命名重构 / Domain Event？
2. 是否先走 `/req-reverse-eng` 澄清 #7 的领域规则（部分支付、SHIPPED 触发方、退款、多币种）？还是先按"现有行为不变 + 结构改善"做？
3. 测试覆盖现状是？（决定 Step 2 是否需要把"特征化测试"排在路线图首位）
4. `orderMapper.update(order)` 的 SQL 是否是动态 set 所有字段？（决定 Money 拆字段 vs TypeHandler 哪种迁移更便宜）

---

继续 Step 2 路线图生成。
