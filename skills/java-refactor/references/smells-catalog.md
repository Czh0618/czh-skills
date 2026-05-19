# Java 坏味道识别目录

本文档列出 18 种 Java/Spring Boot 项目中高频出现的代码坏味道。每条只负责**识别**（症状、判定阈值、关联手法跳转），具体改法在 `refactoring-techniques.md`。

## 与全局规则的映射

`~/.claude/rules/code-quality.md` 定义了 7 类通用坏味道。本文档的 18 种 Java 具体坏味道按以下方式对齐：

| 全局类别 | 包含的 Java 具体坏味道 |
|---------|---------------------|
| 僵化（Rigidity） | 上帝类、霰弹式修改、循环依赖 |
| 冗余（Redundancy） | 重复代码、平行继承体系 |
| 循环依赖（Circular Dependency） | 循环依赖、不当依赖 |
| 脆弱性（Fragility） | 不当依赖、临时字段、Switch / 类型码 |
| 晦涩性（Obscurity） | 神秘命名、长方法、过多 if 嵌套、注释当说明、贫血模型 |
| 数据泥团（Data Clump） | 数据泥团、长参数列 |
| 不必要的复杂性（Needless Complexity） | 长方法、中间人、过多 if 嵌套、魔法数、过度抽象 |

引用坏味道时优先使用全局类别名，再用 Java 具体名做补充说明。

---

## 类与方法结构类

### 1. 长方法（Long Method）

**全局映射**：晦涩性 / 不必要复杂性

**识别特征**：
- 单方法 > 30 行（非生成代码、非配置类）
- 圈复杂度（Cyclomatic Complexity）> 10
- 方法内出现多个空行分隔的"段落"，每段都在做不同的事
- 方法名是动词短语，但实际做了 N 件事（如 `placeOrder` 实际包含：参数校验、库存扣减、价格计算、订单落库、通知）

**严重度判定**：
- 高：> 100 行 或 圈复杂度 > 15 或 频繁修改
- 中：50-100 行 或 圈复杂度 10-15
- 低：30-50 行 但语义连贯

**关联手法**：Extract Method、Decompose Conditional、Replace Temp with Query

---

### 2. 长参数列（Long Parameter List）

**全局映射**：数据泥团

**识别特征**：
- 方法参数 ≥ 4 个（构造函数可放宽到 5-6 个，Builder 模式除外）
- 同一组参数反复出现在多个方法签名中（如 `userId, userName, userEmail, userPhone` 同时出现）
- 参数中有 boolean flag（提示方法在做多件事）

**严重度判定**：
- 高：≥ 7 个 或 同组参数在 3+ 方法中重复
- 中：4-6 个
- 低：4 个但语义独立

**关联手法**：Introduce Parameter Object、Preserve Whole Object、Replace Parameter with Method Call

---

### 3. 上帝类 / 过大的类（God Class / Large Class）

**全局映射**：僵化

**识别特征**：
- 单类 > 500 行
- 字段 > 15 个
- 公共方法 > 20 个
- 类名含模糊词：`XXXManager`、`XXXHelper`、`XXXUtil`、`XXXService` 后接业务领域名（如 `UserService` 承担用户/权限/审计/通知 4 类职责）
- 字段命名分组明显（如 `userXxx`、`orderXxx`、`auditXxx` 混在同一个类中）

**严重度判定**：
- 高：> 1000 行 或 字段 > 25 或 跨多个业务领域
- 中：500-1000 行
- 低：500 行以内但分层清晰

**关联手法**：Extract Class、Extract Subclass、Move Method、Move Field

---

### 4. 数据类 / 贫血模型（Data Class / Anemic Domain Model）

**全局映射**：晦涩性

**识别特征**：
- POJO 只有 getter/setter，没有任何业务方法
- 业务逻辑全在 `XxxService` 里操作 POJO 的字段
- `OrderService.calculateAmount(Order order)` 这类签名——本应是 `order.calculateAmount()`
- 字段直接暴露，没有领域约束（如 Order 的 status 字段可以被任意 set 成任何值）

