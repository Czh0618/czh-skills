# Java 重构手法目录

本文档列出 Fowler《重构》中最常用的约 30 个手法，每个含：动机、mechanics（机械化步骤）、Java 示例、测试要点、常见坑。

按 Fowler 原书章节编号组织，方便交叉引用。

**通用机械化原则**（适用于所有手法）：
1. **小步快跑**：每步改动后立即编译、测试，绿了再下一步
2. **保留旧调用点直到新代码就绪**：先建新的，验证可用，再迁移调用，最后删旧的
3. **单 commit 单意图**：一个手法一个 commit，不混合多个手法
4. **测试保护**：所有手法都假定有测试保护；无测试时先做特征化测试（见 `legacy-code.md`）

---

## §3 重新组织函数

### 3.1 Extract Method（提炼函数）⭐

**动机**：方法过长 / 一段代码做了多件事 / 需要注释解释一段代码

**mechanics**：
1. 创建新方法，命名以**做什么**命名（不是**怎么做**）
2. 把要提取的代码复制到新方法
3. 检查局部变量：被读取的变量作为参数；被赋值且后续仍用的变量作为返回值
4. 编译
5. 把原代码替换为方法调用，编译
6. 测试

**示例**：
```java
// Before
public void printOwing() {
    Enumeration e = orders.elements();
    double outstanding = 0.0;
    System.out.println("**** 客户欠款 ****");
    System.out.println("姓名：" + name);
    while (e.hasMoreElements()) {
        Order each = (Order) e.nextElement();
        outstanding += each.getAmount();
    }
    System.out.println("应付金额：" + outstanding);
}

// After
public void printOwing() {
    printBanner();
    double outstanding = calculateOutstanding();
    printDetails(outstanding);
}
private void printBanner() { /* ... */ }
private double calculateOutstanding() { /* ... */ }
private void printDetails(double outstanding) { /* ... */ }
```

**测试要点**：每抽一个方法跑一次现有测试。

**常见坑**：
- 被赋值的局部变量有 2+ 个 → 拆成多步，每步处理一个变量
- 包含 `return` / `break` / `continue` → 改写控制流再抽
- 抽出的方法应当**短小、命名清晰**——如果命名困难，说明职责还不单一

---

### 3.2 Inline Method（内联函数）

**动机**：方法体比方法名还清晰 / 间接层无价值

**mechanics**：
1. 检查方法没有被多态覆写
2. 找到所有调用点
3. 用方法体替换每个调用点
4. 删除方法定义
5. 编译并测试

**示例**：
```java
// Before
public int getRating() {
    return (moreThanFiveLateDeliveries()) ? 2 : 1;
}
private boolean moreThanFiveLateDeliveries() {
    return numberOfLateDeliveries > 5;
}

// After
public int getRating() {
    return (numberOfLateDeliveries > 5) ? 2 : 1;
}
```

**常见坑**：方法被子类覆写 → 不要内联。

---

### 3.3 Extract Variable / Introduce Explaining Variable（提炼变量）

**动机**：复杂表达式难以理解

**示例**：
```java
// Before
if ((platform.toUpperCase().indexOf("MAC") > -1)
    && (browser.toUpperCase().indexOf("IE") > -1)
    && wasInitialized() && resize > 0) {
    // ...
}

// After
boolean isMacOs = platform.toUpperCase().indexOf("MAC") > -1;
boolean isIEBrowser = browser.toUpperCase().indexOf("IE") > -1;
boolean wasResized = resize > 0;
if (isMacOs && isIEBrowser && wasInitialized() && wasResized) {
    // ...
}
```

**常见坑**：变量数量过多反而降低可读性，3-5 个为宜。

---

### 3.4 Replace Temp with Query（以查询取代临时变量）

**动机**：临时变量只用一次或妨碍提炼

**示例**：
```java
// Before
double basePrice = quantity * itemPrice;
if (basePrice > 1000) return basePrice * 0.95;
else return basePrice * 0.98;

// After
if (basePrice() > 1000) return basePrice() * 0.95;
else return basePrice() * 0.98;
private double basePrice() { return quantity * itemPrice; }
```

**测试要点**：注意性能（多次调用），但通常 JIT 会内联。

---

### 3.5 Decompose Conditional（分解条件表达式）

**动机**：条件分支内部代码块复杂

**示例**：
```java
// Before
if (date.before(SUMMER_START) || date.after(SUMMER_END)) {
    charge = quantity * winterRate + winterServiceCharge;
} else {
    charge = quantity * summerRate;
}

// After
if (notSummer(date)) charge = winterCharge(quantity);
else charge = summerCharge(quantity);
```

**关联**：与 Extract Method 配合，是处理长方法的主力组合。

