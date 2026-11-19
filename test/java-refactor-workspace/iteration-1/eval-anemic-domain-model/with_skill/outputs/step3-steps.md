# Step 3：原子化执行步骤（≥ 2 步详细）

> 本文件展开路线图中的**步骤 2、步骤 3、步骤 5**（核心 Move Method）。步骤 1（特征化测试）与步骤 4、6 待用户确认 Step 0 中的测试覆盖情况后补全。

---

## 重构步骤 #2：Replace Type Code with Enum（`Integer status` → `OrderStatus`）

**手法**：Replace Type Code with Enum（`references/refactoring-techniques.md` §8）
**坏味道来源**：诊断 #2（类型码）
**对应路线图**：步骤 2
**DDD 阶段**：阶段 3 前置（状态机收敛准备）

### 影响范围

- **修改文件**：
  - `Order.java`：字段类型 `Integer status` → `OrderStatus status`
  - `OrderService.java`：`order.getStatus() != 0` / `== 2` / `== 3` → enum 比较
  - **MyBatis 映射**：在 `mybatis-config.xml` 或 `@MappedTypes` 处注册 `EnumOrdinalTypeHandler<OrderStatus>`（如果 DB 列继续存 0/1/2/3）
- **新增文件**：`OrderStatus.java`
- **API 变更**：`Order.getStatus()` 返回类型由 `Integer` → `OrderStatus`（如果 Order 是对外暴露的 DTO，需要 Step 0 重新确认；推定 Order 是领域内部模型，可改）
- **数据库变更**：**无**（DB 列仍存 0/1/2/3 整数，由 TypeHandler 转换）

### 前置条件

- [ ] 步骤 1 特征化测试已通过：`OrderServiceTest.pay_should_succeed_when_draft`、`pay_should_throw_when_not_draft`、`cancel_should_throw_when_shipped`、`cancel_should_throw_when_already_cancelled` 至少这 4 个用例存在
- [x] Step 0 确认 `Order` 为内部领域模型，可改字段类型（**待用户回应**）

### Before

```java
// Order.java
public class Order {
    private Integer status; // 0=DRAFT, 1=PAID, 2=SHIPPED, 3=CANCELLED
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }
}

// OrderService.java
if (order.getStatus() != 0) throw new IllegalStateException("only DRAFT can pay");
if (order.getStatus() == 2) throw new IllegalStateException("already shipped");
if (order.getStatus() == 3) throw new IllegalStateException("already cancelled");
order.setStatus(1);
order.setStatus(3);
```

### After

```java
// OrderStatus.java（新增）
public enum OrderStatus {
    DRAFT(0), PAID(1), SHIPPED(2), CANCELLED(3);

    private final int code;
    OrderStatus(int code) { this.code = code; }
    public int code() { return code; }

    public static OrderStatus fromCode(int code) {
        for (OrderStatus s : values()) if (s.code == code) return s;
        throw new IllegalArgumentException("Unknown OrderStatus code: " + code);
    }
}

// Order.java
public class Order {
    private OrderStatus status;
    public OrderStatus getStatus() { return status; }
    public void setStatus(OrderStatus status) { this.status = status; } // 步骤 5 会再删除
}

// OrderService.java
if (order.getStatus() != OrderStatus.DRAFT) throw new IllegalStateException("only DRAFT can pay");
if (order.getStatus() == OrderStatus.SHIPPED)   throw new IllegalStateException("already shipped");
if (order.getStatus() == OrderStatus.CANCELLED) throw new IllegalStateException("already cancelled");
order.setStatus(OrderStatus.PAID);
order.setStatus(OrderStatus.CANCELLED);
```

### 机械化步骤（Fowler mechanics）