**严重度判定**：
- 高：核心领域对象（订单、用户、账户）完全贫血
- 中：辅助对象贫血但有部分校验
- 低：DTO / VO（这本来就该贫血，**不算坏味道**）

**关联手法**：Move Method（从 Service 搬到领域对象）、Encapsulate Field、Replace Data Value with Object，详见 `ddd-tactical.md`

---

### 5. 霰弹式修改（Shotgun Surgery）

**全局映射**：僵化 / 冗余

**识别特征**：
- 改一个业务规则需要同时改 N 个文件
- 同一个常量/字段名散落在多个类中
- 添加一个新字段（如订单的"优惠券字段"）需要修改 Order、OrderDTO、OrderVO、OrderMapper、OrderXML、OrderService 6+ 处

**严重度判定**：
- 高：改一处需联动 ≥ 5 处，且无编译器辅助（如字符串硬编码）
- 中：需联动 3-4 处
- 低：需联动 2-3 处但有强类型保证（编译器会报错）

**关联手法**：Move Method、Move Field、Inline Class（把分散的拉到一起）

---

### 6. 发散式变化（Divergent Change）

**全局映射**：僵化

**识别特征**：
- 同一个类因不同原因被频繁修改（"加新支付方式"和"加新通知渠道"都要改 OrderService）
- Git log 显示某文件的提交信息涉及多个无关业务主题
- 类内方法可以明显按"职责"分组

**严重度判定**：
- 高：每月被 3+ 个不相关需求改动
- 中：每月被 2 个不相关需求改动
- 低：偶发

**关联手法**：Extract Class（按变化方向拆分）

---

### 7. 平行继承体系（Parallel Inheritance Hierarchies）

**全局映射**：冗余

**识别特征**：
- 新增 `XxxImpl` 时必须同时新增 `XxxFactoryImpl`、`XxxConfigImpl`、`XxxValidatorImpl`
- 两个继承树的子类一一对应
- 类名前缀完全镜像

**严重度判定**：
- 高：3+ 个并行继承树
- 中：2 个并行继承树
- 低：1 个但已开始有镜像迹象

**关联手法**：Move Method、Move Field（把一个继承树的行为搬到另一个，消除并行）

---

### 8. 临时字段（Temporary Field）

**全局映射**：脆弱性 / 晦涩性

**识别特征**：
- 类中某字段只在特定方法被使用，其他方法访问时为 null
- 方法签名干净，但方法内部依赖类字段而不是参数（隐式参数）
- `if (this.tempContext != null)` 这种判空在多个方法中重复

**严重度判定**：
- 高：被并发访问（线程不安全）
- 中：单线程但导致方法间隐式耦合
- 低：仅一个方法使用

**关联手法**：Extract Class（把临时字段和相关方法一起搬出去）、Introduce Null Object

---

### 9. 数据泥团（Data Clumps）

**全局映射**：数据泥团

**识别特征**：
- 同一组字段反复出现在多个类/方法中（如 `province / city / district / detailAddress` 总是一起出现）
- 同一组参数反复出现在多个方法签名中
- 这组数据有明显的领域含义但没被建模为对象（地址、金额+币种、时间段）

**严重度判定**：
- 高：3+ 字段成组、出现在 5+ 处
- 中：2-3 字段成组、出现在 3-4 处
- 低：偶发

**关联手法**：Extract Class（建立值对象，如 `ShippingAddress`、`Money`、`DateRange`）

---

### 10. 神秘命名（Mysterious Name）

**全局映射**：晦涩性

**识别特征**：
- 变量名为 `data`、`info`、`obj`、`temp`、`a`、`b`、`x`
- 方法名为 `process`、`handle`、`doSomething`、`execute`
- 类名为 `XxxHelper`、`XxxUtil`、`XxxManager`、`CommonXxx`
- 缩写不可读：`usrInf`、`ordPrcCalc`、`mtSvc`
- 布尔变量没有 `is/has/can` 前缀：`active`（不知道是状态还是动作）

