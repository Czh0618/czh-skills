# DDD 战术模式与重构

本文档摘录 Eric Evans《领域驱动设计》中的**战术建模模式**，作为 Java 项目从"贫血模型"走向"充血模型"的重构指南。

**定位**：本文档只处理**战术层面**（值对象、聚合、领域服务、Repository），不涉及战略设计（限界上下文、Context Map）。战略设计建议先用 `/req-reverse-eng` 与 `/gspec-specify` 等更上游的工具。

---

## §核心模式速查

| 模式 | 一句话 | 何时使用 | 典型坏味道 |
|------|-------|---------|----------|
| **Value Object（值对象）** | 用值定义身份，不可变 | 描述事物的属性，无需追踪 | 数据泥团、基本类型偏执 |
| **Entity（实体）** | 用 ID 定义身份，有生命周期 | 需要追踪、有状态 | 贫血模型、上帝类 |
| **Aggregate（聚合）** | 一组紧密相关的对象组成的一致性边界 | 维护业务不变量 | 跨实体的事务、强一致性需求 |
| **Aggregate Root（聚合根）** | 聚合的唯一入口 | 防止聚合内部状态被绕过 | 外部直接修改子对象 |
| **Repository（资源库）** | 提供聚合的获取与持久化 | 替代 DAO，关注领域语义 | DAO 散落、跨聚合查询 |
| **Domain Service（领域服务）** | 不属于任何实体的领域逻辑 | 跨多个聚合的协作 | 上帝 Service |
| **Application Service（应用服务）** | 编排领域对象、处理事务/安全 | 用例入口、事务边界 | Controller 直连 Repository |
| **Domain Event（领域事件）** | 领域中发生的重要事件 | 解耦、审计、跨聚合通知 | 紧耦合的直接调用 |

---

## §Value Object（值对象）

### 识别

应当是值对象但被当作基本类型 / 数据泥团：
- `String customerEmail` → 应当是 `Email` 值对象
- `int amount + String currency` 总是同时出现 → `Money` 值对象
- `String province + city + district + detail` → `Address` 值对象
- `LocalDate from + LocalDate to` → `DateRange` 值对象

### 关键特征

1. **不可变**：所有字段 final，无 setter
2. **基于值的相等**：两个相同字段值的对象相等（equals/hashCode 基于所有字段）
3. **无副作用方法**：方法返回新对象，不修改自己（`money.add(other)` 返回新 Money）
4. **自验证**：构造时验证不变量

### 示例（Java 14+ record）

```java
public record Money(BigDecimal amount, Currency currency) {
    public Money {
        Objects.requireNonNull(amount);
        Objects.requireNonNull(currency);
        if (amount.signum() < 0) {
            throw new IllegalArgumentException("Money cannot be negative");
        }
    }
    public Money add(Money other) {
        ensureSameCurrency(other);
        return new Money(amount.add(other.amount), currency);
    }
    public Money multiply(BigDecimal factor) {
        return new Money(amount.multiply(factor), currency);
    }
    private void ensureSameCurrency(Money other) {
        if (!currency.equals(other.currency)) {
            throw new IllegalArgumentException("Currency mismatch");
        }
    }
}
```

### 重构步骤：从基本类型到值对象

1. **识别数据泥团**：哪几个字段/参数总是同时出现？
2. **创建值对象类**：用 record 或不可变 class
3. **加上构造时验证**：把分散在各 Service 的校验集中到构造函数
4. **加上业务方法**：把对该数据的操作（加减乘除、格式化、比较）从 Service 搬入值对象
5. **逐个替换调用点**：从最简单的位置开始，分多个 commit
6. **ORM 适配**：JPA `@Embeddable`、MyBatis `TypeHandler`

### Spring/MyBatis/JPA 适配

```java
// JPA
@Embeddable
public record Money(BigDecimal amount, String currency) {}

// 使用
@Entity
public class Order {
    @Embedded
    private Money totalAmount;
}

// MyBatis：用 TypeHandler 或拆字段映射
public class MoneyTypeHandler extends BaseTypeHandler<Money> { /* ... */ }
```

---

## §Entity（实体）

### 识别

