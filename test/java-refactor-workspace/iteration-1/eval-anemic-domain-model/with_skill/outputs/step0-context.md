# Step 0：边界与安全网确认

> 在动诊断前，必须先确认范围、测试覆盖、API 变更许可、技术栈。用户在本次提示中**未提供**这些信息，因此先列出"待确认 4 项"并基于"贫血模型重构（DDD 战术）"场景给出**推定假设**，再进入 Step 1（用户审阅后可推翻假设）。

## 待用户确认 4 项

| # | 维度 | 推定假设（待确认）| 影响 |
|---|------|----------------|------|
| 1 | **范围** | 仅限 `Order` / `OrderItem` / `OrderService` 三个类，允许波及调用 `OrderService.pay/cancel/calculateTotal` 的上层（如 Controller） | 决定路线图是否包含"调用方迁移"步骤 |
| 2 | **测试覆盖** | **未知**——按"无测试"高风险处理；如已有 `OrderServiceTest`，请告知覆盖率与已覆盖路径（pay 成功 / pay 失败 / cancel 各状态 / calculateTotal） | 决定 Step 3 是否在路线图首位插入"特征化测试"步骤 |
| 3 | **API 变更许可** | 推定：`OrderService` 公开方法签名（`pay(String,BigDecimal)` / `cancel(String)` / `calculateTotal(String):BigDecimal`）**必须保持兼容**；`Order` 是内部领域模型，可改字段类型/封装 setter；DB 表结构推定为"短期内不能改 schema，但可加 TypeHandler/Converter 做映射"。 | 决定 Money 值对象与 OrderStatus 枚举如何持久化（拆字段 vs TypeHandler） |
| 4 | **技术栈** | 推定：Java 17 / Spring Boot 3.x / MyBatis（基于 `orderMapper.selectById/update` 风格） | 决定 record 是否可用、值对象映射方案 |

## 风险标记

- **高风险**：测试覆盖未知 → 默认按"无安全网"处理，Step 2 路线图首位排"特征化测试"
- **中风险**：DDD 化属于结构性改造，会改变实体的可变性与封装边界；如果该模块还有其它 Service 直接 `order.setStatus(...)`，存在霰弹式修改的传染面（需要 Step 1 扫描扩大调用方搜索）
- **过度设计警告**（重要）：用户提示中只展示了 3 个 Service 方法 + 简单的状态机（DRAFT→PAID / →CANCELLED），**领域复杂度可能不足以触发完整 DDD 战术建模**。请参见路线图末尾的 §过度设计警告 决策点。

## 待用户回应后我才继续

请确认或修正以上 4 项。如果你只要看诊断/路线图大致结论，我可以**基于推定假设**先给出 Step 1 与 Step 2（已在同目录其它文件），但 Step 3 的具体改法必须等你确认 #2（测试现状）与 #3（API/DB 许可）之后再细化。