---

## §6 在对象之间搬移特性 / 参数对象

### 6.1 Introduce Parameter Object（引入参数对象）⭐

**动机**：方法参数列出现"数据泥团"（一组参数总是同时出现）

**mechanics**：
1. 创建新的值对象类（推荐 Java 17+ 用 record，否则用 immutable class）
2. 添加到原方法签名（与原参数并存）
3. 一个参数一个参数地从原签名删除，每删一个跑测试
4. 全部迁移后删除原参数
5. 检查所有调用点

**示例**：
```java
// Before
public BigDecimal calculateShipping(String province, String city,
                                     String district, String detail,
                                     double weight, boolean vip) { ... }

// After
public record ShippingAddress(String province, String city,
                               String district, String detail) {}
public BigDecimal calculateShipping(ShippingAddress addr, double weight, boolean vip) { ... }
```

**测试要点**：分多次迁移，每次只动一个调用点。

**常见坑**：值对象不要直接暴露 setter，构造时一次性赋值（不可变）。

---

### 6.2 Preserve Whole Object（保持对象完整）

**动机**：从一个对象取出多个值后作为参数传递

**示例**：
```java
// Before
int low = daysTempRange.getLow();
int high = daysTempRange.getHigh();
withinPlan = plan.withinRange(low, high);

// After
withinPlan = plan.withinRange(daysTempRange);
```

**常见坑**：会增加方法间的耦合（依赖整个对象而不是少数字段）；只有当对象稳定时再用。

---

### 6.3 Replace Parameter with Method Call（以函数调用取代参数）

**动机**：参数可由方法自己算出

**示例**：
```java
// Before
double basePrice = quantity * itemPrice;
double discount = computeDiscount(basePrice, quantity);

// After
double discount = computeDiscount();
private double computeDiscount() {
    double basePrice = quantity * itemPrice;
    // ...
}
```

---

## §7 在对象之间搬移特性 / 类重构

### 7.1 Move Method（搬移函数）⭐

**动机**：方法更多地使用另一个类的特性而不是自己的；或为了平衡两个类的职责

**mechanics**：
1. 检查源类中此方法使用的所有特性，看是否都该一起搬移
2. 在目标类创建新方法（参数包括原宿主类的引用或必要字段）
3. 把代码从源类拷贝过来，调整引用
4. 源方法变成一个委托（`target.newMethod(...)`）
5. 检查所有调用点，逐步迁移到直接调用 target
6. 最后删除源方法

**示例**：
```java
// Before: AccountType 中有
class AccountType {
    double overdraftCharge(int daysOverdrawn) {
        if (isPremium()) {
            double result = 10;
            if (daysOverdrawn > 7) result += (daysOverdrawn - 7) * 0.85;
            return result;
        } else {
            return daysOverdrawn * 1.75;
        }
    }
}
// Account.bankCharge() 调用 accountType.overdraftCharge(this.daysOverdrawn)

// After: 搬到 Account 类中
class Account {
    double overdraftCharge() {
        if (accountType.isPremium()) { /* ... */ }
        else return daysOverdrawn * 1.75;
    }
}
```

**测试要点**：每完成一个调用点的迁移就跑一次测试。

**常见坑**：
- 搬完后源类有"中间人"残留 → 评估是否要继续删除
- 搬移后产生新的依赖循环 → 用 Extract Interface 打破

---

### 7.2 Move Field（搬移字段）

**动机**：某字段被另一个类使用得更频繁

**mechanics**：
1. 在目标类创建字段
2. 修改源类的访问方法（getter/setter）转发到目标类
3. 把字段实际删除（或保留为转发）
4. 重新评估源类的方法是否也该一起搬

**常见坑**：搬移字段往往伴随 Move Method，应一起规划。

---

### 7.3 Extract Class（提炼类）⭐

**动机**：类承担了多个职责（上帝类、发散式变化）

**mechanics**：
1. 决定如何分解（按职责、按变化方向、按数据分组）
2. 创建新类
3. 原类持有新类的引用
4. 把相关字段用 Move Field 一个个搬过去
5. 把相关方法用 Move Method 一个个搬过去
6. 检查新类对外的接口，决定哪些方法应当公开
7. 给两个类各起一个清晰的名字

**示例**：
```java
// Before
class Person {
    String name;
    String officeAreaCode;
    String officeNumber;
    String getTelephoneNumber() {
        return "(" + officeAreaCode + ") " + officeNumber;
    }
}

// After
class Person {
    String name;
    TelephoneNumber officeTelephone;
    String getTelephoneNumber() {
        return officeTelephone.getTelephoneNumber();
    }
}
class TelephoneNumber {
    String areaCode;
    String number;
    String getTelephoneNumber() { return "(" + areaCode + ") " + number; }
}
```

