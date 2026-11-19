# 重构步骤详解：拆分 UserService

本文档展开路线图中的关键步骤。每步原子化、单 commit 可回滚。Spring 特定细节（事务边界、AOP、循环依赖预防）在"影响范围"中显式标出。

---

## 重构步骤 #4：Extract Class —— NotificationService（叶子子域，优先拆）

**手法**：Extract Class（`refactoring-techniques.md` §7.2） + Spring `ApplicationEvent` 解耦（`spring-specific.md` §循环依赖处理）
**坏味道来源**：诊断 #1（上帝类）、#3（通知数据泥团）、#7（AOP self-invocation）
**对应路线图**：步骤 4

### 影响范围

- **修改文件**：`UserService.java`（删除 3 个 sendXxxNotification 方法及 3 个通知相关 `@Autowired`；在创建/重置密码/安全告警处改为 `publisher.publishEvent(...)`）
- **新增文件**：
  - `NotificationService.java`（新 `@Service`）
  - `event/UserCreatedEvent.java` / `event/PasswordResetEvent.java` / `event/SecurityAlertEvent.java`（Java 17 `record`）
- **API 变更**：`UserService.sendWelcomeNotification(...)` 等 3 个公有方法 → 在 Facade 阶段保留转发（步骤 8），最终删除
- **数据库变更**：无
- **事务边界变化**：
  - **原行为**：`createUser` 中调 `sendWelcomeNotification`，self-invocation，sendXxx 的 `@Transactional` **未生效**，与 createUser 共用同一事务
  - **新行为**：事件监听标 `@TransactionalEventListener(phase = AFTER_COMMIT)` + `@Async` + `@Transactional(propagation = REQUIRES_NEW)`，**通知在主事务提交后独立线程异步发出**
  - 这是**有意的语义变化**——通知失败不应回滚用户创建
- **AOP 切面**：通知方法的日志/监控切面，原本因 self-invocation 失效，现在会真的生效。需验证不要因此产生新的副作用（如重复埋点）

### 前置条件

- [x] Step 1 已补特征化测试，覆盖 `createUser` / `updateUser` 触发通知的路径
- [x] Step 2 已改构造器注入
- [x] Step 3 已在类内对通知相关代码做分组与 helper 抽取
- [ ] 已确认事件载荷字段（User 对象 vs userId + 必要字段）

### Before

```java
// UserService.java（节选）
@Service
public class UserService {
    private final NotificationSender notificationSender;
    private final SmsClient smsClient;
    private final EmailClient emailClient;
    private final RedisTemplate<String, Object> redis;
    // ... 其他依赖

    @Transactional
    public User createUser(...) {
        User user = userMapper.insert(...);
        logUserAction("CREATE", user);
        sendWelcomeNotification(user);   // self-invocation：@Transactional 不生效
        return user;
    }

    @Transactional
    public void sendWelcomeNotification(User user) {
        // 40 行：限频 redis check + 多通道（邮件 + 短信）调度 + 失败兜底
    }
}
```

### After

```java
// UserService.java（节选）
@Service
public class UserService {
    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final TenantContextHolder tenantHolder;
    private final ApplicationEventPublisher publisher;   // 新增

    @Transactional
    public User createUser(...) {
        User user = userMapper.insert(...);
        publisher.publishEvent(new UserCreatedEvent(user));   // 事件解耦
        return user;
    }
    // sendWelcomeNotification 已删除
}

// event/UserCreatedEvent.java
public record UserCreatedEvent(User user) {}

// NotificationService.java（新文件）
@Service
public class NotificationService {
    private final NotificationSender sender;
    private final SmsClient sms;
    private final EmailClient email;
    private final RedisTemplate<String, Object> redis;

    public NotificationService(NotificationSender sender, SmsClient sms,
                               EmailClient email, RedisTemplate<String, Object> redis) {
        this.sender = sender; this.sms = sms; this.email = email; this.redis = redis;
    }

    @Async
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onUserCreated(UserCreatedEvent event) {
        sendWelcomeNotification(event.user());
    }

    void sendWelcomeNotification(User user) { /* 原 40 行逻辑 */ }
    // sendPasswordResetNotification / sendSecurityAlert 同样模式
}
```

