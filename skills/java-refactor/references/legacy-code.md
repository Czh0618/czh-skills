# 遗留代码处理技术

本文档摘录 Michael Feathers《修改代码的艺术》（Working Effectively with Legacy Code）中的核心技术，应对"没有测试的代码"这一最常见的重构险境。

**Feathers 的定义**：遗留代码 = **没有测试的代码**，不管它多新。

**核心原则**：在没有测试保护的代码上做重构是赌博。在动刀之前，必须先为它"装上安全网"——这就是**特征化测试（Characterization Test）**。

---

## §核心概念：Seam（接缝）

**Seam（接缝）** 是 Feathers 提出的一个关键概念：

> Seam 是程序中可以**改变行为而不必修改该位置代码**的地方。

接缝让你能在测试中替换依赖、模拟外部系统、绕过难以构造的输入，而**不需要**重写被测代码本身。

### Java 中的常见 Seam 类型

| Seam 类型 | 启用方式 | 示例 |
|----------|---------|------|
| **对象 Seam** | 接口 + 依赖注入 | 把 `new EmailSender()` 改为接收 `EmailSender` 参数 |
| **链接 Seam** | 类路径 / Classpath | 把生产 classpath 上的某个类替换为测试版本 |
| **预处理 Seam** | （Java 无原生支持） | 不适用 |
| **构造 Seam** | 子类化重写 | 子类化生产类，重写 `protected` 方法 |

**Java 实战中最常用：对象 Seam**。本文档重点讲这个。

---

## §特征化测试（Characterization Test）

### 定义

特征化测试 = **记录代码当前的实际行为**（不是"应当"的行为），作为重构前后的对比基准。

**关键差异**：
- 单元测试：验证代码符合规约
- 特征化测试：**先发现**代码当前在做什么，再把它**固化**为测试

### 编写步骤

1. **写一个能跑通的最简调用**，看看代码会发生什么
2. **用一个明显错误的预期值**做断言（如 `assertEquals(-99999, result)`）
3. **跑测试**，让测试失败
4. **从失败信息中拿到实际值**（如"实际为 100"）
5. **把预期值改成实际值**（`assertEquals(100, result)`）
6. **测试绿了**——这就是当前行为的特征化测试

### 示例

```java
// 遗留代码
public class PricingCalculator {
    public double calculate(int quantity, double basePrice) {
        // 一段没人敢动的复杂逻辑
        double price = basePrice * quantity;
        if (quantity > 10) price *= 0.9;
        if (quantity > 100) price *= 0.85;
        return price;
    }
}

// 特征化测试编写过程
@Test
void characterize_calculate_quantity_5() {
    PricingCalculator calc = new PricingCalculator();
    double result = calc.calculate(5, 10.0);
    assertThat(result).isEqualTo(-9999.0); // 故意错的预期
}
// 跑测试 → 失败，实际值是 50.0
// 把 -9999.0 改成 50.0 → 测试绿
// 这就锁定了"5 件、单价 10，结果 50"的当前行为

@Test
void characterize_calculate_quantity_15() {
    double result = calc.calculate(15, 10.0);
    // 跑出来是 135.0（150 * 0.9）
    assertThat(result).isEqualTo(135.0);
}
```

### 特征化测试要覆盖的场景

至少覆盖：
- **典型输入**：业务最常用的参数组合
- **边界值**：0、null、空集合、最大值
- **分支覆盖**：每个 if / case 分支至少一个用例
- **异常路径**：会抛异常的输入

**覆盖率目标**：不要追求 100%（遗留代码的死代码可能很多）。目标是覆盖**即将要改动的路径**——动哪里就先测哪里。

---

## §依赖打破技术（Dependency-Breaking Techniques）

Feathers 列出了 24 种技术，本文档摘录 Java 场景下最常用的 8 种。

### 1. 提取接口（Extract Interface）⭐

**场景**：要测试的类依赖一个难以构造的具体类

**步骤**：
1. 为依赖类创建接口（IDE Refactor → Extract Interface）
2. 让原类 `implements` 这个接口
3. 调用方改为依赖接口
4. 测试时实现接口或用 Mockito mock

