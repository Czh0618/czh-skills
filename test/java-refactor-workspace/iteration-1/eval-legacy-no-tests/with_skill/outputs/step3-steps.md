# 重构执行步骤 — DiscountCalculator（步骤 1-4）

> 以下每步**独立 commit、独立可 revert**。严禁跨步骤耦合。
> 全程**不修改 calculate 内部业务逻辑**，只做依赖打破（步骤 1）和外围扩展（步骤 3-4）。

---

## 重构步骤 #1：Extract Interface 打破 3 处硬编码依赖

**手法**：Extract Interface（legacy-code.md §1）+ Parameterize Constructor（legacy-code.md §2）
**坏味道来源**：诊断 #1 / #2 / #3
**目的**：让 `DiscountCalculator` 在测试中**可被实例化、可被 mock 依赖**，为步骤 2 特征化测试铺路。
**影响文件**：
- 修改：`DiscountCalculator.java`（新增构造函数，原 new/static 调用改为接口方法调用）
- 新增：`CustomerGateway.java`（接口）、`DbCustomerGateway.java`（生产实现，保留 `new DbConnection(...)` 原样）
- 新增：`DiscountConfigProvider.java`（接口）、`PropertiesDiscountConfigProvider.java`（生产实现，包装 `ConfigLoader.load(...)`）
- 新增：`DiscountLogger.java`（接口）、`StaticDiscountLogger.java`（生产实现，包装 `Logger.log(...)`）
- 不变 API：`calculate(...)` 公开签名暂时不变

**前置条件**：
- [ ] 用户确认允许新增构造函数（参考路线图 §待确认 #2）
- [ ] 现有 calculate 调用方有几处？（理论上无影响 — 仍可走默认无参构造）

**Before**
```java
public class DiscountCalculator {
    public BigDecimal calculate(String customerId, BigDecimal amount, String productCategory) {
        DbConnection conn = new DbConnection("jdbc:mysql://prod-db/order", "root", "pwd");
        DiscountConfig config = ConfigLoader.load("discount.properties");
        Customer customer = conn.queryCustomer(customerId);
        // ... 计算 ...
        Logger.log("discount calculated: " + discount);
        return discount;
    }
}
```

**After**
```java
public class DiscountCalculator {
    private final CustomerGateway customerGateway;
    private final DiscountConfigProvider configProvider;
    private final DiscountLogger logger;

    // 生产环境：保持旧的零参构造，行为完全等价
    public DiscountCalculator() {
        this(new DbCustomerGateway(), new PropertiesDiscountConfigProvider(), new StaticDiscountLogger());
    }

    // 测试用：包级可见 / public 注入构造器
    public DiscountCalculator(CustomerGateway customerGateway,
                              DiscountConfigProvider configProvider,
                              DiscountLogger logger) {
        this.customerGateway = customerGateway;
        this.configProvider = configProvider;
        this.logger = logger;
    }

    public BigDecimal calculate(String customerId, BigDecimal amount, String productCategory) {
        DiscountConfig config = configProvider.load();         // was: ConfigLoader.load(...)
        Customer customer = customerGateway.findById(customerId); // was: new DbConnection(...).queryCustomer(...)
        // ... 计算逻辑 100% 原样保留（包括 maxDiscount 上限）...
        logger.log("discount calculated: " + discount);        // was: Logger.log(...)
        return discount;
    }
}
```

**机械化步骤**
1. 新建 3 个接口文件（`CustomerGateway` / `DiscountConfigProvider` / `DiscountLogger`），各只声明一个方法。
2. 新建 3 个生产实现类，内部代码完全照搬原 calculate 中的 `new DbConnection(...)` / `ConfigLoader.load(...)` / `Logger.log(...)` 三行。**不重构、不优化**。
3. 在 `DiscountCalculator` 增加 3 个 final 字段 + 双构造函数（无参委派 → 全参）。
4. 把 calculate 内部 3 处调用点逐字替换为接口方法调用。**不修改任何业务分支**。
5. 编译。
6. 手工冒烟（如果生产有入口）：调一次 calculate，确认行为不变。
7. commit：`refactor(discount): extract 3 collaborators for testability (no behavior change)`。

**验证**：编译通过 + 任何已有手工/集成回归不报错。**此步无新测试**（测试在步骤 2）。

**回滚策略**：单 commit，`git revert <hash>`，无 DB / 配置 / 外部副作用。

**后续衔接**：完成后启用步骤 #2。

---

## 重构步骤 #2：Characterization Test 固化当前行为