**严重度判定**：
- 高：公开 API 命名晦涩
- 中：内部命名晦涩但有注释
- 低：临时变量命名简短但作用域小

**关联手法**：Rename Method / Rename Variable，详见 `clean-code-rules.md` §命名

---

## 表达式与控制流类

### 11. 重复代码（Duplicated Code）

**全局映射**：冗余

**识别特征**：
- 两段代码逐字相同（拷贝粘贴）
- 两段代码结构相同、仅变量名/类型不同（参数化重复）
- 多个 catch 块的处理逻辑相同
- 多个方法的开头都做同一件事（前置校验、日志、上下文初始化）

**严重度判定**：
- 高：> 20 行重复 或 出现在 3+ 处
- 中：10-20 行重复 或 出现在 2 处
- 低：< 10 行 且 只 2 处（视情况，过度抽取也是坏味道）

**关联手法**：Extract Method、Pull Up Method（继承体系内）、Form Template Method

---

### 12. Switch 语句 / 类型码（Switch Statements / Type Code）

**全局映射**：脆弱性

**识别特征**：
- 同一组 case 分支在多处出现（每加一个新类型都要改 N 处）
- 用 int / String 表示类型（`if (type == 1) ... else if (type == 2) ...`）
- 用 `instanceof` 做分支判断（typeof switch）
- enum + switch 也算（虽然比字符串好，但仍违反开闭原则）

**严重度判定**：
- 高：相同 switch 出现在 3+ 处
- 中：单处 switch 有 5+ 个 case 且 case 内部有复杂逻辑
- 低：单处 switch 但每个 case 仅 1-2 行简单赋值

**关联手法**：Replace Conditional with Polymorphism、Replace Type Code with Subclasses、Replace Type Code with Strategy

---

### 13. 注释当说明（Comments as Excuse）

**全局映射**：晦涩性

**识别特征**：
- 注释解释"这段代码在做什么"（应当用方法名替代）
- 注释在为糟糕的命名"辩护"（`// 这个 a 其实是订单金额`）
- 注释长且复杂，但代码本身没有结构性命名
- 大段被注释掉的代码（应当删除，git 会保留历史）

**严重度判定**：
- 高：每个方法都有大段说明性注释
- 中：偶尔出现
- 低：复杂业务规则的"为什么"注释（这是合理注释）

**关联手法**：Extract Method（用方法名替代注释）、Rename Method、删除冗余注释

> 注意：本 skill 不反对"为什么"注释（解释非显然的业务约束、外部 API 怪癖、性能权衡），反对的是"是什么"注释（重复代码字面含义）。详见 `clean-code-rules.md` §注释。

---

### 14. 魔法数（Magic Number）

**全局映射**：晦涩性 / 不必要复杂性

**识别特征**：
- 代码中出现裸字面量：`if (status == 3)`、`Thread.sleep(86400000)`
- 字符串字面量散落在多处：`if ("PAID".equals(order.getStatus()))`
- 0 / 1 / -1 也算（除非作为下标）

**严重度判定**：
- 高：业务语义字面量散落 5+ 处
- 中：单处但语义晦涩（如 `86400000`）
- 低：基础常量（0 / 1 / 100）作下标或步长

**关联手法**：Replace Magic Number with Symbolic Constant、Replace Magic String with Enum

---

### 15. 过多 if 嵌套（Deeply Nested Conditionals）

**全局映射**：不必要的复杂性 / 晦涩性

**识别特征**：
- if / for / while 嵌套层级 ≥ 4
- 嵌套中混杂正常流程与异常处理（应当用 guard clause 提前返回）
- 多分支条件用一长串 `&&` 拼接（`if (a && b && c && !d && e)`）

**严重度判定**：
- 高：嵌套 ≥ 5 层 或 单方法多个 4 层嵌套
- 中：嵌套 4 层
- 低：嵌套 3 层

**关联手法**：Replace Nested Conditional with Guard Clauses、Decompose Conditional、Extract Method、Consolidate Conditional Expression

---

## 依赖与结构类

### 16. 中间人（Middle Man）

