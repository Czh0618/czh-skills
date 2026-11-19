# 重构诊断报告 — DiscountCalculator

> Step 0 安全网确认：用户明确"没有单元测试，不敢动"，代码内含 `new DbConnection(...)`、`ConfigLoader.load(...)`、`Logger.log(...)` 等硬编码外部依赖。
> **风险标记：高风险（Critical / Legacy）**。Feathers 定义：无测试的代码就是 Legacy Code。
> 凡进入 Step 3 执行前，必须先插入"特征化测试（Characterization Test）+ 依赖打破（Dependency Breaking）"两个前置步骤。
> 用户提出"能不能直接在 calculate 里加几行 if 处理地区？" — **明确不建议**，理由见下表 #7。

**扫描范围**：`DiscountCalculator.calculate(String, BigDecimal, String)` 单方法
**Java 版本 / 框架**：未指定（按 Java 8+ 通用处理）
**测试覆盖**：0%（无任何单元测试）
**改动目标**：新增"按地区做不同折扣率"功能

---

## 问题清单

| #  | 坏味道（Java 名）              | 全局规则映射                  | 位置                                 | 严重度 | 推荐手法                                                                 | 工作量 | 依赖前置                  |
|----|------------------------------|------------------------------|-------------------------------------|------|------------------------------------------------------------------------|------|--------------------------|
| 0  | 无测试覆盖（Legacy Code）       | 脆弱性 / 僵化                   | 整个类                                | 高   | Characterization Test（特征化测试，legacy-code.md §特征化测试）              | 1-2h | —（一切重构的前置）           |
| 1  | 硬编码依赖 `new DbConnection`  | 僵化 / 脆弱性 / 晦涩性           | L3 `new DbConnection(\"jdbc:...\", \"root\", \"pwd\")` | 高   | Extract Interface（legacy-code.md §1）+ 构造器注入 / Parameterize Method  | 1h   | 需先有特征化测试            |
| 2  | 硬编码依赖 `ConfigLoader.load` (静态) | 僵化 / 脆弱性                  | L5 `ConfigLoader.load(\"discount.properties\")` | 高   | Encapsulate Static（legacy-code.md §5）+ 注入 `DiscountConfigProvider` | 30m  | 需先有特征化测试            |
| 3  | 硬编码依赖 `Logger.log` (静态)   | 僵化                          | L24 `Logger.log(\"...\")`            | 中   | Subclass and Override（legacy-code.md §4）或直接换 SLF4J Logger（生产改造） | 15m  | 同上                     |
| 4  | 类型码（Type Code）`customer.getLevel()` int | 晦涩性 / 脆弱性                 | L8-L13 `level == 5 / 3 / 4`         | 中   | Replace Type Code with Enum（refactoring-techniques.md §8）            | 30m  | 不影响新增地区折扣，可滞后处理   |
| 5  | 魔法数（Magic Numbers）          | 晦涩性 / 冗余                  | `0.05`, `0.8`, `1.2`, `0.5`, `5/3/4` | 中   | Replace Magic Number with Symbolic Constant（clean-code-rules.md）    | 20m  | 同上                     |
| 6  | 类型码字符串 `productCategory`    | 晦涩性                        | L17 `\"ELECTRONICS\"` / `\"FOOD\"`     | 低   | Replace Type Code with Enum                                            | 20m  | 不阻塞新功能                |
| 7  | 不必要复杂性 — calculate 内堆积分支 | 不必要复杂性 / 僵化              | 整个方法                              | 高   | **不建议**直接在原方法加 if（会进一步恶化）；改用 Sprout Method（legacy-code.md §Sprout Method） | —    | 这是本次任务的核心结论        |
| 8  | 数据泥团 — (customerId, amount, category, region) 一起出现 | 数据泥团                      | 方法签名（一旦加 region 将变 4 个参数）   | 低   | 暂不抽参数对象，等域稳定后再做                                              | —    | 滞后                     |

---

## 总体观察

1. 这是一段典型的"**遗留代码 + 硬编码依赖 + 想加新功能**"组合 — Feathers《修改代码的艺术》中的标准教科书场景。
2. **核心结论**：用户提出的"直接在 calculate 里加几行 if 处理地区"是反模式，会让无测试的复杂方法**变得更脆弱**，未来更难拆。
3. 安全路径是 Feathers 的标准三步走：**先加特征化测试（Characterization Test） → 再用 Sprout Method 把"地区折扣"做成独立可测的新方法 → 旧代码暂不动，等积累足够测试再回头重构依赖**。
4. 硬编码依赖（#1/#2/#3）是测试不能跑的根因。在特征化测试阶段，至少要把其中 1-2 个依赖通过 Extract Interface 或 Subclass and Override 打破，否则测试根本启动不了。

---

## 待用户确认

1. 是否同意"**不直接在 calculate 加 if**"的判断？（这是本次诊断的硬结论）
2. 测试框架与构建工具是什么（JUnit 4 / JUnit 5 / TestNG，Maven / Gradle）？将影响 Step 3 测试命令的写法。
3. 当前的 `DbConnection` / `ConfigLoader` / `Logger` 是项目内自有类还是第三方库？如是自有，是否允许把它们抽接口？
4. 新增"按地区折扣率"的规则明细已有吗？（如：北京 -10%、上海 -8%……）— 如尚未明确，建议先 `/req-reverse-eng` 沉淀规则，再来这里写代码。
5. 是否允许引入构造器注入（改 `DiscountCalculator` 构造函数签名）？这是打破依赖的必要前提。
