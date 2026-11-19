# 重构路线图：UserService 按子域拆分

基于诊断报告（step1-diagnosis.md），按 **收益 - 风险 - 成本/2** 综合优先级排序。详细评分规则见 `references/decision-matrix.md`。

> ⚠️ **Spring 特定风险提示**：本次拆分将改变 `@Transactional` 与 AOP 的实际生效边界。当前 `UserService` 内方法互调（如 `createUser` → `sendWelcomeNotification` → `logUserAction`）属于 self-invocation，`@Transactional` / `@Async` / `@Cacheable` 等切面**实际未生效**。拆分后跨 Bean 调用会让切面真正起作用——这是**行为变化**，必须用特征化测试固化当前基线后再动。

---

## 拆分目标拓扑

```
原：UserService (700+ 行, 11 @Autowired)
              │
              ▼
拆后：
  UserService          ── UserMapper, PasswordEncoder, TenantContextHolder
  PermissionService    ── RoleMapper, PermissionMapper, UserMapper(只读)
  AuditService         ── AuditLogMapper（事件监听者）
  NotificationService  ── NotificationSender, SmsClient, EmailClient, RedisTemplate
  ApplicationEventPublisher：贯穿，承担解耦
```

**依赖方向**（单向，避免循环）：
```
UserService ──事件──▶ AuditService
            ──事件──▶ NotificationService
            ──直接调用──▶ PermissionService（可选，或反过来）
PermissionService ──事件──▶ AuditService
```

---

## 推荐顺序

| 步骤 | 手法 | 对应诊断项 | 收益 | 风险 | 成本 | 优先级 | Spring 备注 |
|-----|-----|----------|-----|-----|-----|-------|-----------|
| 1 | 特征化测试补强（通知 / 审计 / 跨方法互调路径） | #1 前置 | 4 | 1 | 2 | **高** | 必须覆盖"原来 self-invocation 不走代理"的行为基线 |
| 2 | 字段注入改构造器注入 | #5 | 3 | 1 | 1 | **高** | Spring Boot 3 推荐；为后续拆分做依赖梳理 |
| 3 | 类内分组 + 抽 `private` helper（不拆类，先排序）| #2 | 3 | 1 | 1 | **高** | 准备工作；为 Extract Class 划好刀口 |
| 4 | **Extract Class：NotificationService**（叶子，先拆） | #1, #3, #7 | 5 | 2 | 3 | **高** | 通知本是叶子；改用 `ApplicationEvent` 解耦，避免反向注入 UserService |
| 5 | **Extract Class：AuditService**（叶子，并行拆） | #1, #4 | 5 | 2 | 3 | **高** | 用 `@EventListener` 监听；考虑 `@Async` + `Propagation.REQUIRES_NEW` |
| 6 | **Extract Class：PermissionService**（中间层） | #1, #8 | 5 | 3 | 3 | 中 | 注入 `UserMapper`（只读）；可能与 UserService 双向需求，用接口隔离防循环依赖 |
| 7 | 收紧 `@Transactional` 范围 | #6 | 3 | 2 | 2 | 中 | 查询方法加 `readOnly = true`；通知/审计去事务化 |
| 8 | 公有 API 兼容层（原 UserService 作 Facade 转发，标 `@Deprecated`） | - | 2 | 2 | 2 | 中 | 给调用方时间迁移；下个发布版删除 |
| 9 | 删除 Facade，调用方完成迁移 | - | 2 | 3 | 2 | 低 | 跨 PR，单独排期 |

---

## 拆分顺序的依据

1. **先无依赖的叶子（Notification、Audit）**：它们不调用其他子域，拆出来不会产生回头依赖。
2. **再拆有依赖的中间层（Permission）**：依赖 `UserMapper`，拆时要明确接口边界。
3. **最后定型 UserService**：去掉前面三块后剩下的就是用户基础操作，自然收敛。
4. **公有 API 通过 Facade 转发兼容**：避免一次性 break 调用方。

---

## Spring 特定风险与对应措施