### 机械化步骤（Fowler mechanics）

1. **新建空 `NotificationService` 类**，标 `@Service`，加构造器（暂只注入 4 个通知相关依赖）。编译通过。
2. **复制**（不是移动）`sendWelcomeNotification` 到 `NotificationService`，包级可见（`package-private`）。编译通过。
3. 在 `UserService` 注入 `NotificationService`，把原 `sendWelcomeNotification(user)` 调用改为 `notificationService.sendWelcomeNotification(user)`。**保留原 UserService 的 public 方法作转发**（向后兼容）。编译 + 跑测试 → 应全绿（因为还是同步调用）。
4. **commit 一次**："Extract NotificationService, keep facade"。
5. 新建 `UserCreatedEvent` record。
6. 在 `UserService.createUser` 中追加 `publisher.publishEvent(new UserCreatedEvent(user))`（**保留旧的直接调用**，双触发）。在 `NotificationService.sendWelcomeNotification` 内加幂等 guard（如检查 redis key 防重）。跑测试。
7. **commit**："Add event publishing, keep dual-trigger"。
8. 在 `NotificationService` 加 `@TransactionalEventListener(AFTER_COMMIT)` + `@Async` 的 `onUserCreated` 方法，调用 sendWelcomeNotification。
9. **删除** `UserService.createUser` 中的直接调用 `notificationService.sendWelcomeNotification(...)`。只留事件发布。跑测试（注意 `@Async` 在测试中可能需要 `@RecordApplicationEvents` 或同步配置）。
10. **commit**："Switch to event-driven notification"。
11. 重复 5-10 步处理 `PasswordResetEvent` 与 `SecurityAlertEvent`。
12. 在主类配置 `@EnableAsync`（若尚未启用）；为 `@Async` 配置专用 `TaskExecutor`（避免共用默认线程池被通知打满）。

### 验证

```bash
mvn test -Dtest=UserServiceTest,NotificationServiceTest
mvn verify  # 含集成测试，验证事件链路
```

期望：
- `createUser_should_send_welcome_notification`（特征化测试）仍绿——验证语义一致
- 新加 `createUser_when_notification_fails_should_not_rollback_user`——验证新语义（通知失败不影响主事务）
- Spring 上下文启动正常，无 `BeanCurrentlyInCreationException`
- 启动日志确认 `@EnableAsync` 与 `TaskExecutor` 配置就位

### 回滚策略

- **粒度**：步骤 1-12 拆为 6-8 个 commit，每个独立可 revert
- **关键 commit**："Switch to event-driven notification" 是行为变化点，单独 commit，便于精准回滚
- **副作用**：通知是外部副作用（邮件/短信），回滚仅恢复代码不撤回已发通知；测试环境应使用 mock sender

### 循环依赖预防检查

- [ ] `NotificationService` 是否注入了 `UserService`？**禁止**——事件载荷已携带 `User` 对象
- [ ] 若 NotificationService 需要查最新用户信息：用 `UserQueryPort` 接口隔离（实现单向）
- [ ] Spring Boot 3 默认 `spring.main.allow-circular-references=false`，启动失败即说明设计错误，不要打开此开关

### 后续衔接

完成本步骤 → 启用步骤 #5（拆 AuditService，同样事件驱动模式）

---

## 重构步骤 #5：Extract Class —— AuditService（与 #4 并行，叶子子域）

**手法**：Extract Class + `ApplicationEvent` + `@Async` + `@Transactional(propagation = REQUIRES_NEW)`
**坏味道来源**：诊断 #1（上帝类）、#4（霰弹式审计调用）
**对应路线图**：步骤 5

### 影响范围

- **修改文件**：`UserService.java`（删除 `logUserAction` / `queryAuditLogs` / `generateAuditReport`；删除 `auditLogMapper` 注入；所有 `logUserAction("XXX", user)` 调用改为发事件）
- **新增文件**：
  - `AuditService.java`（新 `@Service`）
  - `event/UserActionAuditEvent.java`