1. 新建 `OrderStatus` 枚举，包含 `code()` 与 `fromCode(int)`；先**不动** `Order` 字段
2. 编译——确认枚举本身正确
3. 给 MyBatis 配置 `EnumOrdinalTypeHandler<OrderStatus>`（如果是 XML，加入 `<typeHandler>`；如果是注解，给字段映射加 `@Result(typeHandler=...)`）
4. 修改 `Order.status` 类型为 `OrderStatus`，getter/setter 同步改
5. 编译——所有比较点都会报错，逐个改：
   - `getStatus() != 0` → `getStatus() != OrderStatus.DRAFT`
   - `getStatus() == 2` → `getStatus() == OrderStatus.SHIPPED`
   - `getStatus() == 3` → `getStatus() == OrderStatus.CANCELLED`
   - `setStatus(1)` → `setStatus(OrderStatus.PAID)`
   - `setStatus(3)` → `setStatus(OrderStatus.CANCELLED)`
6. 编译通过
7. 跑特征化测试

### 验证

```bash
mvn -pl <模块名> test -Dtest=OrderServiceTest
```

期望：步骤 1 中所有 pay/cancel 用例全绿；特别验证 DB 写入/读取后 status 仍为正确枚举（建议加一个集成测试 `pay_then_reload_should_be_PAID`）。

### 回滚策略

- **单 commit**："refactor(order): replace status int with OrderStatus enum"
- **回滚命令**：`git revert <hash>`
- **副作用**：DB 数据不变；TypeHandler 双向转换需在回滚时一并撤销

### 后续衔接

- 完成后启用步骤 #3（Money 值对象）
- **暂不**修改 `Order.setStatus` 可见性——留到步骤 5 收敛状态机时一起改

---

## 重构步骤 #3：Introduce Value Object `Money`

**手法**：Introduce Value Object（`references/ddd-tactical.md` §Value Object）
**坏味道来源**：诊断 #3（数据泥团 + 基本类型偏执）
**对应路线图**：步骤 3
**DDD 阶段**：阶段 1（识别值对象，低风险红利）

### 影响范围

- **修改文件**：
  - `Order.java`：`BigDecimal amount + String currency` → `Money amount`（或保留旧字段做过渡）
  - `OrderItem.java`：`BigDecimal unitPrice` → `Money unitPrice`（如有 currency 字段一并合并；若没有，先保留旧形态待步骤 4 一起改）
  - `OrderService.calculateTotal`：`BigDecimal` 累加 → `Money.add` 累加（步骤 4 会整体搬走，此处只做类型替换）
- **新增文件**：`Money.java`
- **API 变更**：`Order.getAmount()` 返回类型 `BigDecimal` → `Money`（如对外暴露需评估）
- **数据库变更**：**无**（amount/currency 列结构不变；MyBatis 端用 `TypeHandler` 把 `amount,currency` 两列合并为 `Money` 对象，或用 `@Results` 拆字段填充）

### 前置条件

- [ ] 步骤 2 已完成（顺序无强依赖，但合并改造便于一个 PR）
- [ ] 步骤 1 特征化测试已通过
- [x] 已澄清"业务上是否真存在多币种"（如果业务恒为 CNY，可考虑去掉 currency 字段，但本步骤保守保留——见决策点）

### 决策点：要不要保留 currency 字段？

| 选项 | 适用 | 备注 |
|------|-----|------|
| A. 保留 currency，建立完整 Money | 业务真有多币种 / 未来可能扩展 | 推荐默认 |
| B. 移除 currency，Money 只含 amount | 业务恒为 CNY，且无外部货币交互 | 节省 schema，但失去类型保护 |

**推荐 A**：currency 字段已存在，移除属于扩大范围；保留并加强校验（构造时校验 currency 非空，运算时校验同币种）。

### Before

```java
// Order.java
public class Order {
    private BigDecimal amount;
    private String currency;
    private List<OrderItem> items;
    // getter/setter ...
}

// OrderItem.java
public class OrderItem {
    private BigDecimal unitPrice;
    private Integer quantity;
    // ...
}

// OrderService.calculateTotal
BigDecimal total = BigDecimal.ZERO;
for (OrderItem item : order.getItems()) {
    total = total.add(item.getUnitPrice().multiply(BigDecimal.valueOf(item.getQuantity())));
}
```

### After

