# 代码整洁之道（Clean Code）量化规范

本文档摘录 Robert C. Martin《代码整洁之道》中**可量化**的规则——命名、函数长度、参数数量、注释、错误处理、边界条件——作为 Java 重构时的具体判断依据。

设计理念：Clean Code 中很多原则是**主观的**（如"函数应当短小"），本文档把它们**量化为阈值**，让诊断与决策可审计。

---

## §命名

### 类名

- **名词或名词短语**：`Customer`、`WikiPage`、`Account`、`AddressParser`
- **避免动词**：不要用 `Manager`、`Processor`、`Handler` 这类后缀作为类的唯一职责描述
- **避免 Data / Info 这种无意义后缀**：`CustomerData` 等同于 `Customer`，多余
- **避免缩写**：`UsrInf` → `UserInfo`；`OrdSvc` → `OrderService`
- **领域词汇优先于技术词汇**：业务类用领域词（`Invoice`），技术类用技术词（`HttpClient`）

### 方法名

- **动词或动词短语**：`postPayment`、`deletePage`、`save`
- **属性访问器**：`getName`、`setName`、`isPosted`（遵循 JavaBean 约定）
- **当方法名需要超过 4 个单词**，考虑这个方法是否做了多件事
- **不要用相反含义的词**：`add` / `remove`（不要用 `insert` / `delete` 混用，除非语义真的不同）

### 变量名

- **有意义的名字**：`d` → `daysSinceCreation`；`l` → `last`、`length`、`list`（消除歧义）
- **避免误导**：`accountList` 应该真的是 `List<Account>`；如果是 `Account[]`，应叫 `accounts`
- **避免使用 1、I、l、0、O 这种容易混淆的字符**
- **布尔变量加 is/has/can/should 前缀**：`active` → `isActive`
- **作用域大小决定名字长度**：循环计数器可以是 `i`；类字段名应详细

### 神秘命名速查表

| 不好 | 好 |
|------|---|
| `data` | `orderItems` / `customerProfile` |
| `info` | `userContactInfo` |
| `temp` | （根据用途命名，或考虑是否真需要） |
| `process` | `validateOrder` / `chargeCustomer` |
| `handle` | `handleTimeout` / `onPaymentFailed`（明确"处理什么"） |
| `doSomething` | 不应当出现的方法名 |
| `util` / `helper` | （考虑是否能改为更具体的功能名） |

### 命名一致性

同一概念在整个代码库中用同一个词：
- `fetch` / `retrieve` / `get` 不要混用
- `add` / `append` / `insert` 不要混用
- `delete` / `remove` / `discard` 不要混用

---

## §函数长度与复杂度

### 行数

| 类型 | 推荐阈值 | 硬上限 |
|------|--------|-------|
| 普通方法 | ≤ 20 行 | 50 行 |
| Controller / Endpoint 方法 | ≤ 10 行 | 20 行（业务逻辑应下沉） |
| 测试方法 | ≤ 30 行 | 50 行 |
| 构造函数 | ≤ 10 行 | 20 行（含字段赋值） |
| 配置类 `@Bean` 方法 | ≤ 15 行 | 30 行 |

**计数规则**：注释、空行不算；多行 if/for 条件算 1 行；多行链式调用算 1 行。

**超出阈值的判定**：
- 30-50 行 → 中度长方法，**建议**重构
- 50-100 行 → 长方法，**应当**重构
- > 100 行 → 严重，**必须**重构（除非是配置生成、状态机定义等特殊场景）

### 圈复杂度（Cyclomatic Complexity）

| 复杂度 | 严重度 |
|-------|-------|
| 1-5 | 简单，易测试 |
| 6-10 | 中等，可接受 |
| 11-15 | 复杂，**建议**重构 |
| 16-20 | 高复杂，**应当**重构 |
| > 20 | 危险，**必须**重构 |

**降复杂度手法**：Extract Method、Replace Conditional with Polymorphism、Replace Nested Conditional with Guard Clauses（见 `refactoring-techniques.md` §3、§8）。

### 嵌套深度

| 深度 | 严重度 |
|------|-------|
| ≤ 2 层 | 良好 |
| 3 层 | 可接受 |
| 4 层 | **建议**重构 |
| ≥ 5 层 | **必须**重构 |

---

## §参数数量