**全局映射**：不必要的复杂性

**识别特征**：
- 类的方法 80%+ 只是"转发"到另一个对象（`return delegate.xxx()`）
- 没有添加任何业务价值的 wrapper / proxy
- DTO 转 VO 时字段一一对应但没做任何变换（这本身可能合理，但 Service 之间的纯转发不合理）

**严重度判定**：
- 高：纯转发方法 ≥ 10 个
- 中：纯转发方法 5-10 个
- 低：少量但混合在有逻辑的方法中

**关联手法**：Remove Middle Man（让调用方直接持有 delegate）、Inline Method

---

### 17. 不当依赖 / 紧耦合（Inappropriate Intimacy）

**全局映射**：脆弱性 / 循环依赖

**识别特征**：
- 一个类频繁调用另一个类的细节方法（不止公共接口）
- 类 A 通过 reflection / 强制 cast 访问类 B 的私有字段
- 两个类互相 new 对方（双向依赖）
- 跨层调用：Controller 直接 new Repository、Service 调用其他模块的 Mapper

**严重度判定**：
- 高：双向依赖 或 跨模块紧耦合
- 中：跨包紧耦合
- 低：同包内细节访问（视情况）

**关联手法**：Hide Delegate、Extract Interface、Move Method（把调用方搬过去）

---

### 18. 循环依赖（Circular Dependency）

**全局映射**：循环依赖

**识别特征**：
- A.java 依赖 B.java，B.java 依赖 A.java
- Spring 启动报 `BeanCurrentlyInCreationException` 或 `@Lazy` 用于打破注入循环
- Maven 模块层面的循环引用（编译都通不过，但偶尔通过反射或 SPI 绕开）
- 包依赖图存在环

**严重度判定**：
- 高：模块级循环 或 Spring 启动失败
- 中：类级循环依赖（已用 @Lazy 临时打破）
- 低：单文件内方法之间的循环调用（视语义）

**关联手法**：Dependency Inversion（引入接口）、Move Method（把循环点搬到第三方）、Extract Interface，详见 `spring-specific.md` §循环依赖

---

## 扫描顺序建议

1. **先看包/模块结构**：循环依赖、分层泄露（坏味道 #18、#17）
2. **再看类**：上帝类、贫血模型、霰弹式修改（坏味道 #3、#4、#5、#6、#7、#8）
3. **再看方法**：长方法、长参数列、过多嵌套（坏味道 #1、#2、#15）
4. **最后看表达式**：重复代码、Switch、魔法数、神秘命名、注释（坏味道 #11、#12、#13、#14、#10）

自顶向下扫描的好处：高层结构问题修复后，很多低层问题会自动消失（如拆类后长方法可能不再是问题）。

## 不算坏味道的常见误判

为避免把"正常代码"诊断为坏味道，列出几种常见误判：

| 看起来像坏味道，但其实不是 | 解释 |
|--------------------------|-----|
| DTO/VO 只有 getter/setter | 这本来就该是数据载体，不是贫血模型 |
| Builder 模式有 10+ 参数 | Builder 本身就是解决长参数列的，不需要再拆 |
| `@Configuration` 类有 30+ 个 @Bean 方法 | 配置类按功能聚合是合理的 |
| Controller 方法签名有 5+ 注解 | `@PostMapping + @Valid + @RequestBody` 等是 Spring 约定 |
| `equals` / `hashCode` / `toString` 长 | IDE 生成的标准实现，不算长方法 |
| 单方法 Stream 链式调用 30 行 | 如语义连贯（map → filter → collect），不算长方法 |
| 异常类 `XxxException extends RuntimeException` 空类 | 异常体系需要类型区分，空类是合理的 |

---

## 输出建议

诊断时尽量做到"每个发现都有证据"：
- 引用具体行号（`L88-L210`）
- 引用具体计数（`字段数 18 > 阈值 15`）
- 引用具体证据（`UserService 同时处理用户/权限/审计/通知 4 个职责`）

诊断报告不是"AI 印象流"，是"基于阈值与计数的工程判断"。