**手法**：Characterization Test（legacy-code.md §特征化测试）
**坏味道来源**：诊断 #0（无测试覆盖）
**目的**：用 Feathers 的"故意错预期 → 跑失败 → 抄实际值"流程，**记录** calculate 现在到底做什么，作为后续所有改动的安全网。
**影响文件**：
- 新增：`DiscountCalculatorCharacterizationTest.java`（仅测试代码，不改生产代码）

**前置条件**：
- [x] 步骤 #1 已完成（否则无法 mock 依赖、无法构造 calculator）
- [ ] 用户提供测试框架（默认按 JUnit 5 + Mockito + AssertJ 编写）

**Before**：无测试。

**After**（节选两个分支，实际需覆盖 5-8 个）
```java
class DiscountCalculatorCharacterizationTest {

    private CustomerGateway gateway;
    private DiscountConfigProvider configProvider;
    private DiscountLogger logger;
    private DiscountCalculator calc;

    @BeforeEach
    void setUp() {
        gateway = mock(CustomerGateway.class);
        configProvider = mock(DiscountConfigProvider.class);
        logger = mock(DiscountLogger.class);
        DiscountConfig cfg = new DiscountConfig();
        cfg.setVipRate(0.20);   // 假设值 — 跑红再改成"实际值"
        cfg.setGoldRate(0.10);
        when(configProvider.load()).thenReturn(cfg);
        calc = new DiscountCalculator(gateway, configProvider, logger);
    }

    @Test
    void characterize_vipLevel5_electronics_under_cap() {
        when(gateway.findById("C1")).thenReturn(customer(5));
        BigDecimal result = calc.calculate("C1", new BigDecimal("100"), "ELECTRONICS");
        // 第 1 次故意写错：assertThat(result).isEqualByComparingTo("-9999"); 跑红 → 实际 16.00 → 改为 16.00
        assertThat(result).isEqualByComparingTo("16.00");
    }

    @Test
    void characterize_normalLevel_food_hits_maxCap() {
        when(gateway.findById("C2")).thenReturn(customer(1));
        BigDecimal result = calc.calculate("C2", new BigDecimal("1000"), "FOOD");
        // 0.05 * 1000 * 1.2 = 60，未触顶；用大额触顶测试单独写一条
        assertThat(result).isEqualByComparingTo("60.00");
    }

    private Customer customer(int level) { Customer c = new Customer(); c.setLevel(level); return c; }
}
```

**机械化步骤**
1. 列出 calculate 的所有分支组合（level ∈ {5, 3/4, 其他} × category ∈ {ELECTRONICS, FOOD, 其他} × maxDiscount 是否触顶）。
2. 对每个组合写一条测试，**预期值故意写错**（如 `-9999`）。
3. 跑测试，从失败信息抄出实际值。
4. 把预期改成实际值，测试转绿。
5. 至少覆盖 5-8 条路径，含 maxDiscount 上限分支。
6. commit：`test(discount): add characterization tests pinning current behavior`。

**验证**：
```bash
mvn -Dtest=DiscountCalculatorCharacterizationTest test
# 或 gradle test --tests DiscountCalculatorCharacterizationTest
```
全绿 = 当前行为已被锁定。

**回滚策略**：仅新增测试文件，可直接 `git revert` 或删除文件，无生产影响。

**后续衔接**：步骤 2 全绿是步骤 3-4 的**硬门禁**。

---

## 重构步骤 #3（Sprout Method）：新增独立可测的 `applyRegionDiscount`

**手法**：**Sprout Method（萌芽方法）**（legacy-code.md §Sprout Method）
**坏味道来源**：诊断 #7（不允许在 calculate 内堆 if）
**目的**：把"按地区折扣"做成一个**完全独立、有完整测试、不依赖 calculate 内部状态**的新方法。这是本次任务的**核心动作**。

**关键警示**：
> **绝不在 `calculate(...)` 方法体里直接加 `if ("BEIJING".equals(region)) ...`**。
> Sprout Method 的精髓 = 新代码与旧代码物理隔离，旧代码"先冻结、留待重构"。

**影响文件**：
- 修改：`DiscountCalculator.java`（仅**新增**一个 package-private 方法，calculate 暂不调用）
- 新增：`DiscountCalculatorRegionDiscountTest.java`（TDD 编写）

**前置条件**：
- [x] 步骤 #2 测试全绿

**Before**：`DiscountCalculator` 中没有任何地区折扣相关代码。

**After**（仅萌芽方法，calculate 本身这一步**不动**）
```java
public class DiscountCalculator {
    // ... 原有内容不变 ...

    /**
     * Sprout Method：独立的地区折扣计算。
     * 不读外部依赖、不写日志、纯函数 — 100% 可单元测试。
     */
    BigDecimal applyRegionDiscount(BigDecimal currentDiscount, String region) {
        if (currentDiscount == null) return BigDecimal.ZERO;
        if (region == null) return currentDiscount;
        switch (region) {
            case "BEIJING":   return currentDiscount.multiply(new BigDecimal("1.10"));
            case "SHANGHAI":  return currentDiscount.multiply(new BigDecimal("1.08"));
            case "REMOTE":    return currentDiscount.multiply(new BigDecimal("0.90"));
            default:          return currentDiscount;
        }
    }
}
```