- **API 变更**：
  - `queryAuditLogs` / `generateAuditReport` 是**对外查询接口**，应**移动**到 AuditService 而非通过事件（这两个是同步查询，不适合事件）
  - `logUserAction` 退化为内部实现细节，仅由事件触发
- **事务边界变化**（**重点**）：
  - **原行为**：`updateUser` 中调 `logUserAction`，self-invocation，审计与主操作**共用同一事务**——主操作失败时审计也回滚
  - **新行为**：`@Async` + `@TransactionalEventListener(AFTER_COMMIT)` + `@Transactional(REQUIRES_NEW)`，审计**仅在主事务提交后异步独立写入**
  - **语义变化点**：失败的操作不再有审计记录。如果安全合规要求"无论成败都留痕"，应改为 `@EventListener(condition = "...")` 同步监听 + `REQUIRES_NEW`，主事务回滚不影响审计提交
- **AOP 切面**：若有针对 `logUserAction` 的切面（如性能监控），切点表达式需更新到新类

### 前置条件

- [x] 特征化测试已固化"操作失败时审计是否记录"的当前行为
- [x] 已与业务/合规方确认：失败操作是否需要审计记录（决定 `phase` 用 `AFTER_COMMIT` 还是 `AFTER_COMPLETION`）

### Before

```java
@Service
public class UserService {
    @Autowired private AuditLogMapper auditLogMapper;
    // ...

    @Transactional
    public User updateUser(String id, UpdateRequest req) {
        User user = userMapper.selectById(id);
        userMapper.update(applyChanges(user, req));
        logUserAction("UPDATE", user);   // 同事务；self-invocation
        return user;
    }

    @Transactional
    public void logUserAction(String action, User user) {
        AuditLog log = new AuditLog();
        log.setAction(action);
        log.setUserId(user.getId());
        log.setTenantId(tenantHolder.current());
        log.setTimestamp(Instant.now());
        auditLogMapper.insert(log);
    }
}
```

### After

```java
// UserService.java
@Service
public class UserService {
    private final ApplicationEventPublisher publisher;
    // 已无 auditLogMapper 注入

    @Transactional
    public User updateUser(String id, UpdateRequest req) {
        User user = userMapper.selectById(id);
        User updated = userMapper.update(applyChanges(user, req));
        publisher.publishEvent(new UserActionAuditEvent("UPDATE", updated, tenantHolder.current()));
        return updated;
    }
}

// event/UserActionAuditEvent.java
public record UserActionAuditEvent(String action, User user, String tenantId) {}

// AuditService.java
@Service
public class AuditService {
    private final AuditLogMapper auditLogMapper;

    public AuditService(AuditLogMapper auditLogMapper) {
        this.auditLogMapper = auditLogMapper;
    }

    // 关键决策点：合规要求决定 phase
    //   AFTER_COMMIT  → 仅成功操作留痕（一般业务可接受）
    //   AFTER_COMPLETION + REQUIRES_NEW → 无论成败都留痕（合规场景）
    @Async("auditExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void onUserAction(UserActionAuditEvent event) {
        AuditLog log = new AuditLog();
        log.setAction(event.action());
        log.setUserId(event.user().getId());
        log.setTenantId(event.tenantId());
        log.setTimestamp(Instant.now());
        auditLogMapper.insert(log);
    }

    // 查询类方法直接搬移（同步、有事务、只读）
    @Transactional(readOnly = true)
    public List<AuditLog> queryAuditLogs(AuditQuery query) { /* 原逻辑 */ }

    @Transactional(readOnly = true)
    public AuditReport generateAuditReport(ReportRequest req) { /* 原逻辑 */ }
}
```

### 机械化步骤