| 参数数量 | 评价 |
|---------|------|
| 0 个 | 理想 |
| 1 个 | 好 |
| 2 个 | 可接受 |
| 3 个 | 应避免（除非有强语义合理性） |
| ≥ 4 个 | **建议** Introduce Parameter Object |
| ≥ 7 个 | **必须**重构 |

**例外情况**（≥ 4 参数可以接受）：
- Builder 模式的 build 方法（参数通常通过 setter 传入）
- 构造函数（依赖注入，但通常也建议 ≤ 5）
- 数学函数（如 `f(x, y, z)` 各参数语义独立）
- 测试 fixture / setup 方法

**避免布尔参数**：`save(order, true)` 不如 `saveAndNotify(order)` 与 `saveSilently(order)` 拆开。布尔参数通常意味着方法在做两件事。

---

## §注释

### 好的注释（保留）

1. **法律性注释**：版权声明、许可证
2. **解释意图的注释**：为什么用这个算法、为什么不用看起来更简单的方案
3. **警示性注释**：`// 注意：这里不能改用 ConcurrentHashMap，因为我们依赖 null 值语义`
4. **TODO 注释**：临时标记需要后续处理的地方（但要尽快清理）
5. **公开 API 的 Javadoc**：尤其是参数、返回值、异常约定

### 坏的注释（删除或重构）

1. **复述代码的注释**：`// 把 i 加 1` 后面跟 `i++` → 删除
2. **过时的注释**：与代码已经不一致 → 删除或修正
3. **被注释掉的代码**：删除（git 会保留历史）
4. **位置标记注释**：`////// Public Methods //////` → 删除，用结构表达
5. **闭合括号注释**：`} // end of for` → 改用 Extract Method 让方法变短
6. **归属与署名**：`// Added by Bob` → 删除，git blame 会显示

### 注释的"代替方案"

| 想写的注释 | 更好的做法 |
|----------|----------|
| `// 计算运费` | 提取方法 `calculateShipping()` |
| `// magic number 86400000 是一天的毫秒数` | `static final long ONE_DAY_MS = Duration.ofDays(1).toMillis();` |
| `// 这段代码做了 X 然后 Y` | 拆成两个有名字的方法 |
| `// status: 1=待付款 2=已付款 3=已发货` | 改用 enum |

---

## §函数原则

### 函数应当做一件事（Single Level of Abstraction）

判定：方法体内的每行代码是否处于**同一抽象层级**？

```java
// 坏：混合多层抽象
public void placeOrder(Order order) {
    // 高层：业务流程
    validate(order);
    // 低层：直接操作字段
    if (order.getItems() == null || order.getItems().isEmpty()) {
        throw new IllegalArgumentException();
    }
    // 高层：业务流程
    chargePayment(order);
}

// 好：所有操作都在同一抽象层
public void placeOrder(Order order) {
    validate(order);
    chargePayment(order);
    notifyCustomer(order);
}
```

### 命令-查询分离（Command-Query Separation）

- **查询函数**：返回值、不修改状态（`getCustomer()`、`isReady()`）
- **命令函数**：修改状态、无返回值或返回 void / 状态码（`saveCustomer()`、`charge()`）

**违反示例**：`boolean set(String attribute, String value)` 既修改状态又返回布尔 → 应拆为 `set` 和 `attributeExists`。

### 没有副作用

函数名说做 A，就只做 A，不能偷偷做 B：

```java
// 坏：checkPassword 偷偷做了 initializeSession
public boolean checkPassword(String user, String password) {
    User u = findUser(user);
    if (u != null && u.passwordMatches(password)) {
        Session.initialize();  // 副作用！
        return true;
    }
    return false;
}

// 好：拆开
boolean valid = checkPassword(user, password);
if (valid) initializeSession();
```

---

## §错误处理

### 异常优于错误码

```java
// 坏：错误码
public int deletePage(Page page) {
    if (page == null) return E_NULL;
    // ...
    return E_OK;
}

// 好：异常
public void deletePage(Page page) {
    Objects.requireNonNull(page, "page");
    // ...
}
```

### 异常类型选择

| 场景 | 异常类型 |
|------|---------|
| 调用方编程错误（null、非法参数）| `IllegalArgumentException` / `NullPointerException` / `IllegalStateException` |
| 业务规则违反 | 自定义业务异常（继承 RuntimeException） |
| 外部依赖失败 | 自定义运行时异常 / 框架异常 |
| 受检异常 | 极少用——只在调用方**有合理恢复策略**时用 |

### 不要返回 null