应当是实体但被当作纯数据载体：
- `Order` 类只有字段和 getter/setter，所有业务逻辑在 `OrderService`
- `User` 的状态变更通过 `user.setStatus(2)` 直接赋值，绕过业务规则
- Order 状态机散落在多个 Service 中（"已支付"在 PaymentService、"已发货"在 ShippingService）

### 关键特征

1. **基于 ID 的相等**：两个 Order 即使其他字段都一样，ID 不同就是不同对象
2. **有生命周期**：创建 → 修改 → 销毁
3. **封装不变量**：业务规则在实体内部强制执行
4. **状态变更通过方法**：不暴露 setter，提供有业务含义的方法

### 重构示例：贫血 → 充血

```java
// Before（贫血）
public class Order {
    private String id;
    private OrderStatus status;
    private BigDecimal amount;
    // getter/setter ...
}
public class OrderService {
    public void pay(Order order, Payment payment) {
        if (order.getStatus() != OrderStatus.DRAFT) {
            throw new IllegalStateException();
        }
        if (payment.getAmount().compareTo(order.getAmount()) < 0) {
            throw new InsufficientPaymentException();
        }
        order.setStatus(OrderStatus.PAID);
        orderRepo.save(order);
    }
}

// After（充血）
public class Order {
    private final OrderId id;
    private OrderStatus status;
    private final Money amount;

    // 状态变更方法封装业务规则
    public void pay(Payment payment) {
        if (status != OrderStatus.DRAFT) {
            throw new IllegalStateException("Order is not in DRAFT status");
        }
        if (payment.amount().lessThan(amount)) {
            throw new InsufficientPaymentException(id, amount, payment.amount());
        }
        this.status = OrderStatus.PAID;
    }
}
public class OrderService {  // 现在是 Application Service
    public void pay(OrderId orderId, Payment payment) {
        Order order = orderRepo.findById(orderId).orElseThrow();
        order.pay(payment);  // 业务规则在 Order 内
        orderRepo.save(order);
    }
}
```

### 实体识别 vs 值对象识别

判断流程：

```
这个对象有 ID 吗？
├── 有 → Entity（需要追踪）
└── 无 → 这个对象的两个实例字段相同是否应当视为同一个？
        ├── 是 → Value Object
        └── 否 → 需要补 ID，做 Entity
```

例：
- 订单（Order）：有订单号 → Entity
- 地址（Address）：两个地址字段一样就是同一个地址 → Value Object
- 邮件地址（Email）：同上 → Value Object
- 客户（Customer）：有客户 ID → Entity

---

## §Aggregate（聚合）

### 识别需要聚合的场景

- 多个实体之间有强一致性约束（"订单总额必须等于订单项金额之和"）
- 修改一个实体必须同时修改另一个（"扣库存时必须减少订单的待发数量"）
- 跨实体的不变量散落在多个 Service 中维护

### 聚合根的职责

1. **唯一入口**：外部代码只能持有聚合根，子实体不直接对外暴露
2. **维护不变量**：聚合内的业务规则在聚合根中强制执行
3. **持久化边界**：Repository 只保存聚合根（连同其内部子实体）
4. **事务边界**：一个事务内只修改一个聚合（最佳实践）

### 示例：Order 聚合

```java
public class Order {  // 聚合根
    private final OrderId id;
    private final CustomerId customerId;
    private final List<OrderItem> items;  // 子实体（受 Order 控制）
    private OrderStatus status;

    // 不变量：总金额 = 所有 item 金额之和
    public Money totalAmount() {
        return items.stream()
            .map(OrderItem::subtotal)
            .reduce(Money.ZERO, Money::add);
    }

    // 添加 item 必须通过聚合根
    public void addItem(ProductId productId, int quantity, Money unitPrice) {
        if (status != OrderStatus.DRAFT) {
            throw new IllegalStateException();
        }
        items.add(new OrderItem(productId, quantity, unitPrice));
    }

    // 移除 item 也要通过聚合根
    public void removeItem(OrderItemId itemId) {
        if (status != OrderStatus.DRAFT) {
            throw new IllegalStateException();
        }
        items.removeIf(item -> item.id().equals(itemId));
    }

    // 不暴露 items 的修改入口
    public List<OrderItem> items() {
        return Collections.unmodifiableList(items);
    }
}

public class OrderItem {  // 聚合内部实体，不对外暴露
    private final OrderItemId id;
    private final ProductId productId;
    private int quantity;
    private final Money unitPrice;

    Money subtotal() {  // 包级可见，仅同包内的 Order 可调
        return unitPrice.multiply(BigDecimal.valueOf(quantity));
    }
}
```

