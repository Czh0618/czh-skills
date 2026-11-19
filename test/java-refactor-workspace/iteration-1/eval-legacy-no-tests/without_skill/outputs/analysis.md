# DiscountCalculator 遗留代码改造分析（No-Tests Legacy Code）

## 一句话回答

**强烈不建议直接在 `calculate` 里加几行 `if` 处理地区**。这是典型的 Michael Feathers 在《Working Effectively with Legacy Code》中描述的「无测试遗留代码（legacy code without tests）」场景，正确的做法是：**先固化行为 → 再打破依赖 → 最后通过 Sprout Method 安全加新功能**。

---

## 一、风险诊断（Risk Diagnosis）

| # | 坏味道 / 风险 | 位置 | 严重度 | 说明 |
|---|--------------|------|--------|------|
| 1 | 无测试遗留代码（Legacy code, no tests） | 整个类 | 高（Critical） | 没有回归网，任何改动都可能引入静默 bug |
| 2 | 硬编码依赖 / Hard-coded dependency | `new DbConnection(...)` | 高 | 直接 `new` 数据库连接，且写死生产 URL 和密码，不可测试、不可替换 |
| 3 | 静态调用紧耦合 / Static cling | `ConfigLoader.load(...)`、`Logger.log(...)` | 高 | 静态方法无法被 mock，构成 Feathers 所说的 *seam* 缺失 |
| 4 | 魔法数字 / Magic numbers | `5`, `3`, `4`, `0.05`, `0.8`, `1.2`, `0.5` | 中 | 等级码、品类系数、最大折扣上限均为字面量 |
| 5 | 类型码（Type Code） | `customer.getLevel() == 5` | 中 | 数字等级缺少语义，应为枚举 `CustomerLevel.VIP / GOLD / NORMAL` |
| 6 | 字符串硬比较 / Stringly-typed | `"ELECTRONICS"`, `"FOOD"` | 中 | 品类应为枚举 `ProductCategory` |
| 7 | 长方法 + 多职责 | `calculate(...)` | 中 | 同时承担：取数据、按等级算折扣、按品类调整、封顶、记日志 |
| 8 | 敏感信息泄露 / Credentials in code | `"root", "pwd"` | 高（安全） | 数据库口令硬编码在源码中，必须立即处理 |

> 说明：第 8 项虽然不是重构问题，但既然看到就必须指出——这是 P0 安全事故级别。

---

## 二、为什么不能「直接加几行 if」？

1. **没有回归网**：你不知道当前行为是否「正确」，更不知道改完后是否「未破坏旧用例」。Feathers 把这种情况叫 *editing without a safety net*。
2. **依赖无法隔离**：`calculate` 方法一启动就连真实数据库、读真实配置文件、写真实日志，意味着你即便想写测试，也无从下手。
3. **变更点会扩散**：地区折扣可能与等级折扣、品类系数、封顶规则相互作用，靠 `if` 堆叠会让分支组合爆炸（等级 × 品类 × 地区），将来下一个人接手更不敢动。
4. **修改原方法 = 修改历史契约**：方法签名变更或行为变更会影响所有上游调用者，而你不知道有谁在调用。

---

## 三、安全改造路线图（3 步走 Safe Path）

### Step 1：先做特征化测试（Characterization Test）固化当前行为

目标：在不理解代码意图的前提下，**捕获代码当前实际产出**作为基线（不是「应该产出什么」，而是「现在产出什么」）。

- 由于 `new DbConnection` 和 `ConfigLoader.load` 不可控，先采用 **Subclass and Override** 或 **Extract and Override Call** 手法（Feathers 第 25 章）：
  - 把 `new DbConnection(...)`、`ConfigLoader.load(...)`、`Logger.log(...)` 三处分别抽成 `protected` 方法：`createConnection()`、`loadConfig()`、`writeLog(String)`。
  - **注意**：这一步只做 Extract Method，不改任何逻辑，IDE 机械化重构可保证安全。
- 写一个 `DiscountCalculatorForTest extends DiscountCalculator`，在子类里 override 三个方法返回 Stub（内存假对象）。
- 用真实/构造的输入跑一遍 `calculate`，把输出 `BigDecimal` 记录下来作为黄金值（golden values），覆盖关键边界：
  - 各等级（1/2/3/4/5）
  - 各品类（ELECTRONICS / FOOD / 其他 / null）
  - 触发封顶 vs 未触发封顶
  - amount 为 0 / 负数 / 极大值

> **退路 / Rollback**：本步骤不修改业务逻辑，只是 Extract Method，可随时 `git revert`。

### Step 2：打破依赖（Break Dependencies）—— Extract Interface