```java
// 坏：调用方必须判空
public List<Item> getItems() {
    if (cart == null) return null;
    return cart.getItems();
}

// 好：返回空集合
public List<Item> getItems() {
    if (cart == null) return Collections.emptyList();
    return cart.getItems();
}
```

### 不要传递 null

如果方法不接受 null 参数，用 `Objects.requireNonNull` 或 `@NonNull` 注解显式表达，不要在内部隐式假设非 null。

### Optional 的正确用法

- **返回值类型**：可以用 `Optional<T>`（如 `findById`）
- **不要做参数**：方法参数不要是 `Optional<T>`，太啰嗦
- **不要做字段**：字段也不要是 `Optional<T>`
- **不要 .get() 不判空**：`opt.orElseThrow()` / `opt.ifPresent()` / `opt.orElse(default)` 优于 `.get()`

详见 `effective-java-notes.md` §Optional。

---

## §边界条件

### 边界值清单

每写一段处理输入的代码，问自己以下边界：

- **null**：参数可以为 null 吗？返回值可以为 null 吗？
- **空集合**：`List` / `Map` / `Set` 为空时行为？
- **0 与 1**：`count == 0` / `count == 1` 时行为？
- **负数**：金额、数量、索引为负时行为？
- **极大值**：`Integer.MAX_VALUE` / `Long.MAX_VALUE` 是否溢出？
- **空字符串与空白**：`""` / `"   "` / null 是否等价？
- **首尾元素**：循环边界是否包含/排除首尾正确？
- **重复**：重复提交、重复元素如何处理？

### 防御性编程的度

- **公开 API**：边界值都要验证（参数校验 + 返回值约定）
- **内部方法**：信任调用方，但加 `assert` 或 `requireNonNull`
- **过度防御 = 噪声**：内部代码每个方法都判空会降低可读性

---

## §类设计原则（SRP / OCP）

虽然 Clean Code 主要讲方法层面，类层面的规则也很重要：

### 单一职责（SRP）

判定方法："这个类**因为什么原因**而修改？" 如果有多个不相关的修改原因 → 违反 SRP。

### 字段数量

| 字段数量 | 评价 |
|---------|------|
| ≤ 7 个 | 良好 |
| 8-15 | 可接受 |
| 16-25 | 偏多，**建议**评估拆分 |
| > 25 | 过多，**应当**拆分 |

**例外**：DTO / VO / ORM 实体类可以放宽（这些是数据载体，本就该字段多）。

### 公共方法数量

| 方法数量 | 评价 |
|---------|------|
| ≤ 10 个 | 良好 |
| 11-20 | 可接受 |
| > 20 | 过多，**建议**评估拆分 |

---

## §测试代码的整洁

测试代码也是代码，同样需要整洁：

### Given-When-Then 三段式

```java
@Test
void placeOrder_should_apply_vip_discount() {
    // Given
    Order order = new Order().withVip(true);
    List<Item> items = List.of(new Item(BigDecimal.TEN));

    // When
    BigDecimal total = orderService.placeOrder(order, items);

    // Then
    assertThat(total).isEqualByComparingTo("8.00");
}
```

### 一个测试一个断言（理想情况）

允许多个相关断言，但**禁止**一个测试方法测试多个无关行为。

### 测试命名

- `methodName_scenario_expectedResult`：`placeOrder_vip_should_apply_discount`
- `should_xxx_when_yyy`：`should_throw_when_inventory_insufficient`
- 不要 `test1` / `testPlaceOrder`（看不出测的什么场景）

### 测试不应当依赖执行顺序

每个测试独立，可乱序执行，可单独执行。

---

## §速查阈值表

| 度量项 | 推荐 | 警戒 | 强制重构 |
|-------|------|------|---------|
| 方法行数 | ≤ 20 | 30 | > 50 |
| 圈复杂度 | ≤ 5 | 10 | > 15 |
| 嵌套深度 | ≤ 2 | 3 | > 4 |
| 参数数量 | ≤ 2 | 3 | ≥ 4 |
| 类行数 | ≤ 200 | 500 | > 1000 |
| 类字段数 | ≤ 7 | 15 | > 25 |
| 类公共方法数 | ≤ 10 | 20 | > 30 |

**注意**：这些是**判定起点**，不是**绝对真理**。代码语义、变更频率、领域复杂度都会调整阈值。诊断报告中使用阈值时，要同时给出"为什么这里超阈值是问题"的解释。