```java
// Money.java（新增，Java 17 record）
public record Money(BigDecimal amount, String currency) {
    public Money {
        Objects.requireNonNull(amount, "amount");
        Objects.requireNonNull(currency, "currency");
        if (amount.signum() < 0) {
            throw new IllegalArgumentException("Money cannot be negative");
        }
    }
    public static Money zero(String currency) {
        return new Money(BigDecimal.ZERO, currency);
    }
    public Money add(Money other) {
        ensureSameCurrency(other);
        return new Money(amount.add(other.amount), currency);
    }
    public Money multiply(int factor) {
        return new Money(amount.multiply(BigDecimal.valueOf(factor)), currency);
    }
    public boolean lessThan(Money other) {
        ensureSameCurrency(other);
        return this.amount.compareTo(other.amount) < 0;
    }
    private void ensureSameCurrency(Money other) {
        if (!currency.equals(other.currency)) {
            throw new IllegalArgumentException(
                "Currency mismatch: " + currency + " vs " + other.currency);
        }
    }
}

// Order.java
public class Order {
    private Money amount;          // 取代 BigDecimal + String
    private List<OrderItem> items;
    public Money getAmount() { return amount; }
    public void setAmount(Money amount) { this.amount = amount; } // 步骤 5 会收敛
}

// OrderItem.java（如果原来没有独立 currency，可暂保留 BigDecimal，由 Order 持币种）
public class OrderItem {
    private BigDecimal unitPrice;   // 暂不动；步骤 4 会把 subtotal 行为搬进来时再决定
    private Integer quantity;
}
```

### 机械化步骤

1. 新建 `Money` record + 单元测试（`MoneyTest`：构造校验、add 同币种、add 异币种抛异常、multiply、zero、lessThan）
2. 编译，跑 `MoneyTest` 全绿
3. 写 `MoneyTypeHandler extends BaseTypeHandler<Money>`：从 `amount/currency` 两列读出、写入两列。或者用 `@Results` 在 XML 端拆字段映射
4. 修改 `Order` 字段：删除 `BigDecimal amount` + `String currency`，新增 `Money amount`；getter/setter 同步改
5. 编译——`OrderService.pay` 中 `payAmount.compareTo(order.getAmount())` 会报错；改为：
   ```java
   Money orderAmount = order.getAmount();
   if (payAmount.compareTo(orderAmount.amount()) < 0) ...
   ```
   （步骤 5 会进一步把 `payAmount` 也升级为 `Money` 类型）
6. 修改 `OrderService.calculateTotal`：累加初始值 `BigDecimal.ZERO` → `Money.zero(order.getAmount().currency())`（或暂保留 BigDecimal，步骤 4 整体搬迁时再统一）
7. 编译通过
8. 跑全部测试

### 验证

```bash
mvn -pl <模块名> test
```

期望：
- `MoneyTest` 全绿（10+ 用例）
- `OrderServiceTest` 全绿
- 集成测试：DB 写入后 `amount` 列与 `currency` 列保持原 schema 与数值

### 回滚策略

- **单 commit**："refactor(order): introduce Money value object"
- **回滚命令**：`git revert <hash>`
- **副作用**：DB 不变；TypeHandler 注册需同步回滚

### 后续衔接

- 完成后启用步骤 #4（Move `calculateTotal` 到 `Order.totalAmount()`）
- 步骤 5 中 `pay(Money)` 才能保持类型一致

---

## 重构步骤 #5（骨架）：Move Method `pay/cancel/calculateTotal` 搬入 `Order` 实体

**手法**：Move Method + Encapsulate Field（`references/ddd-tactical.md` §Entity §贫血→充血 阶段 2-3）
**坏味道来源**：诊断 #1、#4、#5、#6（贫血模型 / 状态机散落 / 多余 DB 查询 / setter 全开）
**对应路线图**：步骤 4 + 步骤 5 + 步骤 6 的合并视图
**DDD 阶段**：阶段 2 + 阶段 3（核心改造）

### 强烈建议：执行本步骤前先 `/req-reverse-eng`

诊断 #7 的领域规则未澄清。如果在此处未先固化状态机不变量，搬入 Order 的方法会**冻结一个错误的规则**。请先调用：

```
/req-reverse-eng

输入：Order 状态机（DRAFT/PAID/SHIPPED/CANCELLED）
需要回答：
1. 允许的状态转换路径（穷举）
2. pay 业务规则：等额 / 多付 / 部分支付？同币种校验？
3. cancel 业务规则：哪些状态可 cancel？已 PAID 是否触发退款？
4. SHIPPED 由谁触发？是否本 Service 范围？
```

