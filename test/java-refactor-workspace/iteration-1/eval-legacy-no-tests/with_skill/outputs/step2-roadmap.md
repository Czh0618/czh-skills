# 重构路线图 — DiscountCalculator

## 严正警示（务必先读）

> **不要直接在 `calculate(...)` 方法里加 if 处理地区折扣**。
>
> 理由：
> 1. **无测试**。任何对 calculate 内部逻辑的改动都无安全网验证（参考 Feathers《修改代码的艺术》：无测试的代码 = 遗留代码 = 不可信任的代码）。
> 2. **硬编码依赖**（`new DbConnection`、`ConfigLoader.load`、`Logger.log`）使方法**无法在测试中独立运行**，你既不能事先固化当前行为，也不能验证新行为。
> 3. 直接在 calculate 中堆 if 会把"晦涩性"和"不必要复杂性"同时升级，**让下一个想重构的人更不敢动**。
>
> **正确做法**：用 Feathers 的标准三步走 — 先加特征化测试 + 打破依赖（最小代价） → 再用 **Sprout Method** 把"地区折扣"作为独立可测方法萌芽出来 → 旧代码暂不重构。

---

## Feathers 推荐顺序（加测试 → 打破依赖 → 加新功能 → 旧代码留待重构）

| 步骤 | 手法                                          | 对应诊断项     | 收益 | 风险 | 成本 | 优先级 | 备注                                                                 |
|----|---------------------------------------------|------------|----|----|----|------|---------------------------------------------------------------------|
| 1  | 打破最小依赖：Extract Interface + 构造器注入（DbConnection / ConfigLoader / Logger）抽 3 个接缝接口 | #1 #2 #3   | 4  | 2  | 2  | 高   | 让 calculate **可以在测试中被实例化**；不动其内部逻辑                              |
| 2  | Characterization Test（特征化测试）— 覆盖现有 5 条分支路径（VIP / Gold / 普通 × ELECTRONICS / FOOD / 其他、含 maxDiscount 上限） | #0         | 5  | 1  | 2  | 高   | 固化"动之前的行为"，作为后续所有改动的安全网；目标覆盖**即将改动的路径**而非 100%        |
| 3  | **Sprout Method**：新增 `applyRegionDiscount(BigDecimal current, String region)` 独立方法，独立 TDD 编写 | #7（新功能）  | 5  | 1  | 1  | 高   | 新代码整洁、有测试；calculate 仅多一行调用，风险最小                                |
| 4  | 在 calculate 末尾**单点**调用 `applyRegionDiscount(discount, region)`（方法签名新增 region 参数） | —          | 4  | 2  | 1  | 高   | 唯一对旧方法的修改：插入一行新方法调用；机械化步骤可逐字核对                            |
| 5  | （滞后）Replace Type Code with Enum：`customer.getLevel()` → `CustomerLevel` | #4         | 3  | 2  | 2  | 中   | 等步骤 2 测试覆盖巩固后再做；不阻塞当前任务                                       |
| 6  | （滞后）Replace Magic Number with Constant：`0.05/0.8/1.2/0.5` 等命名常量 | #5         | 2  | 1  | 1  | 中   | 在步骤 5 之后顺手做，单 commit 风险极低                                       |
| 7  | （滞后）Extract Method：把 calculate 拆分为 `levelDiscount / categoryDiscount / capDiscount` 三段 | #7         | 4  | 2  | 2  | 中   | 拆分动作必须**有测试再做**；不在本次任务中执行                                    |

**综合优先级公式**（参考 decision-matrix.md）：收益 - 风险 - 成本/2。当前任务（新增地区折扣）**只做步骤 1-4**即可，步骤 5-7 留待后续。

---

## 不推荐近期做

- **诊断 #7 拆分 calculate（Extract Method）**：在测试覆盖未达 80% 之前不动。Sprout Method 已经把新功能隔离开了，旧代码可以"先冻结"。
- **整体重写 `DiscountCalculator`**：Feathers 明确警示，重写遗留代码会丢失**隐式的业务规则**（如 maxDiscount 上限、`level == 3 || 4` 的 Gold 判定边界）。先 Sprout，等测试积累足够再考虑。
- **诊断 #8 抽参数对象**：等新增 region 参数后，如果还要加更多上下文（如 channel、promotionId）再做。

---

## 待用户确认

1. 是否同意此 4 步顺序（先 1+2+3+4，5/6/7 滞后）？
2. 第 1 步抽接缝接口的命名是否可接受：`OrderQueryGateway`（包装 DbConnection 查 customer）、`DiscountConfigProvider`（包装 ConfigLoader）、`DiscountLogger`（包装 Logger.log）？
3. 第 4 步 `calculate` 签名将变为 `calculate(String customerId, BigDecimal amount, String productCategory, String region)`。这是**调用方可见的破坏性变更**，是否允许？如果不允许，改用**方法重载**（保留旧签名委派到新签名 region=null）作为兼容方案。
4. 是否同意"在步骤 2 测试达到稳定前，**不进行步骤 5-7 任何重构**"？

确认后我将进入 Step 3，给出步骤 1-4 的 before/after + 机械化步骤 + 测试命令 + 回滚策略。
