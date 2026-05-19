# Spring / Spring Boot 重构专题

本文档处理 Spring 与 Spring Boot 项目中**特有的**重构场景。通用 Java 重构手法见 `refactoring-techniques.md`；本文档只补充 Spring 上下文带来的额外约束与机会。

---

## §分层架构与职责泄露

Spring 项目典型分层：

```
Controller (Web)
   ↓
Service (业务)
   ↓
Repository / Mapper (数据)
   ↓
Entity / DTO / VO
```

### 常见职责泄露

| 泄露方向 | 症状 | 修复 |
|---------|------|------|
| Controller → Repository | Controller 直接注入 Mapper、绕过 Service | 把数据访问搬到 Service |
| Controller 业务逻辑 | Controller 方法 > 30 行，含业务规则 | 抽到 Service / DomainService |
| Service → 视图层 | Service 返回 ResponseEntity / HTTP 状态码 | Service 只返回领域对象，Controller 负责包装响应 |
| Service → 持久化细节 | Service 出现 `EntityManager.flush()` / SQL 字符串 | 封装到 Repository 抽象 |
| Repository → 业务规则 | Mapper 方法名含业务条件如 `findActiveVipOrdersInLastMonth` | 评估是否该上移到 Service |
| 跨模块直连 | `OrderService` 注入 `inventory.InventoryMapper` | 通过模块对外 Service 调用，不绕开 |

### 修复手法

**Move Method**（见 `refactoring-techniques.md` §7.1）的 Spring 适配版：

1. 在目标层创建新 Bean / 新方法
2. 原方法变成转发（持续转发期内同时保留两份）
3. 调用方逐个迁移到新位置
4. 转发空了再删除

---

## §@Service 上帝类拆分

### 识别

- 单个 `@Service` 类 > 500 行
- 字段（多为 `@Autowired` 依赖）> 10 个
- 公共方法跨多个业务子域（如 `UserService` 同时处理：用户、权限、审计、通知）

### 拆分维度

| 拆分维度 | 适用场景 | 示例 |
|---------|---------|------|
| 按子领域 | 一个 Service 跨多个业务对象 | UserService → UserService + PermissionService + AuditService |
| 按读/写 | CQRS 风格 | OrderService → OrderQueryService + OrderCommandService |
| 按调用方 | 一个 Service 同时供 Web / Job / MQ 调用 | 抽公共 OrderDomainService + OrderWebService + OrderJobService |
| 按事务边界 | 一个 Service 内部分有/无事务的方法 | 把无事务的查询方法独立成 ReadOnlyService |

### 拆分步骤（含 Spring 特定考虑）

1. **画依赖图**：在拆分前列出方法间的调用关系，找出"少依赖、易切出的叶子方法"
2. **创建新 `@Service` Bean**：先建空类，加 `@Service` 注解
3. **逐个 Move Method**：用 `refactoring-techniques.md` §7.1 的步骤
4. **检查事务边界**：每移一个方法，确认 `@Transactional` 注解是否需要在新类上重新声明
5. **检查 AOP 切面**：日志、性能监控、权限等切面是否仍然生效（切点表达式可能依赖原类名）
6. **更新调用方注入**：调用方从注入 1 个 Bean 变为注入 2 个 Bean
7. **运行集成测试**：确保 Spring 上下文能启动，所有切面生效

### 拆分中的 Spring 陷阱

- **循环依赖**：拆完后 A 注入 B、B 注入 A → Spring 会失败。见 §循环依赖处理
- **@Transactional 失效**：同类内 `methodA` 调用 `methodB`，B 的 `@Transactional` 不生效。拆分后跨类调用反而能让事务生效——但要小心**反向**：原本同类内调用不受事务影响的代码，拆分后突然受事务管理
- **AOP 失效**：Spring AOP 基于代理，**self-invocation 不走代理**。`@Async`、`@Cacheable`、`@Transactional` 同类内调用都无效。拆分通常能修复这个问题
- **@Lazy 注入**：临时打破循环依赖，但不推荐长期保留

---

