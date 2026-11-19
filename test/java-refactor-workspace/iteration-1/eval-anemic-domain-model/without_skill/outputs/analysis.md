# Order 充血模型重构分析（Anemic to Rich Domain Model）

> 范围：仅对当前贴出的 `Order` / `OrderItem` / `OrderService` 三个类做诊断与改造建议。
> 约束：本回复仅输出建议，不直接改动用户代码。

## 一、坏味道诊断（Code Smell Diagnosis）

| # | 坏味道（Smell） | 位置 | 严重度 | 说明 |
|---|---|---|---|---|
| 1 | 贫血模型（Anemic Domain Model） | `Order` / `OrderItem` | 高 | 实体只有字段与 getter/setter，所有业务规则（支付状态流转、取消校验、金额计算）外泄到 `OrderService`，违反"信息专家"原则。 |
| 2 | 类型码反模式（Type Code） | `Order.status: Integer` | 高 | 用 `0/1/2/3` 表达 DRAFT/PAID/SHIPPED/CANCELLED，编译期无约束、易写错；状态机不可见。 |
| 3 | 数据泥团（Data Clump） | `amount` + `currency` | 中高 | 金额与币种永远成对出现却散落为两字段；跨币种比较、加减无保护。典型 Money 值对象诉求。 |
| 4 | Feature Envy（特性依恋） | `OrderService.pay/cancel/calculateTotal` | 高 | Service 反复 `order.getXxx()` 后判断/计算再 `setXxx()`，行为本属于 `Order`。 |
| 5 | 状态校验散布 | pay/cancel 的 `if status != ...` | 中 | 新增状态（如 REFUNDED）需多处修改。应内聚到 `Order` 或枚举内。 |
| 6 | 缺少不变量保护 | `OrderItem.quantity / unitPrice` | 中 | setter 全开放，可被设为负数、null；聚合一致性无法保证。 |
| 7 | 重复真相源 | `calculateTotal` 与 `Order.amount` 并存 | 中 | `amount` 字段与 items 求和可能不一致。 |

## 二、前置提醒：是否值得 DDD 化？（Complexity Warning）

引入充血模型 / 值对象 / 聚合根并非"越多越好"。开工前请评估：

1. **领域复杂度**：若只有"下单-支付-发货"线性流程、未来 1-2 年不会大改，**轻度充血**（pay/cancel 搬入实体 + status 改 enum）就够了，无需 Aggregate Root / Repository / Domain Event 全套。
2. **团队熟悉度**：盲目引入 DDD 会增加心智负担与 Code Review 成本。
3. **持久化框架**：MyBatis 对充血模型不如 JPA 友好（无脏检查），值对象需要 TypeHandler。
4. **建议先做需求反向工程**：真实业务里大概率还有超时未支付自动取消、部分发货、退款、跨币种等。**强烈建议先用 `/req-reverse-eng` 把状态机和不变量梳理清楚**，否则容易把贫血搬成另一种贫血。

## 三、重构路线图（Roadmap）

| Step | 动作 | 手法 | 工作量 | 前置 |
|---|---|---|---|---|
| 0 | 澄清范围与领域规则 | `/req-reverse-eng` 输出状态机+不变量 | 0.5d | — |
| 1 | 补特征化测试 | Characterization Test（pay/cancel/calculateTotal） | 0.5d | Step 0 |
| 2 | `status: Integer` 改 `OrderStatus` enum | Replace Type Code with Enum | 0.5d | Step 1 |
| 3 | 引入 `Money` 值对象（amount + currency） | Extract Value Object | 0.5d | Step 1 |
| 4 | Move Method：`calculateTotal` 进 `Order` | Move Method | 0.5h | Step 3 |
| 5 | Move Method：`pay`/`cancel` 进 `Order`（保留 Service 编排） | Move Method + Encapsulate Field | 1d | Step 2,4 |
| 6 | （可选）`Order` 升为 Aggregate Root | Aggregate Pattern | 1d | Step 5 |
| 7 | （可选）发布 `OrderPaid` / `OrderCancelled` 领域事件 | Domain Event | 0.5d | Step 5 |

> 关键原则：**Service 不消失，只变薄**。Service 仍负责事务边界、Repository 调用、跨聚合协作；领域规则下沉到实体。

## 四、关键步骤详解

### Step 2 — Replace Type Code with Enum

**Before：**
```java
public class Order { private Integer status; /* 0..3 */ }
if (order.getStatus() != 0) throw new IllegalStateException("only DRAFT can pay");
```

