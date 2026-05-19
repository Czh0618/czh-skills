# 输出模板

本文档提供 Step 1 诊断报告、Step 2 重构路线图、Step 3 重构步骤的标准 Markdown 模板。直接使用这些模板可以确保输出结构稳定、用户审阅效率高。

---

## §诊断报告模板（Step 1 产出）

```markdown
## 重构诊断报告

**扫描范围**：`com.example.order.OrderService`（420 行 / 18 方法）
**Java 版本**：17 | **框架**：Spring Boot 3.x | **测试覆盖**：行覆盖 32%（OrderServiceTest）
**扫描时间**：2026-05-19

### 问题清单

| # | 坏味道（Java 名）| 全局规则映射 | 位置 | 严重度 | 推荐手法 | 估算工作量 | 依赖前置 |
|---|----------------|------------|------|-------|---------|----------|---------|
| 1 | 长方法 `placeOrder` | 晦涩性/不必要复杂性 | L88-L210（123 行） | 高 | Extract Method + Introduce Parameter Object | 1h | 需先补特征化测试 |
| 2 | 上帝类 `OrderService` | 僵化 | 整体 | 高 | Extract Class（拆为 Pricing/Inventory/Notify 3 个 Service） | 4h | 依赖 #1 |
| 3 | 霰弹式修改：折扣字段 | 冗余 | `Order.java` / `OrderDTO.java` / `OrderVO.java` 共 4 处 | 中 | Move Field + Extract Class | 2h | - |
| 4 | 贫血模型 `Order` | 晦涩性 | `Order.java` | 中 | Move Method（从 Service 搬入 Order） | 3h | 需评估领域模型 |
| 5 | 数据泥团：收件人三件套 | 数据泥团 | 共 6 处使用 | 低 | Introduce Parameter Object `ShippingAddress` | 30m | - |

### 总体观察

- 测试覆盖偏低，建议先对 `placeOrder` 路径做特征化测试再动刀（参见 `references/legacy-code.md` §特征化测试）
- 问题 #2 是问题 #1 的放大版，建议先做 #1（小步），再评估是否需要 #2（大步）
- 问题 #5 收益低、风险低，可作为"顺手清理"放到任何一次相关改动里

### 待用户确认

1. 是否允许新增 `ShippingAddress` 值对象（影响 6 处调用）？
2. 是否接受 `OrderService` 拆分后内部注入点变化（不破坏 API，但 Spring 上下文里多 2 个 Bean）？
3. 是否同意先补特征化测试再重构？

---

继续 Step 2 路线图生成吗？还是先针对某一项展开 Step 3 拿到具体改法？
```

### 字段填写说明

| 字段 | 填写要点 |
|------|---------|
| 扫描范围 | 具体到包/类，注明行数与方法数 |
| 测试覆盖 | 必须有具体数字（覆盖率工具的实际数据），不可写"较低""不全" |
| 坏味道 | 用 `smells-catalog.md` 中的标准命名 |
| 全局规则映射 | 引用 7 种通用坏味道之一 |
| 位置 | 精确到行号或文件，多处时枚举 |
| 严重度 | 必须是"高/中/低"三档之一，结合频率判定 |
| 推荐手法 | 引用 `refactoring-techniques.md` 中的标准手法名 |
| 估算工作量 | 用绝对时间（30m / 1h / 4h / 1d），不用"小/中/大" |
| 依赖前置 | 必须显式列出，"无"也写出来 |
| 待用户确认 | 1-3 个关键决策点，避免无确认决策项 |

---

## §重构路线图模板（Step 2 产出）