### 影响范围（待 #7 澄清后才能精确化）

- **修改文件**：`Order.java`（新增 `pay/cancel/totalAmount` 行为，删除 setStatus/setAmount 的对外可见性）、`OrderService.java`（变薄）
- **API 变更**：`OrderService.pay/cancel/calculateTotal` 签名**保持不变**；`Order.setStatus/setAmount` 包级可见（或删除）
- **数据库变更**：无

### Before（Service 中的核心规则）

```java
// OrderService.java
public void pay(String orderId, BigDecimal payAmount) {
    Order order = orderMapper.selectById(orderId);
    if (order.getStatus() != OrderStatus.DRAFT) throw new IllegalStateException("only DRAFT can pay");
    if (payAmount.compareTo(order.getAmount().amount()) < 0) throw new IllegalStateException("insufficient");
    order.setStatus(OrderStatus.PAID);
    orderMapper.update(order);
}
public void cancel(String orderId) {
    Order order = orderMapper.selectById(orderId);
    if (order.getStatus() == OrderStatus.SHIPPED)   throw new IllegalStateException("already shipped");
    if (order.getStatus() == OrderStatus.CANCELLED) throw new IllegalStateException("already cancelled");
    order.setStatus(OrderStatus.CANCELLED);
    orderMapper.update(order);
}
public BigDecimal calculateTotal(String orderId) {
    Order order = orderMapper.selectById(orderId);
    BigDecimal total = BigDecimal.ZERO;
    for (OrderItem item : order.getItems()) {
        total = total.add(item.getUnitPrice().multiply(BigDecimal.valueOf(item.getQuantity())));
    }
    return total;
}
```

### After（充血模型）

```java
// Order.java
public class Order {
    private final String id;
    private final String customerId;
    private Money amount;
    private OrderStatus status;
    private final List<OrderItem> items;

    // 业务行为 ↓↓↓

    public void pay(Money payAmount) {
        if (status != OrderStatus.DRAFT) {
            throw new IllegalStateException("only DRAFT can pay, current=" + status);
        }
        if (payAmount.lessThan(amount)) {
            throw new InsufficientPaymentException(id, amount, payAmount);
        }
        // 注：是否允许多付、是否记录支付流水，待 /req-reverse-eng 澄清
        this.status = OrderStatus.PAID;
    }

    public void cancel() {
        if (status == OrderStatus.SHIPPED) {
            throw new IllegalStateException("already shipped, cannot cancel");
        }
        if (status == OrderStatus.CANCELLED) {
            throw new IllegalStateException("already cancelled");
        }
        // 注：PAID 可 cancel 是否触发退款？待澄清
        this.status = OrderStatus.CANCELLED;
    }

    public Money totalAmount() {
        Money zero = Money.zero(amount.currency());
        return items.stream()
            .map(OrderItem::subtotal)        // OrderItem 也需要 subtotal() 方法
            .reduce(zero, Money::add);
    }

    // 不暴露 setStatus / setAmount 给业务调用方
    void setStatus(OrderStatus status) { this.status = status; }   // 包级，仅供持久化层
}

// OrderItem.java
public class OrderItem {
    private final String productId;
    private final int quantity;
    private final Money unitPrice;

    Money subtotal() {                 // 包级
        return unitPrice.multiply(quantity);
    }
}

// OrderService.java（变薄为 Application Service）
@Service
public class OrderService {
    @Autowired private OrderMapper orderMapper;

    public void pay(String orderId, BigDecimal payAmountRaw) {
        Order order = orderMapper.selectById(orderId);
        // 注：保留原签名以兼容；内部转 Money。多币种澄清后可改对外签名
        Money payAmount = new Money(payAmountRaw, order.getAmount().currency());
        order.pay(payAmount);
        orderMapper.update(order);
    }

    public void cancel(String orderId) {
        Order order = orderMapper.selectById(orderId);
        order.cancel();
        orderMapper.update(order);
    }

    public BigDecimal calculateTotal(String orderId) {
        Order order = orderMapper.selectById(orderId);
        return order.totalAmount().amount();   // 对外签名保持 BigDecimal
    }
}
```