## §@Transactional 边界

### 常见错误

1. **`@Transactional` 标在 private 方法上** → 不生效（Spring AOP 代理只拦截 public）
2. **同类内调用** → 不生效（self-invocation 不走代理）
3. **`@Transactional` 标在 Controller 上** → 反模式（事务应当在 Service 层）
4. **过粗的事务**：整个方法 `@Transactional`，但只有 2 行需要事务，其余是远程调用 → 拉长事务时间，DB 连接占用过多
5. **过细的事务**：每个 Service 方法独立事务，业务上需要原子性的两步分别提交 → 数据不一致

### 重构方向

**收紧事务范围**：
```java
// Before：整个方法都在事务中
@Transactional
public void placeOrder(OrderRequest req) {
    Order order = buildOrder(req);              // 无 DB 操作
    Address addr = geoService.lookup(req.getAddr()); // 远程调用！事务被拉长
    orderRepo.save(order);
    auditService.log(order);
}

// After：缩小事务，只覆盖真正的 DB 操作
public void placeOrder(OrderRequest req) {
    Order order = buildOrder(req);
    Address addr = geoService.lookup(req.getAddr());
    saveOrderTransactionally(order, addr);  // 只这一行在事务中
}
@Transactional
protected void saveOrderTransactionally(Order order, Address addr) {
    orderRepo.save(order);
    auditService.log(order);
}
```

**注意**：protected 方法同类调用仍然不生效。解决方案：
- 把事务方法搬到另一个 Spring Bean（推荐）
- 用 `TransactionTemplate` 编程式事务
- 注入自己的代理（`self`，复杂且不推荐）

**事务传播行为**：

| 传播行为 | 典型场景 |
|---------|---------|
| REQUIRED（默认）| 大多数业务方法 |
| REQUIRES_NEW | 独立事务，如审计日志（不受主事务回滚影响）|
| NESTED | 子事务可单独回滚 |
| SUPPORTS | 查询方法 |
| MANDATORY | 必须在事务内调用（断言用） |
| NOT_SUPPORTED / NEVER | 明确不要事务 |

---

## §Controller 瘦身

### 目标

Controller 方法应当只做 4 件事：

1. **接收**：参数绑定 + `@Valid` 触发校验
2. **委托**：调用 Service
3. **包装**：把 Service 返回值转 DTO
4. **响应**：返回 ResponseEntity 或直接返回 DTO

不应当做：业务规则、数据访问、复杂转换。

### 重构手法

**1. 提取 DTO Mapper**：
```java
// Before
@PostMapping
public OrderVO create(@RequestBody @Valid OrderRequest req) {
    Order order = new Order();
    order.setCustomerId(req.getCustomerId());
    order.setAmount(req.getAmount());
    // ... 10 行字段拷贝
    Order saved = orderService.placeOrder(order);
    OrderVO vo = new OrderVO();
    vo.setOrderId(saved.getId());
    // ... 8 行字段拷贝
    return vo;
}

// After
@PostMapping
public OrderVO create(@RequestBody @Valid OrderRequest req) {
    Order order = orderMapper.toDomain(req);
    Order saved = orderService.placeOrder(order);
    return orderMapper.toVO(saved);
}
```

可以用 MapStruct 自动生成 Mapper（推荐），或手写 Mapper 类。

**2. 提取异常处理**：
```java
// Before：每个 Controller 都有 try-catch
@PostMapping
public ResponseEntity<?> create(@RequestBody OrderRequest req) {
    try {
        return ResponseEntity.ok(orderService.placeOrder(req));
    } catch (InventoryException e) {
        return ResponseEntity.badRequest().body(...);
    } catch (PaymentException e) {
        return ResponseEntity.status(402).body(...);
    }
}

// After：抽到 @ControllerAdvice
@ControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(InventoryException.class)
    public ResponseEntity<?> handle(InventoryException e) { /* ... */ }
    @ExceptionHandler(PaymentException.class)
    public ResponseEntity<?> handle(PaymentException e) { /* ... */ }
}
// Controller 干净
@PostMapping
public OrderVO create(@RequestBody @Valid OrderRequest req) {
    return orderMapper.toVO(orderService.placeOrder(req));
}
```

