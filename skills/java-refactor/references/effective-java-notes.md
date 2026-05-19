# Effective Java 重构要点

本文档摘录 Joshua Bloch《Effective Java》中**与重构高度相关**的 Item，作为 Java 语言特性层面的最佳实践。

**定位**：本文档不是 Effective Java 全书摘要，只挑选**重构时容易踩坑或需要主动改造**的 Item。每条只列：识别 → 修复方向 → 关键示例。

通用手法见 `refactoring-techniques.md`；本文档处理 Java 语言层面的细节。

---

## §对象的创建与销毁

### Item 1：考虑用静态工厂方法代替构造函数

**识别**：构造函数重载过多、构造意图不清晰

**修复**：用命名的静态工厂方法替代

```java
// Before：5 个构造函数重载，看不出哪个干什么
public Order(String id);
public Order(String id, BigDecimal amount);
public Order(String id, BigDecimal amount, Customer c);
// ...

// After：命名静态工厂
public static Order createDraft(String id);
public static Order createWithAmount(String id, BigDecimal amount);
public static Order restoreFrom(OrderSnapshot snapshot);
```

**约定命名**：
- `from(X)` - 类型转换
- `of(...)` - 聚合多个参数
- `valueOf(...)` - 等价转换
- `getInstance()` - 单例或缓存
- `newInstance()` - 每次新对象
- `create(...)` - 创建
- `builder()` - 返回 Builder

---

### Item 2：构造函数参数多时考虑 Builder

**识别**：构造函数 ≥ 4 个参数 / 大量 setter / 可选参数多

**修复**：用 Builder

```java
// Before
new Pizza("Medium", true, true, false, false, true, "Thin");

// After
Pizza pizza = Pizza.builder()
    .size("Medium")
    .cheese(true)
    .pepperoni(true)
    .crust("Thin")
    .build();
```

**重要**：可以用 Lombok `@Builder` 一行解决，或用记录类 + Builder 模式手写。

---

### Item 3：用私有构造器或枚举类型强化 Singleton

**识别**：手写双重检查锁定的单例

**修复**：用 `enum` 单例

```java
// Before
public class ConnectionPool {
    private static ConnectionPool instance;
    public static ConnectionPool getInstance() {
        if (instance == null) {
            synchronized (ConnectionPool.class) {
                if (instance == null) instance = new ConnectionPool();
            }
        }
        return instance;
    }
}

// After（防序列化攻击、线程安全、简洁）
public enum ConnectionPool {
    INSTANCE;
    public void doSomething() { /* ... */ }
}
```

**Spring 项目特定**：用 `@Component` + Spring 容器管理单例（默认 scope=singleton），不需要手写。

---

### Item 5：依赖注入优于硬连接

**识别**：类内 `new` 依赖、静态依赖

**修复**：通过构造函数注入

```java
// Before
public class SpellChecker {
    private final Lexicon dictionary = new EnglishDictionary(); // 硬编码
}

// After
public class SpellChecker {
    private final Lexicon dictionary;
    public SpellChecker(Lexicon dictionary) {
        this.dictionary = Objects.requireNonNull(dictionary);
    }
}
```

详见 `legacy-code.md` §依赖打破。

---

### Item 6：避免创建不必要的对象

**识别**：循环内创建对象、boxing 频繁、String 重复拼接

**修复**：缓存、用基本类型、用 StringBuilder

```java
// Before
for (int i = 0; i < items.size(); i++) {
    String result = "" + i; // String.valueOf 更明确
    Long total = 0L;        // 自动装箱！
    total += i;             // 每次都创建新 Long 对象
}

// After
for (int i = 0; i < items.size(); i++) {
    String result = String.valueOf(i);
    long total = 0L;        // 基本类型
    total += i;
}
```

**Java 8+ 特定**：`Pattern.compile()` 应当缓存（编译耗时），不要每次匹配都编译。

---

## §对所有对象都通用的方法

### Item 10：重写 equals 时遵守通用约定

**识别**：自己写的 `equals`，特别是涉及继承

**修复要点**：
- 自反性、对称性、传递性、一致性、null 处理
- **使用 IDE 生成**：IntelliJ → Generate → equals() and hashCode()，不要手写

```java
// 推荐：用 record（Java 14+）自动生成正确的 equals
public record OrderId(String value) {}
// equals / hashCode / toString 都正确，不需要手写

// 或用 Lombok @EqualsAndHashCode
@Data
public class Customer { ... }
```

---

### Item 11：重写 equals 时必须重写 hashCode

**识别**：重写了 `equals` 但没重写 `hashCode` → 放入 HashMap / HashSet 会出错

**修复**：用 `Objects.hash()`

```java
@Override
public int hashCode() {
    return Objects.hash(id, name, email);
}
```

---

### Item 12：始终重写 toString

**识别**：日志/调试时打印对象只看到 `Customer@1a2b3c4d`

**修复**：用 IDE 生成或 Lombok `@ToString`

