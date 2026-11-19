# UserService 上帝类拆分分析

你这个 UserService 是典型的 **God Class（上帝类）+ Divergent Change（发散式变化）**。一个类同时承担了用户管理、RBAC、审计、通知四个子领域的职责，注入了 11 个依赖，700+ 行。每加一个新功能都要在同一个类里改，团队之间也会频繁产生 merge 冲突。下面给你一份完整的诊断 + 拆分路线图 + 风险提醒。

---

## 一、诊断报告

| 坏味道 | 严重度 | 证据 | 推荐手法 |
|---|---|---|---|
| God Class（上帝类） | 高 | 单类 700+ 行、11 个依赖、4 个子域方法 | Extract Class（按子域拆分） |
| Divergent Change（发散式变化） | 高 | 用户/权限/审计/通知任一变更都会改这个类 | Extract Class + 按 SRP 分包 |
| Feature Envy（特性依恋）潜在 | 中 | Notification 方法操作的几乎全是 SmsClient/EmailClient | Move Method 到 NotificationService |
| 过宽事务边界 | 中 | 所有方法都 `@Transactional`，连 `findUser`、`sendXxx` 这种只读/外部 IO 也包在事务里 | 拆分后重新评估事务粒度（只读用 `readOnly=true`，外部 IO 不进事务） |
| 隐式跨子域耦合 | 中 | createUser 大概率内联调用了 sendWelcomeNotification + logUserAction | 拆分后通过 ApplicationEvent 解耦 |
| 多职责依赖注入 | 中 | NotificationSender / SmsClient / EmailClient 三个通知通道堆在一起 | 抽象 NotificationChannel 策略 |

---

## 二、拆分目标架构

按子域拆成 4 个 Service + 1 个门面（如果上层调用方多到无法一次切换，可保留 UserService 作为 facade 做透传，过渡期内逐步下线）：

```
UserService (核心，只做用户 CRUD)
  └─ UserMapper

PermissionService (RBAC)
  ├─ RoleMapper
  ├─ PermissionMapper
  └─ 依赖：UserService（只读查用户是否存在）

AuditService (审计，叶子模块，无业务依赖)
  └─ AuditLogMapper

NotificationService (通知，叶子模块)
  ├─ NotificationSender / SmsClient / EmailClient
  └─ 内部可再抽 NotificationChannel 策略
```

**依赖方向（DAG）**：UserService 不反向依赖 Permission/Audit/Notification——这一点很关键，能避免循环依赖。Permission/Audit/Notification 通过事件订阅 UserService 发出的领域事件。

---

## 三、拆分路线图（按顺序执行）

**核心原则**：先拆叶子（无业务依赖），再拆中间层；每一步可独立提 PR、独立回归。

### Step 1：拆 AuditService（叶子，最安全）

- 为什么先拆它：只依赖 AuditLogMapper，不被其他子域反向依赖，没有事务嵌套问题。
- 工作量：1 人天
- 风险：极低
- 验收：UserService 内部把 `auditLogMapper` 的调用全部替换为 `auditService.xxx`，原方法签名不变。

### Step 2：拆 NotificationService（叶子）

- 为什么次之：依赖 3 个外部通道客户端，但不依赖其他业务子域。
- 注意：通知通常**不应该在数据库事务里**。原 `@Transactional` 方法直接调发短信/邮件，如果事务回滚，邮件已经发出去了——拆分时顺手修掉，把外部 IO 移出事务（参考下面"事务边界"一节）。
- 工作量：1 ~ 2 人天
- 验收：调用方改为 `notificationService.sendWelcomeNotification(user)`，并验证发送动作发生在事务提交之后（可用 `@TransactionalEventListener(AFTER_COMMIT)`）。

### Step 3：拆 PermissionService（依赖 UserService）

- 为什么放第三：依赖 UserService，但 UserService 反过来不依赖它。
- 注意 `hasPermission` 这类**高频只读**方法：拆分后建议加 `@Transactional(readOnly = true)` 或者干脆不加事务，配合 Redis 缓存。
- 工作量：2 ~ 3 人天
- 验收：权限相关接口性能不降，RBAC 单测覆盖率不掉。

### Step 4：UserService 瘦身

- 此时 UserService 应只剩 createUser / updateUser / deleteUser / findUser / listUsers。
- 把 createUser 里"发欢迎通知 + 记审计"的内联调用改为发 `UserCreatedEvent`，由 NotificationService / AuditService 用 `@EventListener` 订阅。这是打破未来潜在循环依赖的关键。
- 工作量：1 ~ 2 人天

### Step 5（可选）：保留 UserService 作为 Facade 一段时间