在测试网就位后，进一步把硬依赖换成 *seam*：

- **Extract Interface**：
  - `DbConnection` → 抽取 `CustomerRepository` 接口，仅暴露 `Customer findById(String)`。
  - `ConfigLoader` 静态 → 包装为 `DiscountConfigProvider` 接口。
  - `Logger` 静态 → 替换为 `slf4j` 的 `Logger` 字段或 `AuditLogger` 接口。
- **改造构造器**：通过构造器注入这三个依赖（Constructor Injection），保留一个无参构造器或工厂方法兜底现有调用方（保持向后兼容）。
- 测试此时可改用普通 Mock 框架（Mockito）即可，特征化测试用例不变，期望值不变——这正是 Step 1 黄金值的价值。

> **退路 / Rollback**：保留旧构造器路径，新依赖注入不上线前先在测试中验证。

### Step 3：用 Sprout Method 加「按地区折扣」新功能

**核心思想**：新功能不写在旧方法里，而是「萌芽」出一个新的、独立可测的方法（Feathers 第 6 章 *Sprout Method / Sprout Class*）。

```
// 伪代码示意（不直接编辑用户代码，仅展示思路）
public BigDecimal calculate(String customerId, BigDecimal amount,
                            String productCategory, String region /* 新参数 */) {
    BigDecimal base = /* 旧逻辑保持不动 */;
    return applyRegionalAdjustment(base, region);   // ← Sprout
}

// 新方法：纯函数，零依赖，单元测试 100% 可达
BigDecimal applyRegionalAdjustment(BigDecimal discount, String region) {
    // 新的按地区规则，全部在这里
}
```

要点：
- `applyRegionalAdjustment` 是 **纯函数**：无 IO、无静态调用、无时间相关，单测零成本。
- 旧方法 `calculate` 几乎不动，特征化测试继续保护「旧路径」；新方法用 TDD 方式从零写测试。
- 如果地区规则较复杂（多条件组合），用 **Sprout Class**：抽 `RegionalDiscountPolicy`（策略模式），便于后续扩展华北/华南/海外等地区。
- 接口稳定性：新增参数 `region` 属破坏式变更，建议用方法重载保留旧签名一段时间，再渐进迁移。

> **退路 / Rollback**：Sprout 出的方法/类与旧逻辑解耦，可单独 revert 而不影响旧行为。

---

## 四、可选的后续清理（Optional Follow-ups）

只在 Step 1-3 完成且稳定后，再考虑：

1. 等级 `int` → `enum CustomerLevel { NORMAL, GOLD, VIP }`，魔法数字下沉为枚举常量。
2. 品类字符串 → `enum ProductCategory`，并以「策略 + Map」替换 if-else 链。
3. 按等级、按品类、按地区、封顶四段规则抽为各自的 `DiscountRule`，组成责任链 / 策略集合，便于单测和扩展。
4. 把硬编码生产数据库口令立即移到 `application.yml` / 配置中心 / Secret Manager，并轮换密钥（**安全 P0**，独立于本次重构）。

---

## 五、给团队的「不要做」清单（Anti-patterns to avoid）

- 「先重构再说，反正我熟悉这块」— 没有测试网时熟悉感是错觉。
- 「重写一遍更快」— 重写会丢失隐性业务规则（implicit invariants），是遗留代码最大的陷阱。
- 「先把测试欠着，下个迭代补」— 没有测试上线的改动，会让下个迭代更不敢动。
- 「直接在 `calculate` 里加 `if region.equals(...)`」— 让长方法更长、分支更乱、可测性更差。

---

## 六、总结

| 阶段 | 动作 | 产出 | 风险 |
|------|------|------|------|
| Step 1 | Extract Method + 子类化重写 + 特征化测试 | 黄金值测试套件 | 低（机械化重构） |
| Step 2 | Extract Interface + 构造器注入 | 可 mock 的依赖边界 | 低（行为不变） |
| Step 3 | Sprout Method/Class 加地区折扣 | 新功能 + 独立单测 | 低（新代码隔离） |
| 可选 | 枚举化、策略化、密钥外置 | 长期可维护性 | 中（按需推进） |

**一句话**：先建网（特征化测试），再换桩（打破依赖），最后长芽（Sprout 新功能）。比起「直接加几行 if」，这条路看似多走两步，但每一步都可回滚，每一步都有回归保护，是遗留代码加功能的标准安全路径。

---

*参考：Michael Feathers, _Working Effectively with Legacy Code_, Chapters 6 (Sprout Method/Class), 13 (Characterization Tests), 25 (Dependency-Breaking Techniques)。*
