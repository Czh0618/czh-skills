# 重构诊断报告：UserService 上帝类拆分

**扫描范围**：`UserService`（700+ 行 / 16 个公共方法 / 11 个 `@Autowired` 字段）
**Java 版本**：17 | **框架**：Spring Boot 3 + MyBatis | **测试覆盖**：行覆盖约 65%
**扫描时间**：2026-05-19
**Step 0 风险标记**：中（测试覆盖中等，但单类影响面大；每方法 `@Transactional`，事务边界改动需重点验证）

---

## 重构上下文摘要

| 维度 | 内容 |
|------|------|
| 范围 | `UserService`（单文件，允许波及调用方注入点改动） |
| 测试覆盖 | 65%（用户基础操作覆盖较好；权限/审计/通知未确认） |
| API 变更 | 公有方法签名保持兼容（拆分后通过原 `UserService` 转发 or 调用方逐步迁移） |
| 技术栈 | Java 17 / Spring Boot 3 / MyBatis；所有 Service 方法 `@Transactional` |
| 风险标记 | 中（覆盖率尚可，但 `@Transactional` + AOP 切面叠加需验证） |

---

## 问题清单

| # | 坏味道（Java 名） | 全局规则映射 | 位置 | 严重度 | 推荐手法 | 估算工作量 | 依赖前置 |
|---|------------------|------------|------|-------|---------|----------|---------|
| 1 | 上帝类 `UserService` | 僵化 / 不必要复杂性 | 整类 700+ 行 | **高** | Extract Class（按子领域拆 4 个 `@Service`） | 1-1.5d | 依赖 #2 完成后才能精准拆 |
| 2 | 发散式变化（按子域分组明显） | 僵化 | 4 个注释块：用户/角色权限/审计/通知 | **高** | 先在原类内分组排列 + 抽 private helper，再 Extract Class | 2h | 无（可立即开始） |
| 3 | 数据泥团：通知三件套（`NotificationSender` + `SmsClient` + `EmailClient`）| 数据泥团 | 3 个字段 + 3 个 sendXxx 方法 | 中 | Extract Class `NotificationDispatcher`（封装多通道）| 3h | 依赖 #1 拆出 NotificationService 后做 |
| 4 | 霰弹式修改：审计落库散落 | 冗余 | `logUserAction` 在多方法内被显式调用 | 中 | 改用 `ApplicationEventPublisher` 异步发事件，AuditService 监听 | 4h | 依赖 #1 拆出 AuditService |
| 5 | 字段注入（`@Autowired` 11 处）| 脆弱性 | 类首 | 中 | 改构造器注入（Spring Boot 3 推荐）| 1h | 与 #1 同步做收益最高 |
| 6 | 过宽 `@Transactional` | 不必要复杂性 | 16 个方法全部 | 中 | 查询方法改 `@Transactional(readOnly = true)`；通知方法去事务化（事件 + REQUIRES_NEW）| 2h | 依赖 #1 |
| 7 | 潜在 AOP self-invocation 失效 | 晦涩性 | 类内方法互调（如 `createUser` 内调 `sendWelcomeNotification`、`logUserAction`）| 中 | 拆分后跨 Bean 调用，AOP 自动生效 | 同 #1 | - |
| 8 | 跨子域数据耦合（同一 Bean 持有 `UserMapper` + `AuditLogMapper` + `RoleMapper`） | 循环依赖（潜在） | 11 个 `@Autowired` | 中 | Extract Class 后，每个 Service 只持有自己子域的 Mapper | 同 #1 | - |

---

## 总体观察

1. **核心矛盾**：`UserService` 承担 4 个子领域职责（用户基础 / 角色权限 / 审计 / 通知），每次任一子域变更都要打开同一个文件，是发散式变化的典型表征，必须按子域拆分。
2. **拆分顺序的关键**：通知（Notification）和审计（Audit）是叶子子域（只被调用，不调用其他子域），应**先拆**；角色权限（Permission）需要查 `UserMapper`，是中间层；用户基础操作（User）是核心，**最后定型**。
3. **Spring 特定风险**：每个方法都标了 `@Transactional`，拆分时事务边界会从"同 Bean 内自调（self-invocation 不走代理 = 当前其实没生效）"变为"跨 Bean 调用（代理生效，事务真正起作用）"。**这是行为变化，必须特征化测试覆盖**。
4. **循环依赖预防**：拆出 NotificationService / AuditService 后，不应反向注入 UserService（NotificationService 不应再去查用户）。如必要，通过事件 (`ApplicationEvent`) 解耦。
5. **测试覆盖盲区**：65% 是整体数字，需进一步确认通知和审计两块的覆盖情况——这两块即将被拆分，是重点保护对象。

---

## 待用户确认

1. 公有 API 是否允许"先 deprecated + 转发，下版本删除"的两阶段迁移？还是必须保证一次性切换？
2. 是否允许新增 4 个 `@Service` Bean（`UserService` / `PermissionService` / `AuditService` / `NotificationService`）？包名建议在 `user` 子包下平铺，还是按子域建 4 个子包？
3. 审计是否可改异步（`@EventListener` + `@Async`）？这会改变"操作失败时审计也回滚"的语义。
4. 通知是否可改异步？同上语义影响。
5. 是否同意在拆分前先做一遍 `@Transactional` 行为的特征化测试（验证当前同类自调实际未走代理的行为基线）？

---

继续 Step 2 路线图生成吗？我会给出按子域拆分的依赖排序与 Spring 特定风险标注。