- 如果上游调用方很多，一次切换风险大，可让旧的 `UserService.sendWelcomeNotification` 直接委托给 `notificationService.sendWelcomeNotification`，加 `@Deprecated`，给上游一个迁移窗口。等调用方都迁完再删。

---

## 四、Spring 特定风险（必须提醒）

### 1. `@Transactional` 边界变化

- 拆分前：A → B 是**同一个类内部调用**，事务从外层方法开始，传播给内部方法。
- 拆分后：A → B 变成**跨 Bean 调用**，B 上的 `@Transactional` 才会真正生效（Spring AOP 代理基于 Bean 边界）。
- 行动项：
  - 检查原方法里有没有**自调用**（`this.xxx()` 调用另一个 `@Transactional` 方法）——这种在原类里**事务本来就没生效**，拆出去之后反而生效了，可能暴露隐藏 bug。
  - 决定每个方法的传播级别：`REQUIRED`（默认）、`REQUIRES_NEW`（审计日志独立事务，主流程回滚也要落库）、`SUPPORTS`（只读查询）。
  - 外部 IO（发短信、发邮件、调第三方）**移出事务**，用 `@TransactionalEventListener(AFTER_COMMIT)`。

### 2. AOP 切面影响

- 如果项目里有自定义切面（如 `@LogExecution`、`@RateLimit`）按类名 / 包路径匹配，拆分后切面可能漏切或多切。
- 行动项：grep 所有 `@Pointcut`、`@Around`、`execution(... com.x.UserService.*)`，逐个评估。

### 3. Spring 注入点变化

- 调用方原来注入 `UserService`，现在可能需要同时注入 `UserService` + `PermissionService` + `AuditService` + `NotificationService`。
- 建议**一次只拆一个**，每次拆完跑全量回归 + 上游编译，不要一把梭。
- 注意 `@Autowired` 按类型注入，如果有人通过 `@Qualifier` 或 `BeanFactory.getBean("userService")` 字符串拿 Bean，要重点 grep。

### 4. 循环依赖预防

拆分后最容易出现的循环：

- **PermissionService ↔ UserService**：如果 UserService.createUser 里要"给新用户默认角色"，又调回 PermissionService，而 PermissionService 又要查 User——就循环了。
  - **打破方案 A**：把"给默认角色"作为 `UserCreatedEvent` 的事件监听器放在 PermissionService 里，UserService 只发事件，不直接调 PermissionService。
  - **打破方案 B**：抽 `UserReader`（只读接口）给 PermissionService 用，UserService 实现该接口；权限写入由 PermissionService 独占。
- **NotificationService → UserService**（通知需要查用户邮箱）+ **UserService → NotificationService**（发欢迎通知）：
  - 解法同上，UserService 改为发 `UserCreatedEvent(user)`，事件里直接带 user 对象，NotificationService 不需要回查 UserService。

### 5. 测试覆盖率保护

你目前覆盖率 65%，拆分过程中**每一步都要保证覆盖率不降**：

- 拆 Service 前，先把原方法的行为补一份**特征化测试（characterization test）**，断言现状行为。
- 拆完后，原测试改为针对新 Service，旧 UserServiceTest 里只保留 user CRUD 部分。
- 跑一次 mutation testing（PIT）会比单纯看行覆盖率更有信心。

### 6. MyBatis 相关

- 每个新 Service 注入对应的 Mapper，注意 `@MapperScan` 包路径覆盖范围。
- 如果有二级缓存配置，拆分后可能影响缓存命中（不同 Service 里查同一表），建议拆完后压一次主链路性能。

---

## 五、不建议的做法

- **不要一次大爆炸式重构**：4 个 Service 同时拆，一个 PR 几千行，review 不动、出问题也定位不到。
- **不要保留"门面 + 全量委托"作为终态**：facade 只能是过渡，否则你只是把 700 行从一个类移到了另一个类的入口。
- **不要在没有特征化测试的情况下动 createUser 这种核心写入路径**：先补测试再动手。

---

## 六、下一步建议

如果你确认这个拆分方向，建议从 **Step 1（AuditService）** 开始，我可以给你出 Step 1 的具体执行步骤——包括 before/after 代码对比、机械化拆分步骤、回归测试命令、回滚方案。要继续吗？

也可以告诉我一些信息帮我把方案再精确化：

1. 调用方有多少（同模块 vs 跨服务）？是否允许小范围 API 改动？
2. 是否已有 ApplicationEvent 的使用习惯？团队对事件驱动接受度如何？
3. createUser 里是否真的内联调用了 sendWelcomeNotification 和 logUserAction？还是只是命名上分组？
4. `@Transactional` 传播级别目前是否都是默认的 REQUIRED？