**测试要点**：每搬一个字段或方法都跑一次测试。

**常见坑**：
- 一次性搬太多 → 退回小步迭代
- 拆出的新类没有领域意义 → 重新考虑拆分维度
- 拆完后调用方需要同时持有两个类的引用 → 用 Hide Delegate 隐藏

---

### 7.4 Inline Class（内联类）

**动机**：类的职责越来越少，已无独立存在价值

**mechanics**：与 Extract Class 相反，把字段和方法逐个搬回宿主类，最后删除空类。

---

### 7.5 Hide Delegate（隐藏委托）

**动机**：客户端通过服务端的字段访问另一个对象（`person.getDepartment().getManager()`）

**示例**：
```java
// Before
Person john = ...
String manager = john.getDepartment().getManager();

// After
Person john = ...
String manager = john.getManager(); // Person 内部委托给 Department
```

**常见坑**：可能引入"中间人"——只有当封装真的有意义时才做。

---

### 7.6 Remove Middle Man（移除中间人）

**动机**：与 Hide Delegate 相反——委托方法太多，类只是中间人。

**mechanics**：让客户端直接获取被委托对象。

---

### 7.7 Replace Data Value with Object（以对象取代数据值）

**动机**：基本类型（String / int）承担了领域含义但缺乏行为

**示例**：
```java
// Before
class Order {
    private String customerName; // 实际是身份证号
}

// After
class Order {
    private CustomerId customerId; // 有 validate / equals / toString
}
class CustomerId {
    private final String value;
    public CustomerId(String value) {
        if (!isValid(value)) throw new IllegalArgumentException();
        this.value = value;
    }
}
```

**常见坑**：不要过度——`String name`、`int age` 通常不必单独建对象，除非有领域行为。

---

## §8 简化条件表达式

### 8.1 Replace Conditional with Polymorphism（以多态取代条件式）⭐

**动机**：根据类型码做分支（如 switch / if-elseif 一长串）

**mechanics**：
1. 把类型码改为类继承体系（或策略接口）
2. 为每种类型创建一个子类（或策略实现）
3. 把条件分支中的代码搬到对应子类的方法中
4. 父类方法（或接口方法）变为抽象

**示例**：
```java
// Before
class Employee {
    int type; // 1=engineer, 2=salesman, 3=manager
    int monthlySalary() {
        switch (type) {
            case 1: return engineerSalary;
            case 2: return salesmanSalary + bonus;
            case 3: return managerSalary + bonus * 2;
        }
    }
}

// After
interface EmployeeType {
    int monthlySalary();
}
class Engineer implements EmployeeType { /* ... */ }
class Salesman implements EmployeeType { /* ... */ }
class Manager implements EmployeeType { /* ... */ }
```

**测试要点**：每搬一个分支跑一次，确保多态调用正确。

**常见坑**：
- 类型很少（2-3 种）且行为差异小 → 多态可能过度，保留 if 即可
- 在 Spring 项目中可借助 `@Component + Map<String, EmployeeType>` 自动注入（参见 `spring-specific.md` §策略模式）

---

### 8.2 Replace Nested Conditional with Guard Clauses（用守卫语句取代嵌套条件）⭐

**动机**：方法中正常路径被嵌套 if 淹没

**示例**：
```java
// Before
double getPayAmount() {
    double result;
    if (isDead) result = deadAmount();
    else {
        if (isSeparated) result = separatedAmount();
        else {
            if (isRetired) result = retiredAmount();
            else result = normalPayAmount();
        }
    }
    return result;
}

// After
double getPayAmount() {
    if (isDead) return deadAmount();
    if (isSeparated) return separatedAmount();
    if (isRetired) return retiredAmount();
    return normalPayAmount();
}
```

**常见坑**：早期返回不要包裹复杂资源释放（用 try-with-resources / try-finally 处理）。

---

### 8.3 Consolidate Conditional Expression（合并条件表达式）

**动机**：多个条件分支返回相同结果

**示例**：
```java
// Before
if (anEmployee.seniority < 2) return 0;
if (anEmployee.monthsDisabled > 12) return 0;
if (anEmployee.isPartTime) return 0;

// After
if (isNotEligibleForDisability(anEmployee)) return 0;
private boolean isNotEligibleForDisability(Employee e) {
    return e.seniority < 2 || e.monthsDisabled > 12 || e.isPartTime;
}
```

---

### 8.4 Replace Magic Number with Symbolic Constant（魔法数改常量）