```markdown
## 重构路线图

基于诊断报告，按 **收益 - 风险 - 成本/2** 综合优先级排序。详细评分规则见 `references/decision-matrix.md`。

### 推荐顺序

| 步骤 | 手法 | 对应诊断项 | 收益 | 风险 | 成本 | 优先级 | 备注 |
|-----|-----|----------|-----|-----|-----|-------|-----|
| 1 | 补 `placeOrder` 特征化测试 | #1 前置 | 3 | 1 | 1 | **高** | 后续所有改动的安全网 |
| 2 | Extract Method `calculateShipping` | #1 | 4 | 1 | 1 | **高** | 步骤 1 完成后即可做 |
| 3 | Introduce Parameter Object `ShippingAddress` | #5 + #1 | 3 | 1 | 1 | **高** | 与步骤 2 顺道做 |
| 4 | Extract Method `validateOrderRequest` | #1 | 3 | 1 | 1 | **高** | 与步骤 2 同类型 |
| 5 | Extract Class `PricingService` | #2 | 5 | 3 | 3 | 中 | 依赖步骤 2-4 |
| 6 | Move Method（`Order.calculateAmount`）| #4 | 4 | 2 | 2 | 中 | 依赖步骤 5 |

### 不推荐近期做

| 诊断项 | 不推荐原因 | 重新评估时机 |
|-------|----------|-----------|
| #3 折扣字段散弹式修改 | 涉及 4 个文件，需协调前端 VO 与 ORM；当前 ROI 偏低 | 下次需要新增折扣字段时一并做 |

### 进度建议

- **本次会话内可完成**：步骤 1-4（合计约 3 小时）
- **下次专门排期**：步骤 5-6（半天工作量）
- **暂不动**：诊断 #3

### 待用户确认

1. 是否同意此顺序？是否要调整某项的优先级？
2. 步骤 5 拆分后 `OrderService` 会变薄，是否同意新增 `PricingService` Bean？
3. 是否需要把"步骤 1-4 完成"作为一个独立 PR 提交，"步骤 5-6"作为另一个 PR？

---

继续 Step 3 展开具体步骤吗？告诉我从哪一步开始（或一次性全部展开）。
```

### 字段填写说明

- **收益/风险/成本**：1-5 评分，详见 `decision-matrix.md`
- **优先级**：根据综合分自动分档为高/中/低
- **进度建议**：必须给出"本次完成"与"下次排期"的区分，便于用户安排
- **不推荐近期做**：必须列出，并给出"重新评估时机"，让用户知道这些被记录但暂搁置

---

## §重构步骤模板（Step 3 产出）

```markdown
## 重构步骤 #2：将运费计算从 placeOrder 提取为 calculateShipping

**手法**：Extract Method（`refactoring-techniques.md` §3.1）
**坏味道来源**：诊断 #1（长方法 placeOrder）
**对应路线图**：步骤 2

### 影响范围

- **修改文件**：`com/example/order/OrderService.java`（新增私有方法、替换调用点）
- **新增文件**：无
- **删除文件**：无
- **API 变更**：无（`placeOrder` 公开签名保持不变）
- **数据库变更**：无

### 前置条件

- [x] 已有 `OrderServiceTest.placeOrder_should_*` 5 个用例（行覆盖 87%）
- [x] Step 0 已确认范围限定为 `OrderService` 单文件
- [ ] 若覆盖不足，先做步骤 1：特征化测试

### Before

```java
// OrderService.java L120-L145，placeOrder 方法内
double weight = items.stream()
    .mapToDouble(Item::getWeight)
    .sum();
double shipping;
if (weight > 5) {
    shipping = weight * 2.5;
} else {
    shipping = 10;
}
if (order.isVip()) {
    shipping *= 0.8;
}
```

### After

```java
// placeOrder 方法内
double shipping = calculateShipping(items, order.isVip());

// OrderService 新增私有方法
private double calculateShipping(List<Item> items, boolean vip) {
    double weight = items.stream().mapToDouble(Item::getWeight).sum();
    double shipping = weight > 5 ? weight * 2.5 : BASE_SHIPPING;
    return vip ? shipping * VIP_DISCOUNT : shipping;
}
private static final double BASE_SHIPPING = 10;
private static final double VIP_DISCOUNT = 0.8;
```

### 机械化步骤（Fowler mechanics）

1. 在 `OrderService` 末尾新建 `calculateShipping(List<Item> items, boolean vip)`，方法体为空
2. 复制 L120-L145 进新方法，让其编译通过（注意 `weight`、`shipping` 变量改为局部）
3. 把魔法数 `10` 和 `0.8` 提取为类常量 `BASE_SHIPPING`、`VIP_DISCOUNT`
4. 编译
5. 在 `placeOrder` 中把 L120-L145 替换为 `double shipping = calculateShipping(items, order.isVip());`
6. 编译

### 验证

```bash
mvn -pl order test -Dtest=OrderServiceTest
```

期望：所有 5 个用例绿。重点确认：
- `placeOrder_vip_should_apply_shipping_discount` 用例（验证 VIP 折扣）
- `placeOrder_heavy_should_calculate_by_weight` 用例（验证重量阶梯）

### 回滚策略

- **单 commit**：本步骤所有改动应在单个 commit 内
- **回滚命令**：`git revert <hash>`
- **副作用**：无（纯内部重构，无 DB / 外部 API / 消息队列变更）

### 后续衔接

- 完成本步骤后 → 启用步骤 #3（`Introduce Parameter Object ShippingAddress`）
- 不建议跳到步骤 #5 → 它依赖 #2、#3、#4 全部完成
```