**3. 提取参数校验**：
- 简单校验用 `@Valid` + Bean Validation 注解（`@NotNull` / `@Size` / `@Pattern`）
- 跨字段校验用 `@AssertTrue` 方法或自定义 `ConstraintValidator`
- 业务校验留在 Service（如"用户是否实名"这种需要查 DB 的校验）

---

## §循环依赖处理

### 识别

- Spring 启动报 `BeanCurrentlyInCreationException`
- 现有代码用 `@Lazy` "临时"打破循环（已经存在的味道）
- 编译能过但启动时 Bean 无法注入

### 修复方向

**1. 引入第三方（依赖倒置）**：
```
原：A ↔ B（循环）
改：A → C ← B（C 是接口或新 Bean）
```

**示例**：
```java
// Before
@Service
public class OrderService {
    @Autowired UserService userService;
}
@Service
public class UserService {
    @Autowired OrderService orderService; // 循环
}

// After：把循环点抽到第三方
@Service
public class OrderService {
    @Autowired UserQueryPort userQueryPort; // 接口
}
@Service
public class UserService {
    @Autowired OrderQueryPort orderQueryPort; // 接口
}
// UserQueryPort 实现单独在 UserQueryAdapter Bean
// OrderQueryPort 实现单独在 OrderQueryAdapter Bean
// 接口在公共模块，实现单向依赖
```

**2. Move Method**：把循环点上的方法搬到第三方类。

**3. 事件解耦**：用 Spring `ApplicationEvent` 替代直接调用。
```java
// Before：OrderService 直接调用 NotifyService
orderRepo.save(order);
notifyService.send(order); // 假设 NotifyService 也依赖 OrderService

// After：发事件
orderRepo.save(order);
eventPublisher.publishEvent(new OrderPlacedEvent(order));
// NotifyService 监听事件
@EventListener
public void on(OrderPlacedEvent event) { /* ... */ }
```

**事件解耦的代价**：
- 调用链变得隐式，调试困难
- 默认同步，但容易误用 `@Async` 导致事务边界问题
- 适合**真正解耦**的场景（如审计、通知），不适合主业务链路

**4. 不推荐：@Lazy / setter 注入**
- `@Lazy` 只是延迟解析，仍然耦合
- setter 注入打破构造时检查，不推荐

---

## §配置类 vs 业务类

`@Configuration` 类应当**只做配置**，不应混入业务逻辑：

| 应当 | 不应当 |
|------|-------|
| `@Bean` 方法定义 | 在 `@Bean` 方法中调用业务 Service |
| 条件配置（`@ConditionalOn*`）| 用 `@Configuration` 类承担业务计算 |
| 属性绑定（`@ConfigurationProperties`）| 在 `@PostConstruct` 中触发业务流程 |

### 重构方向

```java
// Before：配置类混业务
@Configuration
public class OrderConfig {
    @Bean
    public OrderService orderService(OrderRepo repo) {
        OrderService svc = new OrderService(repo);
        svc.warmUpCache(); // 业务！配置类不该做
        return svc;
    }
}

// After：配置归配置、业务归业务
@Configuration
public class OrderConfig {
    @Bean
    public OrderService orderService(OrderRepo repo) {
        return new OrderService(repo);
    }
}
@Component
public class OrderCacheWarmer {
    @EventListener(ApplicationReadyEvent.class)
    public void warmUp() { orderService.warmUpCache(); }
}
```

---

## §策略模式与 Spring 注入

Spring 提供了优雅的策略模式实现：