**注意**：`toString` 中不要泄露敏感信息（密码、token）→ Lombok `@ToString(exclude = "password")`。

---

## §类与接口

### Item 15：使类与成员的可访问性最小化

**识别**：默认 public / 字段直接 public / 工具方法 public 但只在内部用

**修复**：从最严收紧

```java
// 收紧顺序：public → protected → package-private → private
public class OrderService {
    private final OrderRepo repo;  // 私有
    public Order placeOrder(...) { ... }   // 公开
    private void validate(...) { ... }     // 私有
    Order draft(...) { ... }               // 包级（仅测试用 + 内部）
}
```

**字段**：永远不要 public 字段（除非 static final 常量）。用 getter/setter 或 record。

---

### Item 16：使用复合优于继承

**识别**：用继承获取代码复用，但子类与父类无 is-a 关系

**修复**：改为组合

```java
// Before：HashSet 继承获得 size() 等
public class CountingSet<E> extends HashSet<E> { ... }
// 问题：依赖 HashSet 的内部实现，HashSet 升级可能破坏

// After：组合
public class CountingSet<E> {
    private final Set<E> delegate = new HashSet<>();
    public boolean add(E e) {
        addCount++;
        return delegate.add(e);
    }
    // 委托其他方法
}
```

**关联手法**：`refactoring-techniques.md` §10.4 Replace Inheritance with Delegation。

---

### Item 17：使可变性最小化

**识别**：值对象有 setter / 字段非 final

**修复**：让类不可变（推荐用 record）

```java
// Before
public class Money {
    private BigDecimal amount;
    private Currency currency;
    public void setAmount(BigDecimal a) { this.amount = a; }
}

// After（Java 14+ record）
public record Money(BigDecimal amount, Currency currency) {
    public Money {
        Objects.requireNonNull(amount);
        Objects.requireNonNull(currency);
        if (amount.signum() < 0) throw new IllegalArgumentException();
    }
    public Money add(Money other) {
        if (!currency.equals(other.currency)) throw new IllegalArgumentException();
        return new Money(amount.add(other.amount), currency);
    }
}
```

**好处**：天然线程安全、易理解、易测试。

---

### Item 18：复合优于继承（重申）/ Item 19：要么为继承设计且文档化，要么禁止继承

**识别**：非 final 类、protected 字段、protected 钩子方法

**修复**：
- 不打算被继承的类标 `final`
- 打算被继承的类显式文档化钩子方法
- 不要在构造函数里调用可重写方法

---

### Item 22：接口只用于定义类型

**识别**：用 `interface` 装常量（"常量接口"反模式）

**修复**：用 `class` + `static final`，或 `enum`

```java
// Before（反模式）
public interface PhysicalConstants {
    double AVOGADROS_NUMBER = 6.022_140_857e23;
    double BOLTZMANN_CONSTANT = 1.380_648_52e-23;
}

// After
public final class PhysicalConstants {
    private PhysicalConstants() {} // 不可实例化
    public static final double AVOGADROS_NUMBER = 6.022_140_857e23;
    public static final double BOLTZMANN_CONSTANT = 1.380_648_52e-23;
}
```

---

## §泛型

### Item 28：列表优于数组

**识别**：使用泛型数组、协变陷阱

**修复**：用 `List<E>` 替代 `E[]`

---

### Item 29-31：泛型类、泛型方法、通配符

**识别**：编写或修改泛型代码时类型不安全的强转

**修复**：
- PECS 原则：Producer extends, Consumer super
  - `List<? extends T>` 用于读
  - `List<? super T>` 用于写
- 用 `<T>` 替代 `Object` 强转

---

## §枚举与注解

### Item 34：用 enum 代替 int 常量

**识别**：`public static final int STATUS_PAID = 1;`

**修复**：用 enum

```java
// Before
public class Order {
    public static final int STATUS_DRAFT = 0;
    public static final int STATUS_PAID = 1;
    public static final int STATUS_SHIPPED = 2;
    private int status;
}

// After
public enum OrderStatus {
    DRAFT, PAID, SHIPPED;
    public boolean canBeCancelled() {
        return this != SHIPPED;
    }
}
public class Order {
    private OrderStatus status;
}
```

**好处**：类型安全、可加方法、可用 switch 穷举、可序列化。

---

### Item 36：用 EnumSet 替代位字段

**识别**：`static final int OPTION_A = 1; static final int OPTION_B = 2;` + 按位或

**修复**：用 `EnumSet<Option>`

---

## §Lambda 与 Stream

### Item 42：Lambda 优于匿名内部类

**识别**：单方法接口的匿名内部类

**修复**：用 Lambda 或方法引用

```java
// Before
Collections.sort(words, new Comparator<String>() {
    public int compare(String a, String b) {
        return Integer.compare(a.length(), b.length());
    }
});

// After
words.sort(Comparator.comparingInt(String::length));
```

---