### 聚合边界设计原则

1. **小聚合优于大聚合**：聚合越小，并发冲突越少、事务越短
2. **跨聚合引用用 ID**：不持有另一个聚合根对象的引用，只持有 `CustomerId` / `ProductId`
3. **跨聚合操作走应用服务**：不在聚合根内部调用其他 Repository
4. **跨聚合一致性用最终一致性**：通过领域事件解耦，不在一个事务内修改两个聚合

```java
// 反模式：Order 持有 Customer 引用
public class Order {
    private Customer customer; // 跨聚合直接引用
}

// 推荐：只持有 ID
public class Order {
    private final CustomerId customerId;
}
```

---

## §Repository（资源库）

### 与 DAO 的区别

| 维度 | DAO | Repository |
|------|-----|-----------|
| 关注点 | 数据访问 | 领域对象的获取/保存 |
| 粒度 | 表/行 | 聚合根 |
| 接口语言 | 数据库术语（select、where）| 领域术语（findByCustomer、ofStatus）|
| 返回值 | DTO / 数据行 | 领域对象（聚合根） |
| 实现位置 | 业务层 | 仓储位于领域层接口、基础设施层实现 |

### 重构：DAO → Repository

```java
// Before：DAO 风格
public interface OrderMapper {
    OrderDO selectById(Long id);
    int updateStatus(@Param("id") Long id, @Param("status") int status);
    List<OrderDO> selectByConditions(Map<String, Object> conditions);
}

// After：Repository 风格
public interface OrderRepository {
    Optional<Order> findById(OrderId id);
    void save(Order order);  // 不区分新增/更新
    List<Order> findByCustomer(CustomerId customerId);
    List<Order> findPendingOrdersOlderThan(Duration duration);
}

// 实现在 infrastructure 层
@Repository
public class JpaOrderRepository implements OrderRepository {
    private final OrderJpaRepository jpa;
    private final OrderMapper mapper;

    public Optional<Order> findById(OrderId id) {
        return jpa.findById(id.value()).map(mapper::toDomain);
    }
    // ...
}
```

### Repository 方法命名

- `findById(id)` - 按主键查找
- `findByXxx(...)` - 按业务条件查找，返回 List 或 Optional
- `existsByXxx(...)` - 存在性判断
- `save(aggregate)` - 保存（新增或更新由实现决定）
- `delete(aggregate)` - 删除
- `countByXxx(...)` - 计数

**禁止**：
- `update(aggregate)` / `insert(aggregate)`（暴露存储细节）
- `selectXxx()`（DAO 风格）
- 返回 DO / DTO（应返回领域对象）

---

## §Domain Service vs Application Service

### 区别

| 维度 | Domain Service | Application Service |
|------|---------------|--------------------|
| 关注 | 领域规则 | 用例编排 |
| 依赖 | 领域对象 | Repository + Domain Service + 基础设施 |
| 包含 | 业务逻辑 | 事务、安全、日志、事件发布 |
| 命名 | 业务概念（PricingService、ShippingCalculator）| 用例（PlaceOrderUseCase、OrderApplicationService）|

### 示例

```java
// Domain Service：纯领域逻辑
public class ShippingCalculator {
    public Money calculate(Address address, Weight weight, ShippingTier tier) {
        Money base = tier.baseFee();
        Money perKg = tier.perKgFee();
        Money distanceFee = distanceFeeFor(address);
        return base.add(perKg.multiply(weight.kg())).add(distanceFee);
    }
}

// Application Service：编排、事务、事件
@Service
@Transactional
public class OrderApplicationService {
    private final OrderRepository orderRepo;
    private final ShippingCalculator shippingCalc;
    private final EventPublisher eventPublisher;

    public OrderId placeOrder(PlaceOrderCommand cmd) {
        Order order = Order.create(cmd.customerId(), cmd.items());
        Money shipping = shippingCalc.calculate(cmd.address(), order.totalWeight(), cmd.tier());
        order.setShipping(shipping);

        orderRepo.save(order);
        eventPublisher.publish(new OrderPlacedEvent(order.id()));
        return order.id();
    }
}
```