| 风险 | 触发场景 | 预防/打破方案 |
|------|---------|-------------|
| **`@Transactional` 行为变化** | 原 `createUser` 内调 `logUserAction`，self-invocation 让 `@Transactional` 嵌套实际未生效。拆分后跨 Bean 调用，新事务嵌套真的发生 | Step 1 特征化测试先固化；Step 5/7 显式声明传播行为（`REQUIRES_NEW` 用于审计、通知）|
| **AOP 切面失效/突然生效** | 同上原理。`@Async`、`@Cacheable`、日志切面同理 | 拆分后逐个验证切面切点；切点表达式若依赖原类名需更新 |
| **循环依赖**（A→B→A） | 若 `NotificationService` 反向注入 `UserService`（如发通知前查最新用户信息）| 用 `ApplicationEvent` 事件载荷直接携带 User 对象；或抽 `UserQueryPort` 接口，单向依赖 |
| **`@Transactional` + `@Async` 同方法** | 异步审计/通知方法标 `@Async` 时，事务上下文不会传递到异步线程 | 异步方法明确不依赖外层事务；需要时用 `TransactionTemplate` 显式开新事务 |
| **MyBatis Mapper 共享** | 拆分后 `UserMapper` 被 UserService 和 PermissionService 同时注入 | 没问题——Mapper 本身无状态；但要避免在 PermissionService 中写入 User 表 |
| **构造器循环依赖直接报错** | Spring Boot 2.6+ 默认禁用循环依赖；拆分后若设计错误会立即启动失败 | 视为好事——逼迫一次性把依赖方向理顺；不要用 `@Lazy` 绕过 |

---

## 事件解耦设计（步骤 4-5 核心）

```java
// UserService 发事件，不直接调通知/审计
public User createUser(...) {
    User user = userMapper.insert(...);
    publisher.publishEvent(new UserCreatedEvent(user));
    return user;
}

// NotificationService 监听
@EventListener
public void on(UserCreatedEvent e) { sendWelcomeNotification(e.user()); }

// AuditService 监听（独立事务）
@EventListener
@Async
@Transactional(propagation = REQUIRES_NEW)
public void on(UserCreatedEvent e) { logUserAction("CREATE", e.user()); }
```

**收益**：彻底切断 UserService → Notification / Audit 的方向依赖，根除循环依赖隐患。
**代价**：调用链变隐式；用 `@TransactionalEventListener(phase = AFTER_COMMIT)` 控制时机（避免在事务回滚后还发通知）。

---

## 不推荐近期做

| 项 | 不推荐原因 | 重新评估时机 |
|----|----------|-----------|
| 把 `RedisTemplate` 抽成 `UserCacheService` | 当前 Redis 用法仅在 Notification 中限频，拆出 NotificationService 后已收敛 | 出现第二处 Redis 使用时再抽 |
| 引入 MapStruct | 当前 UserService 不涉及 VO/DTO 转换 | 拆出对外 Facade 时一并考虑 |
| 改为 Spring Modulith 模块化 | 单仓拆服务即可满足；模块化是更大跨度的架构改动 | 团队对子域共识稳定后 |

---

## 进度建议

- **本周可完成**：步骤 1-3（特征化测试 + 构造器注入 + 类内分组），共约 1 天
- **下周排期**：步骤 4-5（拆 Notification + Audit），共约 1 天
- **第二个迭代**：步骤 6-7（拆 Permission + 事务收紧），共约 1 天
- **第三个迭代**：步骤 8-9（Facade + 调用方迁移 + 删除），跨 PR

---

## 待用户确认

1. 是否同意此顺序（先叶子 Notification/Audit → 中间 Permission → 最后定型 UserService）？
2. 是否同意通知/审计改事件驱动（语义从"强一致"变成"最终一致 + AFTER_COMMIT"）？
3. 是否需要把"步骤 1-5"作为一个 PR 提交，"步骤 6-9"作为另一个 PR？
4. 是否允许新增 4 个子包（`user/user`、`user/permission`、`user/audit`、`user/notification`）？还是平铺在同一个包？

---

继续 Step 3 展开具体步骤吗？我会优先展开步骤 4（拆 NotificationService）与步骤 5（拆 AuditService），这是含 Spring 特定细节最多的两步。