**示例**：
```java
// Before：OrderService 直接依赖 EmailSender 具体类，无法测试
public class OrderService {
    private EmailSender emailSender = new EmailSender(); // hard-wired
    public void placeOrder(Order order) {
        // ...
        emailSender.send(order.getCustomerEmail(), "Order placed");
    }
}

// After：抽接口、依赖注入
public interface EmailSender {
    void send(String to, String content);
}
public class SmtpEmailSender implements EmailSender { /* ... */ }
public class OrderService {
    private final EmailSender emailSender;
    public OrderService(EmailSender emailSender) {
        this.emailSender = emailSender;
    }
}
// 测试时
@Test
void should_send_email_when_order_placed() {
    EmailSender mock = mock(EmailSender.class);
    OrderService svc = new OrderService(mock);
    svc.placeOrder(order);
    verify(mock).send(anyString(), anyString());
}
```

---

### 2. 参数化构造函数（Parameterize Constructor）

**场景**：类在构造函数中 `new` 了依赖，无法注入

**步骤**：
1. 新增一个接收依赖的构造函数
2. 原构造函数调用新构造函数，传入默认实现
3. 测试用新构造函数，生产用原构造函数

**示例**：
```java
// Before
public class OrderService {
    private final EmailSender sender = new SmtpEmailSender();
}

// After
public class OrderService {
    private final EmailSender sender;
    public OrderService() {
        this(new SmtpEmailSender());
    }
    OrderService(EmailSender sender) { // 包级可见，仅测试
        this.sender = sender;
    }
}
```

**Spring 项目特定**：用 Spring 注入解决，不需要这个手法（构造函数注入是天然的接缝）。

---

### 3. 参数化方法（Parameterize Method）

**场景**：方法内部 `new` 了依赖

**步骤**：
1. 新增重载方法，接收依赖作为参数
2. 原方法调用新方法，传入默认实例

**示例**：
```java
// Before
public Order placeOrder(Cart cart) {
    Order order = new Order(); // 直接 new
    // ...
}

// After
public Order placeOrder(Cart cart) {
    return placeOrder(cart, new Order());
}
Order placeOrder(Cart cart, Order order) {
    // ...
}
```

---

### 4. 子类化并重写（Subclass and Override Method）⭐

**场景**：方法依赖一个无法替换的静态调用或难构造的协作者

**步骤**：
1. 把要替换的代码提取为 `protected` 方法
2. 在测试中创建子类，重写这个方法
3. 测试使用子类

**示例**：
```java
// Before
public class TimeService {
    public boolean isExpired(LocalDateTime time) {
        return time.isBefore(LocalDateTime.now()); // 静态调用，难测试
    }
}

// After
public class TimeService {
    public boolean isExpired(LocalDateTime time) {
        return time.isBefore(currentTime());
    }
    protected LocalDateTime currentTime() {
        return LocalDateTime.now();
    }
}
// 测试
class TestableTimeService extends TimeService {
    LocalDateTime fixedTime;
    @Override
    protected LocalDateTime currentTime() { return fixedTime; }
}
```

**注意**：现代 Java 应优先考虑注入 `Clock` 而不是子类化（Java 8+ 提供了 `Clock` 类专门解决这个问题）。

---

### 5. 静态方法封装（Encapsulate Static Method）

**场景**：方法调用了静态方法（如 `LocalDateTime.now()`、`UUID.randomUUID()`、第三方库的 static utility）

**步骤**：
1. 创建一个实例方法包裹静态调用
2. 把这个实例方法变成可注入的依赖

**示例**：
```java
// Before
String id = UUID.randomUUID().toString();

// After
public interface IdGenerator {
    String newId();
}
public class UuidIdGenerator implements IdGenerator {
    public String newId() { return UUID.randomUUID().toString(); }
}
// 测试时注入固定 ID 的 IdGenerator
```

---

### 6. 提取并重写实例委托（Extract and Override Factory Method）

**场景**：类在 `new` 一个对象时混合了创建与使用

**步骤**：
1. 把 `new X()` 提取为一个 `protected` 工厂方法
2. 测试时子类化并重写工厂方法

---

### 7. 接缝法（Link Seam）

**场景**：依赖是一个静态方法或硬编码的类，但你能控制 classpath

**步骤**：测试时在 classpath 前面放一个同包名同类名但行为不同的"替身"。

**实战**：通常不推荐——容易踩 JVM 类加载坑。优先用其他手法。

---

### 8. 实例委托保留旧接口（Adapt Parameter）

**场景**：方法签名复杂，难以测试，但又不能改签名

**步骤**：
1. 在方法内部把复杂参数转换为简单参数
2. 用简单参数调用真正的实现
3. 测试针对简单参数的实现

---

## §应对策略

### Sprout Method（萌芽方法）

**场景**：要在遗留方法中添加新功能，但不想动旧代码