---

## §Domain Event（领域事件）

### 何时使用

- 跨聚合的协作（如下单后扣库存）
- 跨限界上下文的通知
- 审计 / 日志 / 集成
- 实现最终一致性

### Spring 实现

```java
// 事件
public record OrderPlacedEvent(OrderId orderId, CustomerId customerId, Instant occurredAt) {}

// 发布
@Service
public class OrderApplicationService {
    private final ApplicationEventPublisher publisher;
    public void placeOrder(...) {
        // ...
        publisher.publishEvent(new OrderPlacedEvent(order.id(), order.customerId(), Instant.now()));
    }
}

// 监听
@Component
public class InventoryEventHandler {
    @EventListener
    @Async  // 注意事务边界
    public void on(OrderPlacedEvent event) {
        // 扣库存（独立事务）
    }
}
```

### 注意事项

- **事务边界**：默认 `@EventListener` 在同事务内执行，可能放大事务范围
- **`@TransactionalEventListener`**：可指定 AFTER_COMMIT 等阶段，但失败处理需要单独考虑
- **`@Async`**：异步执行，但需要可靠投递（落库 + 重试机制）才能保证最终一致性
- **不要把核心业务全部异步化**：用于真正解耦的场景，不滥用

---

## §贫血 → 充血 的重构路径

完整的重构路径，按风险从小到大排列：

### 阶段 1：识别值对象（低风险）

把基本类型偏执改为值对象：
- 金额 `BigDecimal` → `Money`
- 邮箱 `String` → `Email`
- 地址 4 字段 → `Address`

每改一个值对象是一个独立的小步，可独立 commit、可回滚。

### 阶段 2：把简单业务方法搬进实体（中风险）

```java
// 从 Service 搬到 Entity
class OrderService {
    boolean canBeCancelled(Order order) {
        return order.getStatus() == DRAFT || order.getStatus() == PAID;
    }
}
// 改为
class Order {
    public boolean canBeCancelled() {
        return status == DRAFT || status == PAID;
    }
}
```

每个方法独立搬移，跑测试。

### 阶段 3：状态机收敛到实体（中-高风险）

把状态变更的所有路径收敛到 Entity 的方法中，Service 不再直接 `setStatus`。

### 阶段 4：识别聚合边界（高风险）

判断哪些实体应当组成聚合，重新组织数据访问与事务边界。

### 阶段 5：识别 Domain Service 与 Application Service（高风险）

拆分原本臃肿的 `@Service` 类，按职责重新组织。

### 阶段 6：引入领域事件（高风险）

把紧耦合的跨聚合调用改为事件发布。

**建议**：除非有充分的领域复杂度需求，否则**不要一次性做完所有阶段**。阶段 1-2 在大多数项目都值得；阶段 3-6 要量入为出。

---

## §过度设计警告

DDD 战术模式不是免费的：

- **小项目慎用**：CRUD 系统强行 DDD 化是过度设计
- **不要为了 DDD 而 DDD**：值对象、聚合、Repository 是工具，不是目标
- **领域复杂度才是触发条件**：业务规则简单时，贫血模型 + Service 完全够用
- **团队成熟度**：DDD 需要团队对领域有共识，否则容易模型不稳定

### 判定是否值得 DDD

回答以下问题：

1. 业务规则是否复杂到需要"领域专家"参与设计？
2. 是否存在多个业务领域纠缠在一起（跨上下文）？
3. 业务规则是否经常变化？
4. 当前贫血模型是否已经导致维护痛苦（散弹式修改、规则散落）？

如果 ≥ 2 项为是 → 值得引入 DDD 战术模式。
如果 < 2 项 → 用基础重构手法（`refactoring-techniques.md`）即可。

---

## §与其他文档的衔接

- 识别贫血模型 → `smells-catalog.md` §4
- Move Method（搬业务方法）的 mechanics → `refactoring-techniques.md` §7.1
- Spring 注入与 @Service 拆分 → `spring-specific.md`
- 值对象（record）的实现 → `effective-java-notes.md` §Item 17