```java
// 接口
public interface PaymentStrategy {
    boolean supports(PaymentType type);
    void charge(Payment payment);
}

// 实现们
@Component
public class AliPayStrategy implements PaymentStrategy {
    public boolean supports(PaymentType type) { return type == ALIPAY; }
    public void charge(Payment payment) { /* ... */ }
}
@Component
public class WeChatPayStrategy implements PaymentStrategy { /* ... */ }

// 路由
@Service
public class PaymentService {
    private final List<PaymentStrategy> strategies; // Spring 自动收集所有实现
    public PaymentService(List<PaymentStrategy> strategies) {
        this.strategies = strategies;
    }
    public void charge(Payment payment) {
        strategies.stream()
            .filter(s -> s.supports(payment.getType()))
            .findFirst()
            .orElseThrow(() -> new UnsupportedPaymentException(payment.getType()))
            .charge(payment);
    }
}
```

**优势**：
- 新增支付方式只需加一个 `@Component`，无需改 PaymentService
- 符合开闭原则
- 测试方便（Mock 单个 Strategy）

**对应重构手法**：Replace Conditional with Polymorphism（`refactoring-techniques.md` §8.1）的 Spring 版。

---

## §MyBatis 重构注意事项

MyBatis 项目的特殊重构关注点：

### 1. Mapper 方法重命名

Mapper 接口方法名与 XML `<select id="..."/>` 必须一致。重命名时：
1. IDE Refactor → Rename
2. 检查 XML 文件中的 id（IDE 通常会一起改，但要确认）
3. 检查 `@Mapper` 或 SQL 注解形式的 Mapper 是否也用了旧名

### 2. ResultMap 重构

- 多个 Mapper 复用同一个 ResultMap 时，集中放到公共 XML
- 字段映射用 `<resultMap>` 而非 `<select>` 内部别名（便于复用）

### 3. 动态 SQL 复杂度

- `<choose>` / `<when>` / `<otherwise>` 嵌套 > 3 层 → 考虑拆为多个 SQL
- 重复的 `<where>` / `<set>` 片段抽为 `<sql>` 引用

### 4. 与 Entity 的关系

- 不要把 `@TableField` / `@TableName` 这类 MyBatis-Plus 注解上的逻辑泄露到业务层
- DTO 与 Entity 分离（参见 `clean-code-rules.md`）

---

## §Spring Boot 配置重构

### `application.yml` / `application.properties`

- 按环境拆分 `application-dev.yml` / `application-prod.yml`
- 敏感信息用环境变量或外部配置中心，不写入 yml
- 业务相关配置封装为 `@ConfigurationProperties` 强类型类

### `@ConfigurationProperties` vs `@Value`

- `@Value` 适合单值；`@ConfigurationProperties` 适合一组相关配置
- `@ConfigurationProperties` 有 IDE 提示与验证（配合 `spring-boot-configuration-processor`）

```java
// 推荐
@ConfigurationProperties(prefix = "app.order")
public record OrderProperties(
    int maxItemsPerOrder,
    Duration timeout,
    boolean enableNotify
) {}

// 不推荐
@Value("${app.order.max-items-per-order}") int maxItems;
@Value("${app.order.timeout}") Duration timeout;
```

---

## §速查：Spring 重构常用手法对应

| Spring 场景 | 对应通用手法 | 本文档章节 |
|------------|-----------|----------|
| @Service 上帝类 | Extract Class | §@Service 上帝类拆分 |
| Controller 太厚 | Extract Method + 引入 Mapper | §Controller 瘦身 |
| 循环依赖 | Dependency Inversion / 事件解耦 | §循环依赖处理 |
| @Transactional 失效 | Move Method（跨类调用）| §@Transactional 边界 |
| 字段注入难测试 | 改构造函数注入 | `legacy-code.md` §依赖打破 |
| switch 选择支付方式 | Strategy + Spring 自动收集 | §策略模式与 Spring 注入 |
| 配置类有业务逻辑 | Move Method 到 @Component | §配置类 vs 业务类 |

---

## §与其他文档的衔接

- 识别"上帝类""循环依赖"等坏味道 → `smells-catalog.md`
- 通用重构手法的 mechanics → `refactoring-techniques.md`
- 拆 Service 前若无测试 → 先看 `legacy-code.md`
- 涉及领域模型重构（贫血→充血）→ `ddd-tactical.md`
- 输出格式 → `output-templates.md`