**步骤**：
1. 把新功能写成一个独立的新方法（"萌芽"）
2. 在旧方法中调用新方法
3. 旧方法只多了一行调用，风险最小
4. 新方法独立编写测试

**示例**：
```java
// 遗留方法 placeOrder 太复杂不敢动，但要加"优惠券校验"
public void placeOrder(Order order) {
    // ... 200 行老代码 ...

    // 萌芽：新增的功能
    validateCoupon(order); // 新方法，独立可测

    // ... 继续老代码 ...
}

private void validateCoupon(Order order) {
    // 新代码，写得整洁，有测试
}
```

### Sprout Class（萌芽类）

**场景**：新功能比萌芽方法复杂，需要多个方法

**步骤**：把新功能写成一个独立的新类，遗留代码只持有它的引用。

### Wrap Method / Wrap Class（包装方法/包装类）

**场景**：要在遗留方法的**前后**做事（如加日志、加事务、加重试），但不想动方法本身

**步骤**：
1. 重命名原方法为 `xxxInternal`（私有）
2. 创建新方法用原名，包装 internal 方法

**示例**：
```java
// Before
public void chargePayment(Order order) {
    // 100 行遗留代码
}

// After
public void chargePayment(Order order) {
    log.info("charging order {}", order.getId());
    try {
        chargePaymentInternal(order);
        log.info("charged order {}", order.getId());
    } catch (Exception e) {
        log.error("charge failed", e);
        throw e;
    }
}
private void chargePaymentInternal(Order order) {
    // 100 行遗留代码原封不动
}
```

---

## §决策流程

面对一段遗留代码要修改时的决策流程：

```
1. 这段代码有测试吗？
   ├── 有 → 直接重构（用 refactoring-techniques.md 的手法）
   └── 没有 → 进入下一步

2. 我能在不改原代码的情况下加测试吗？
   ├── 能 → 加特征化测试 → 再重构
   └── 不能 → 进入下一步

3. 依赖能打破吗？（看本文档 §依赖打破技术）
   ├── 能 → 用最小侵入手法打破依赖 → 加测试 → 重构
   └── 不能 → 进入下一步

4. 我是要"修改"还是"扩展"？
   ├── 扩展 → 用 Sprout Method / Sprout Class，新代码有测试，旧代码不动
   └── 修改 → 用 Wrap Method 包装，把改动隔离在包装层
```

---

## §常见反模式

### 1. "我等下次再补测试"

不行。下次你也不会补。补测试与修改必须是同一次任务。

### 2. "代码这么乱，先重构再说"

不行。无测试时重构 = 赌博。重构前必须先有特征化测试。

### 3. "全量重写更快"

通常不是。Feathers 的研究表明：遗留代码中往往包含**隐式的业务规则**——这些规则在重写时容易丢失，导致重写后的代码"看起来对，跑起来错"。

### 4. "我只改一行，应该没事"

风险评估别看改动量，看影响范围。一行 `if (a == null)` 改成 `if (a == null || a.isEmpty())` 可能让所有依赖此方法的调用方行为变化。

---

## §与 Step 0 的衔接

Step 0 边界与安全网确认时，如果探明：

| 探明结果 | 处理 |
|---------|------|
| 有充分测试（覆盖率 > 70%）| 跳过本文档，直接走 `refactoring-techniques.md` |
| 测试不足（覆盖率 30-70%）| 在路线图前置一个"补关键路径测试"步骤 |
| 几乎无测试（< 30%）| 路线图前置"特征化测试 + 依赖打破"两个步骤 |
| 完全无测试 + 严重耦合 | 建议用 Sprout Method 加新功能，暂不重构旧代码 |

---

## §速查：手法 → Java 实现

| Feathers 手法 | Java 现代实现 |
|--------------|-------------|
| Extract Interface | IDE Refactor → Extract Interface |
| Parameterize Constructor | 加包级构造函数 + 默认参数 |
| Subclass and Override | 用 protected 方法 + 测试用子类 |
| Encapsulate Static | 包装为接口 + 注入实现 |
| Wrap Method | 重命名 + 包装方法 |
| Sprout Method | 新方法独立编写 + 测试 |
| Adapt Parameter | 内部转换 + 简化签名 |

更现代的替代方案：
- 时间相关 → 注入 `java.time.Clock`
- 随机相关 → 注入 `java.util.Random` 或 `SecureRandom`
- 当前用户 → 注入 `SecurityContext` / `Principal` 提供者
- 配置 → 注入 `@Value` / `@ConfigurationProperties`

这些都比 Feathers 时代（2004 年）的子类化更优雅，应优先考虑。