### 机械化步骤（高层骨架，待 #7 澄清后细化）

1. **先做 `totalAmount`**（最纯粹的领域计算，无副作用）：
   1. `Order` 新增 `public Money totalAmount()`，先用现有逻辑拷贝过来
   2. `OrderItem` 新增包级 `subtotal()`
   3. `OrderService.calculateTotal` 内部改为调用 `order.totalAmount().amount()`
   4. 编译 → 跑测试 → commit "refactor(order): move calculateTotal to Order.totalAmount()"
2. **再做 `cancel`**（无外部参数，最简单的状态变更）：
   1. `Order` 新增 `public void cancel()`，把守卫规则与状态变更搬入
   2. `OrderService.cancel` 改为 `order.cancel(); orderMapper.update(order);`
   3. 编译 → 跑测试 → commit "refactor(order): move cancel logic to Order.cancel()"
3. **最后做 `pay`**（涉及 Money 类型转换）：
   1. `Order` 新增 `public void pay(Money payAmount)`，搬入守卫与状态变更
   2. `OrderService.pay` 内部把 `BigDecimal payAmountRaw` 包装为 `Money`，再调 `order.pay(money)`
   3. 编译 → 跑测试 → commit "refactor(order): move pay logic to Order.pay()"
4. **收敛 setter**：
   1. 把 `Order.setStatus`、`Order.setAmount` 改为包级（确保 MyBatis 仍能反射注入；MyBatis 默认能访问包级）
   2. 编译 → 跑测试 → commit "refactor(order): seal Order setters from business callers"

每一小步都是独立 commit，独立 revert。

### 验证

```bash
mvn -pl <模块名> test
```

期望全部已有测试 + 新增的 `Order.pay/cancel/totalAmount` 单元测试全绿。

**新增建议测试**（无需 Service 与 DB）：
- `OrderTest.pay_should_succeed_when_draft_and_sufficient`
- `OrderTest.pay_should_throw_when_not_draft`
- `OrderTest.pay_should_throw_when_insufficient`
- `OrderTest.cancel_should_succeed_when_draft_or_paid`（视澄清结果）
- `OrderTest.cancel_should_throw_when_shipped_or_cancelled`
- `OrderTest.totalAmount_should_sum_all_item_subtotals`

### 回滚策略

- 每个子步骤独立 commit；任意一步失败可单独 `git revert <hash>`
- 整组步骤建议放一个 PR，便于 review；但 commit 粒度保持细，便于二分回退

### 后续衔接

- 完成后，路线图阶段 1-3 全部完成
- 阶段 4-6 **不在本路线图**；若用户后续提出新需求（如领域事件、聚合根、Repository 重命名），再单独排期

---

## 步骤 1 / 4 / 6 占位

- **步骤 1（特征化测试）**：待用户回应测试现状后展开
- **步骤 4（独立的 calculateTotal Move Method）**：已被步骤 5 的第 1 个子步骤覆盖
- **步骤 6（收尾去 setter）**：已被步骤 5 的第 4 个子步骤覆盖

---

## 总体回滚 / 进度建议

| 阶段 | 提交粒度 | PR 建议 |
|-----|---------|--------|
| 步骤 1 | 1 commit | 单独 PR（"chore(test): characterization tests for Order"）|
| 步骤 2 + 3 | 各 1 commit | 可同 PR（"refactor(order): introduce OrderStatus enum + Money VO"）|
| 步骤 5（4 个子步骤）| 4 commits | 单独 PR（"refactor(order): move business behaviors into Order entity"）|

---

## 等待用户决策

完成上述步骤前请回应：

1. ✅ Step 0 中 4 项推定假设是否确认？
2. ✅ 是否同意"DDD 战术阶段 1-3"边界？
3. ✅ 是否同意在执行步骤 5 之前先走 `/req-reverse-eng` 澄清诊断 #7？
4. ✅ 测试覆盖现状？（决定步骤 1 是否需要）
5. ✅ PR 拆分方案是否接受（3 个 PR）？