**After：**
```java
public enum OrderStatus {
    DRAFT, PAID, SHIPPED, CANCELLED;
    public boolean canPay()    { return this == DRAFT; }
    public boolean canCancel() { return this != SHIPPED && this != CANCELLED; }
}
public class Order { private OrderStatus status; }
```

机械化步骤：(1) 按 0..3 顺序定义 enum 常量；(2) MyBatis 配 `EnumOrdinalTypeHandler`；(3) 字段类型替换；(4) Service 判断改为 `!status.canPay()`；(5) 跑特征化测试。
回滚：Git revert；DB 不变。

### Step 3 — 引入 Money 值对象

```java
public record Money(BigDecimal amount, String currency) {
    public Money {
        Objects.requireNonNull(amount);
        Objects.requireNonNull(currency);
        if (amount.signum() < 0) throw new IllegalArgumentException("negative");
    }
    public Money add(Money other) {
        if (!currency.equals(other.currency)) throw new IllegalStateException("currency mismatch");
        return new Money(amount.add(other.amount), currency);
    }
    public boolean lessThan(Money other) {
        if (!currency.equals(other.currency)) throw new IllegalStateException("currency mismatch");
        return amount.compareTo(other.amount) < 0;
    }
    public static Money zero(String currency) { return new Money(BigDecimal.ZERO, currency); }
}
```

机械化步骤：(1) Java 17 record 创建 Money；(2) 写 `MoneyTypeHandler`；(3) `Order.total` 取代 `amount+currency`，`OrderItem.unitPrice` 同步；(4) 调用方迁移；(5) 跨币种比较现在显式抛错——暴露隐藏 bug。
回滚：保留旧字段一个版本，并行灰度。

### Step 5 — Move Method：pay / cancel 进 Order

**After：**
```java
public class Order {
    private OrderStatus status;
    private Money total;

    public void pay(Money payAmount) {
        if (!status.canPay()) throw new IllegalStateException("cannot pay in status " + status);
        if (payAmount.lessThan(this.total)) throw new IllegalStateException("insufficient");
        this.status = OrderStatus.PAID;
    }
    public void cancel() {
        if (!status.canCancel()) throw new IllegalStateException("cannot cancel in status " + status);
        this.status = OrderStatus.CANCELLED;
    }
}

@Service
public class OrderService {
    @Transactional
    public void pay(String orderId, Money payAmount) {
        Order order = orderMapper.selectById(orderId);
        order.pay(payAmount);
        orderMapper.update(order);
    }
    @Transactional
    public void cancel(String orderId) {
        Order order = orderMapper.selectById(orderId);
        order.cancel();
        orderMapper.update(order);
    }
}
```

机械化步骤：(1) Order 新增 pay/cancel 复制领域校验；(2) Service 改为委托；(3) 跑测试；(4) 删 Service 旧分支；(5) 领域规则用例迁到 POJO 级 `OrderTest`，更快更稳。
回滚：三文件 revert 即可，DB 与接口契约不变。

## 五、需要你确认的问题

1. 持久化框架确认 MyBatis？接受自定义 TypeHandler？
2. `OrderServiceTest` 覆盖率？pay/cancel 是否有测试？
3. `OrderService.pay(String, BigDecimal)` 外部签名能否改？
4. 是否真有多币种？单币种可延后 Money。
5. DB `status` tinyint(0..3)？枚举序数需锁死？
6. pay/cancel 后是否要触发后续动作（邮件、扣库存、MQ）？决定是否上 Step 7。

## 六、DDD 战术模式参考（References）

- **Value Object（值对象）**：Money、Address。无身份、不可变、按值相等。
- **Entity（实体）**：Order、OrderItem。有 id、生命周期、可变。
- **Aggregate Root（聚合根）**：Order 是 OrderItem 的根，外部经根访问，保不变量。
- **Domain Service**：跨聚合领域逻辑。
- **Application Service**：重构后的 OrderService，负责事务/编排，不含领域规则。
- **Move Method / Replace Type Code with Enum**：Fowler《重构》。
- **Characterization Test**：Feathers《修改代码的艺术》。

## 七、下一步建议

1. 跑 `/req-reverse-eng` 把状态机和不变量写清楚；
2. 先合 Step 1 + Step 2（补测试 + enum），收益高、风险低、不破坏 API；
3. Step 3 起单独评审。