### 字段填写说明

| 字段 | 是否必填 | 说明 |
|------|---------|------|
| 手法 | 必填 | 引用标准手法名 + reference 锚点 |
| 影响范围 | 必填 | 显式列出所有变更，"无"也写出 |
| 前置条件 | 必填 | checkbox 形式，已满足打 [x]，未满足打 [ ] |
| Before | 必填 | 5-15 行最相关代码，不贴完整文件 |
| After | 必填 | 与 Before 等长，对照阅读 |
| 机械化步骤 | 必填 | 编号步骤，每步可独立操作并编译 |
| 验证 | 必填 | 具体的测试命令 + 期望结果 |
| 回滚策略 | 必填 | 必须说明 commit 粒度与回滚命令 |
| 后续衔接 | 可选 | 仅当本步骤是多步链条的一环时填 |

---

## §用户确认话术

每个 Step 结束时主动引导，但不自动进入下一步。

**Step 0 → Step 1**：
> "上下文已明确。我现在开始 Step 1 诊断（扫描坏味道）。如果你只想做 [某个具体方面] 的诊断，告诉我，我可以限定扫描范围。"

**Step 1 → Step 2**：
> "诊断完毕。这份清单显示了所有坏味道。下一步我可以帮你把它们按 '收益 × 风险 × 成本' 排序，
> 形成一份可执行的重构路线图。继续 Step 2 吗？或者你想先针对某一项展开 Step 3 拿到具体改法？"

**Step 2 → Step 3**：
> "路线图已就绪。如果你同意这个顺序，告诉我从哪一步开始（如 '步骤 2'），我会给出该步骤的详细改法
> （before/after + 机械化步骤 + 测试命令 + 回滚策略）。也可以让我一次性把所有步骤都展开。"

**Step 3 完成（用户已执行某步骤）**：
> "步骤 #N 完成。建议跑一次完整测试套件确认无回归。
> 如果一切正常，是否继续步骤 #N+1（手法名）？或者你想先返回 Step 1 重新扫描，看看是否有新发现的坏味道？"

---

## §特殊场景输出微调

### 无测试场景（Step 0 探明）

诊断报告与路线图前**额外加一段警告**：

```markdown
> ⚠️ **风险提示**：本次重构范围内测试覆盖不足（行覆盖 < 50%）。
> 我已在路线图首位加入"特征化测试"步骤。请勿跳过此步骤直接重构——
> 否则一旦行为变化无测试可发现，回滚成本会显著上升。
```

### 跨模块场景

在路线图后加：

```markdown
> ⚠️ **跨模块提示**：本次重构涉及 `order` 与 `inventory` 两个模块。
> 建议拆为 2 个 PR：先合 order 模块的内部重构（步骤 1-4），
> 再合涉及 inventory 协作的步骤（5-6）。便于 review 与回滚。
```

### Spring `@Transactional` 边界改动

在影响范围中**显式列出事务影响**：

```markdown
### 影响范围
- **修改文件**：`OrderService.java`
- **事务边界变化**：原 `placeOrder` 的 `@Transactional` 现在覆盖了新拆出的 `PricingService.calculate`。
  由于 `PricingService` 也标 `@Transactional(propagation = REQUIRED)`，传播行为不变。
- **建议验证**：单元测试 + 一次手工触发并观察事务日志
```

---

## §诊断报告输出长度参考

| 代码规模 | 诊断报告建议长度 | 问题清单条数 |
|---------|---------------|-----------|
| 单方法（< 100 行） | 30 行内 | 1-3 |
| 单类（< 500 行） | 50 行内 | 3-7 |
| 单模块（多类） | 80 行内 | 5-12 |
| 跨模块 | 100 行内 | 8-15 |

**超过 15 条坏味道时**：合并相同类型（如 4 个"长方法"合并为一条，列出位置清单），避免清单过长丢失重点。

---

## §引用约定

- 引用 reference 文件：`references/xxx.md §章节名`
- 引用具体行号：`L88-L210`（123 行）`
- 引用具体类/方法：使用反引号 `OrderService.placeOrder()`
- 引用全局规则：`~/.claude/rules/code-quality.md` 第 N 条