**机械化步骤**
1. 用 TDD 先写测试（红 → 绿 → 重构）：
   - `regionNull_returnsSameDiscount`
   - `beijing_multiplies1_10`
   - `shanghai_multiplies1_08`
   - `remote_multiplies0_90`
   - `unknownRegion_returnsSameDiscount`
   - `nullDiscount_returnsZero`
2. 在 `DiscountCalculator` 末尾追加 `applyRegionDiscount` 方法。**不在 calculate 中调用它。**
3. 编译 + 跑新测试全绿。
4. 步骤 #2 的 Characterization 测试**必须仍然全绿**（验证没有意外触发旧路径）。
5. commit：`feat(discount): sprout regional discount calculation (not yet wired)`。

**验证**：
```bash
mvn test
# 期望：所有 characterization 测试 + 6 条 region 测试全绿
```

**回滚策略**：单 commit，`git revert <hash>`。即使 revert，calculate 内部行为完全不受影响。

**后续衔接**：步骤 #4 才把萌芽方法接入主流程。

---

## 重构步骤 #4：在 calculate 单点接入萌芽方法

**手法**：方法重载（Overload）保持旧契约 + 单点插入新方法调用
**目的**：把 #3 的萌芽方法接入主流程，**对 calculate 做最小、可逐字核对的修改**（只增 1 行）。

**前置条件**：
- [x] 步骤 #2 + #3 全绿
- [ ] 用户在路线图 §待确认 #3 选择"重载兼容"还是"破坏性签名变更"。下面按**重载兼容**给出。

**Before**
```java
public BigDecimal calculate(String customerId, BigDecimal amount, String productCategory) {
    // ... 原逻辑 ...
    if (discount.compareTo(maxDiscount) > 0) discount = maxDiscount;
    logger.log("discount calculated: " + discount);
    return discount;
}
```

**After**
```java
// 旧契约保留 — 老调用方零改动
public BigDecimal calculate(String customerId, BigDecimal amount, String productCategory) {
    return calculate(customerId, amount, productCategory, null);
}

// 新契约 — 接受 region
public BigDecimal calculate(String customerId, BigDecimal amount, String productCategory, String region) {
    // ... 原逻辑 100% 不动 ...
    if (discount.compareTo(maxDiscount) > 0) discount = maxDiscount;
    discount = applyRegionDiscount(discount, region);   // ← 唯一新增的一行
    logger.log("discount calculated: " + discount);
    return discount;
}
```

**机械化步骤**
1. 重命名/复制原 calculate 为 4 参数版本（IDE Refactor → Change Signature，追加 `String region`）。
2. 在 4 参数版本的"maxDiscount 截断"之后、log 之前，插入唯一一行：
   `discount = applyRegionDiscount(discount, region);`
3. 新增 3 参数重载，委派到 4 参数版本传 `region = null`。
4. 跑全量测试：
   - Characterization 测试（3 参数路径）：全绿（因为 region=null → applyRegionDiscount 返回原值）
   - Region 测试：全绿
5. 新增 4-6 条端到端测试：覆盖（level × category × region）组合，验证 region 折扣**只在末段**生效。
6. commit：`feat(discount): apply regional discount in calculate (backward compatible)`。

**验证**：
```bash
mvn test
# 期望：Characterization 测试零失败 + 新 region 端到端测试全绿
```

**回滚策略**：单 commit revert。旧 3 参数调用方在 revert 前后**行为完全一致**（因为新代码路径仅在传 region 非 null 时激活）。

**后续衔接**：
- 旧 calculate 内部依然是长方法、含魔法数、有类型码 — **不在本次任务中处理**。
- 等团队后续有空且测试覆盖更稳后，再启动路线图步骤 #5-#7（Enum / Constant / Extract Method）。
- 任何下游调用方迁移到 4 参数版本是**渐进的**，不强制同步。

---

## 步骤完成核对清单

- [ ] 4 个 commit 各自独立、各自可 revert
- [ ] 全程**未修改 calculate 内部业务计算逻辑**（仅依赖调用方式变更 + 末段加一行）
- [ ] 新功能"按地区折扣"以 Sprout Method 形式落地，独立可测
- [ ] 旧的硬编码 `new DbConnection` 等仅被**包装**进生产实现类，原始字面量未改动
- [ ] 旧 calculate 3 参数调用方零改动（重载兼容）