### Item 45：明智地使用 Stream

**识别**：用 Stream 写了一切，包括不适合的场景

**修复方向**：
- Stream **适合**：filter → map → reduce 的纯函数链
- Stream **不适合**：副作用、抛检查异常、可读性差
- 多行 Stream 优于一行难懂 Stream

```java
// 不好：一行塞太多
list.stream().filter(o -> o.getAmount().compareTo(BigDecimal.ZERO) > 0 && o.getStatus() == PAID).mapToInt(Order::getQty).sum();

// 好：分行
return list.stream()
    .filter(o -> o.getAmount().signum() > 0)
    .filter(o -> o.getStatus() == PAID)
    .mapToInt(Order::getQty)
    .sum();
```

---

### Item 49：检查参数的有效性

**识别**：方法不验证参数，错误延迟到深处

**修复**：方法开头验证

```java
public Order placeOrder(Customer customer, List<Item> items) {
    Objects.requireNonNull(customer, "customer must not be null");
    if (items == null || items.isEmpty()) {
        throw new IllegalArgumentException("items must not be empty");
    }
    // ...
}
```

---

### Item 55：明智地返回 Optional

**识别**：
- 方法返回 null 表示"没有"
- 方法参数类型是 `Optional<T>`（反模式）
- 字段类型是 `Optional<T>`（反模式）

**修复**：
- 只在**返回值**用 Optional
- 集合类返回空集合而非 `Optional<List<X>>`
- 调用方用 `orElseThrow` / `orElse` / `ifPresent`，**避免** `.get()` 不判空

```java
// 推荐
public Optional<Order> findById(String id) { ... }

// 调用方
Order order = orderRepo.findById(id)
    .orElseThrow(() -> new OrderNotFoundException(id));

// 反模式（不要在参数用 Optional）
public void process(Optional<Order> order) { ... } // 别这样写
```

---

## §并发

### Item 78：同步访问共享的可变数据

**识别**：多线程访问的字段无 `volatile` / 无锁

**修复**：根据场景选 `synchronized` / `volatile` / `java.util.concurrent` 工具类

---

### Item 80：executors / tasks / streams 优于线程

**识别**：手动 `new Thread()`

**修复**：用 `ExecutorService` 或 `CompletableFuture`

---

### Item 81：concurrent 工具优于 wait/notify

**识别**：手写 `wait()` / `notify()` / `notifyAll()`

**修复**：用 `CountDownLatch` / `Semaphore` / `ConcurrentHashMap` / `BlockingQueue` 等

---

## §异常

### Item 69：异常仅用于异常情况

**识别**：用异常控制流程（如循环用 `ArrayIndexOutOfBoundsException` 终止）

**修复**：用普通条件判断

---

### Item 71：避免不必要地使用受检异常

**识别**：处处 `throws Exception` / 调用方只能 `catch` 然后 `e.printStackTrace()`

**修复**：用 `RuntimeException` 子类（除非调用方真的能恢复）

---

### Item 73：抛出与抽象级别相对应的异常

**识别**：业务方法抛出 `SQLException` / `IOException`

**修复**：包装为业务异常

```java
// Before
public Order placeOrder(...) throws SQLException, IOException { ... }

// After
public Order placeOrder(...) {
    try { /* ... */ }
    catch (SQLException e) { throw new OrderPersistenceException("...", e); }
}
```

---

## §综合速查

### Java 14+ 现代特性优先

| 老写法 | 新写法 | 说明 |
|--------|-------|------|
| Lombok `@Data` 不可变 POJO | `record` | 自动 equals/hashCode/toString |
| 长 switch | switch expression | Java 14+ |
| `if (obj instanceof Foo) { Foo f = (Foo) obj; ... }` | `if (obj instanceof Foo f) { ... }` | Pattern matching |
| 多行字符串 `+` 拼接 | text block `"""` | Java 15+ |
| 显式锁 | `java.util.concurrent.locks` | 仍推荐用 synchronized 简单场景 |

### Spring Boot 项目中的常见 Item 应用

| 场景 | Effective Java Item | 应用 |
|------|------------------|------|
| @Service Bean 设计 | Item 5（依赖注入）、Item 15（最小可访问）| 构造函数注入、所有协作者私有 |
| DTO 设计 | Item 17（不可变）、Item 12（toString）| 用 record + Bean Validation |
| 异常体系 | Item 71（少用受检）、Item 73（抽象层级）| 自定义业务异常继承 RuntimeException |
| 枚举类型 | Item 34、Item 35 | 业务状态/类型一律用 enum |
| 配置属性 | Item 17、Item 1 | `@ConfigurationProperties` + record |

---

## §与其他文档的衔接

- 命名 / 函数长度 / 参数数量 → `clean-code-rules.md`
- 通用重构手法 mechanics → `refactoring-techniques.md`
- 涉及 Spring 容器与注入 → `spring-specific.md`
- 涉及领域模型设计 → `ddd-tactical.md`