1. 新建 `AuditService` 空类 + 构造器注入 `AuditLogMapper`。编译。
2. **Move Method**：`queryAuditLogs` / `generateAuditReport` 从 UserService 整体搬到 AuditService。`UserService` 中保留转发：`return auditService.queryAuditLogs(query);`（兼容）。编译 + 跑测试。**commit**。
3. 在 `AuditService` 复制 `logUserAction` 为 `auditUserAction(String action, User user, String tenantId)`（无 `tenantHolder` 依赖，参数化注入）。**commit**。
4. 新建 `UserActionAuditEvent` record。
5. 在 `UserService` 各调用点 `logUserAction("XXX", user)` 处追加 `publisher.publishEvent(new UserActionAuditEvent(...))`（保留旧调用，双触发并加幂等 guard）。跑测试。**commit**。
6. 在 `AuditService` 加 `@TransactionalEventListener(AFTER_COMMIT)` + `@Async` + `@Transactional(REQUIRES_NEW)` 的 `onUserAction`，调用内部 `auditUserAction`。**commit**。
7. 配置 `auditExecutor` Bean（独立线程池，避免和通知共用打满）：
   ```java
   @Bean("auditExecutor")
   public TaskExecutor auditExecutor() {
       ThreadPoolTaskExecutor exec = new ThreadPoolTaskExecutor();
       exec.setCorePoolSize(2); exec.setMaxPoolSize(8);
       exec.setQueueCapacity(500); exec.setThreadNamePrefix("audit-");
       exec.initialize(); return exec;
   }
   ```
8. 删除 `UserService.logUserAction` 及所有 `logUserAction(...)` 直接调用，只保留事件发布。跑测试。**commit**：行为切换点。
9. 删除 `UserService.auditLogMapper` 注入。编译。**commit**。

### 验证

```bash
mvn test -Dtest=UserServiceTest,AuditServiceTest
mvn verify
```

期望：
- 原有审计测试全绿（验证成功路径审计仍记录）
- **新加测试**：`updateUser_when_db_fails_should_not_audit`（验证新语义：主事务回滚后审计不写入；若合规要求相反则反向断言）
- 启动正常，`auditExecutor` 线程池可见
- 日志确认审计事件在事务提交**后**写入（时间戳对比）

### 回滚策略

- **粒度**：9 个独立 commit
- **行为切换 commit（步骤 8）单独可 revert**：一旦发现审计丢失或行为不符，可只回退此一步，回到双触发状态
- **副作用**：审计表写入是幂等 append，回滚不需要清理已写入数据（最多冗余）

### 循环依赖预防检查

- [ ] `AuditService` **禁止**注入 `UserService` / `PermissionService`（事件载荷已携带必要信息）
- [ ] 不要在 `UserService` 注入 `AuditService` 后又让 AuditService 反向查 UserService——这种环路通过事件天然切断
- [ ] 启动时观察 Spring 是否报循环依赖警告，是则立刻回到上一 commit 重新设计依赖方向

### 后续衔接

完成本步骤 → 启用步骤 #6（拆 PermissionService）。注意 PermissionService 不是叶子，需要注入 `UserMapper`（只读），拆分时增加接口隔离评估。

---

## 通用约定（适用于所有 Extract Class 步骤）

| 项 | 约定 |
|----|-----|
| commit 粒度 | 每个机械化子步骤一个 commit；行为变化点（切换为事件驱动）单独 commit |
| 测试命令 | 拆分后单 Service 一个测试类；集成测试覆盖跨 Bean 调用 |
| 切面验证 | 拆分前后用 `@SpringBootTest` 启动上下文，断言关键 Bean 与切面就位 |
| `@Transactional` 自检清单 | 1) 是否标在 public 方法？ 2) 是否仍在同 Bean self-invocation？ 3) 传播行为是否符合预期？ |
| 循环依赖自检 | 启动期 Spring 报错 = 设计问题，不要用 `@Lazy` / `setter 注入` 绕过 |
| 包结构 | 建议子包 `user/notification`、`user/audit`、`user/permission`，事件放 `user/event` 公共包 |

---

完成步骤 4-5 后，建议回到 Step 1 重新扫描 `UserService`——很多坏味道（11 字段注入、事务边界混乱、霰弹式修改）会一并消失，剩余的可能是新生坏味道（如 Event 类型过多需要再聚合）。