**示例**：
```java
// Before
double potentialEnergy(double mass, double height) {
    return mass * 9.81 * height;
}

// After
static final double GRAVITATIONAL_CONSTANT = 9.81;
double potentialEnergy(double mass, double height) {
    return mass * GRAVITATIONAL_CONSTANT * height;
}
```

**Java 特定**：字符串常量考虑用 enum；状态码用 enum 而非 int。

---

## §9 简化函数调用与命名

### 9.1 Rename Method / Variable（重命名）⭐

**动机**：名字没有揭示意图

**mechanics**：
1. 如果方法是公有接口的一部分，先检查所有调用方（IDE 全文搜索）
2. 用 IDE 的 Rename 重构（Shift+F6）
3. 检查 XML 配置、反射调用、Spring SpEL 表达式中是否硬编码方法名
4. 编译并测试

**常见坑**：
- 反射调用的方法名 IDE 改不到 → 全文搜索字符串
- MyBatis XML 中的 `<select id="..."/>` 与 Mapper 接口方法同名 → 一起改
- 公有 API 重命名前评估调用方影响，必要时保留旧名作 `@Deprecated`

---

### 9.2 Remove Setting Method（移除设值函数）

**动机**：字段应在构造时确定，之后不应改变（不可变对象）

**示例**：
```java
// Before
class Account {
    private String accountId;
    public void setAccountId(String id) { this.accountId = id; }
}

// After
class Account {
    private final String accountId;
    public Account(String id) { this.accountId = id; }
    // 无 setter
}
```

**关联**：`effective-java-notes.md` §不可变对象。

---

## §10 处理概括关系（继承）

### 10.1 Pull Up Method / Pull Up Field（提升方法/字段）

**动机**：多个子类有完全相同的方法或字段

**mechanics**：
1. 比较子类方法的方法体，确保完全相同（或只有命名差异）
2. 移到父类（或新建中间父类）
3. 删除子类中的副本
4. 测试

---

### 10.2 Push Down Method / Push Down Field（下移方法/字段）

**动机**：父类的方法只有部分子类使用

**mechanics**：
1. 移到使用它的子类
2. 父类删除
3. 测试

---

### 10.3 Form Template Method（构造模板方法）

**动机**：多个子类有相似的执行步骤但细节不同

**示例**：
```java
// Before
class HtmlReport { void generate() { writeHeader(); writeBody(); writeFooter(); } }
class PdfReport { void generate() { writePdfHeader(); writePdfBody(); writePdfFooter(); } }

// After
abstract class Report {
    final void generate() {
        writeHeader();
        writeBody();
        writeFooter();
    }
    abstract void writeHeader();
    abstract void writeBody();
    abstract void writeFooter();
}
class HtmlReport extends Report { /* 实现各 step */ }
class PdfReport extends Report { /* 实现各 step */ }
```

**Java 现代写法**：若步骤独立性高，可改用 Strategy + 组合代替继承。

---

### 10.4 Replace Inheritance with Delegation（以委托取代继承）

**动机**：子类只使用父类一小部分功能 / 不希望继承父类的接口

**mechanics**：
1. 在子类创建一个父类字段
2. 把所有调用 super 的地方改为调用此字段
3. 父类接口不再继承
4. 测试

---

## 重构手法选择速查

按"我要解决什么问题"选手法：

| 我的问题 | 首选手法 | 备选 |
|---------|---------|------|
| 方法太长 | Extract Method | Decompose Conditional / Replace Temp with Query |
| 参数太多 | Introduce Parameter Object | Preserve Whole Object |
| 类太大 | Extract Class | Extract Subclass |
| 重复代码 | Extract Method + Pull Up Method | Form Template Method |
| 嵌套太深 | Replace Nested Conditional with Guard Clauses | Decompose Conditional |
| switch / 类型码 | Replace Conditional with Polymorphism | Replace Type Code with Strategy |
| 行为在错误的类 | Move Method | Move Field |
| 数据字段成组 | Introduce Parameter Object / Extract Class | - |
| 类只是中间人 | Remove Middle Man | Inline Class |
| 命名不清 | Rename | - |
| 魔法数 | Replace Magic Number with Symbolic Constant | Replace Magic String with Enum |
| 贫血模型 | Move Method（行为搬入数据类） | 参见 ddd-tactical.md |
| 循环依赖 | Extract Interface（DIP）| Move Method |

---

## 与其他文档的衔接

- **识别坏味道** → `smells-catalog.md`
- **量化规范（命名/长度/参数）** → `clean-code-rules.md`
- **无测试场景如何重构** → `legacy-code.md`
- **Spring 场景特定手法** → `spring-specific.md`
- **DDD 战术建模** → `ddd-tactical.md`
- **Java 语言特性最佳实践** → `effective-java-notes.md`
- **输出模板** → `output-templates.md`
