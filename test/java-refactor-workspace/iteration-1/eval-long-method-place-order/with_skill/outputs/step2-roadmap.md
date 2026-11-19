# Step 2 重构路线图：OrderService.placeOrder

> 基于 `step1-diagnosis.md` 的 12 项坏味道清单，按 **收益 - 风险 - 成本/2** 综合优先级排序。评分规则参见 `references/decision-matrix.md`。

## 上下文回顾

| 维度 | 内容 |
|------|------|
| 范围 | `OrderService.placeOrder` 单方法 + 同包内辅助 |
| 测试覆盖 | ≈ 30%（VIP / 优惠券 0 覆盖）→ 首位必须补特征化测试 |
| API 约束 | `placeOrder` 公有签名暂不动；DB 表结构不动 |
| 技术栈 | Java 17 / Spring Boot 3 / MyBatis |

> ⚠️ **风险提示**：测试覆盖不足。路线图首位为"补特征化测试"。**禁止跳过**直接进入步骤 2。

---

## 推荐顺序

| 步骤 | 手法 | 对应诊断项 | 收益 | 风险 | 成本 | 优先级 | 备注 |
|------|------|-----------|------|------|------|--------|------|
| **1** | 补 `placeOrder` 特征化测试（覆盖 VIP / 优惠券 type1 / type2 / 北京上海地区 / 库存不足 / 客户禁用 共 ≥ 8 用例） | #9 前置 | 5 | 1 | 2 | **高** | 后续所有改动的安全网；用 MyBatis `@MockBean` + 真实分支断言 |
| **2** | 删除 dead code `stockMap`（写入未读取） | #11 | 1 | 1 | 1 | **高** | 5 分钟纯清理，热身 |
| **3** | Extract Method `validateRequest(customerId, items, addr)` | #1 | 3 | 1 | 1 | **高** | 第一刀，最安全，让方法降 12 行 |
| **4** | Introduce Parameter Object `ShippingAddress`（record） + Extract Method `validateAddress` | #2 + #1 | 4 | 1 | 1 | **高** | 收件人四件套收拢；`AddressRequest` → `ShippingAddress` 转换在入口完成 |
| **5** | Extract Method `loadProductsByIds(items)` → 返回 `Map<String, Product>` 一次性加载 | #4 + #1 | 5 | 2 | 2 | **高** | 顺手干掉 N+1 雏形；后续库存 / 计价 / 运费循环共享此 map |
| **6** | Extract Method `verifyCustomer` / `verifyStock` / `calculateItemsTotal` | #1 | 4 | 1 | 1 | **高** | 三个独立私有方法，分别 commit |
| **7** | Extract Method 链 `calculateShipping`：`shippingByWeight` → `applyVipDiscount` → `applyRegionSurcharge` + 抽魔法常量 | #1 + #5 + #6 | 4 | 2 | 2 | **高** | 让运费三段规则各自可单测；魔法值 `5 / 2.5 / 10 / 0.8 / 1.2` 提为常量 |
| **8** | Extract Method `applyCoupon(couponCode, itemsTotal)` → 返回 `Discount` record | #1 + #5 | 4 | 2 | 2 | 中 | 包含查券 / 校验 / 计算 / 标记已用；为后续策略模式留接口 |
| **9** | Replace Type Code with Enum：`CouponType {FIXED, PERCENT}`、`CustomerStatus`、`OrderStatus`（仅内部 enum，DB 仍 int） | #5 + #7 | 3 | 2 | 2 | 中 | 用 `@JsonValue` / MyBatis `TypeHandler` 桥接，DB 列不动 |
| **10** | Extract Method `persistOrder(...)` + `persistOrderItems(...)` | #1 | 3 | 1 | 1 | 中 | 让落库段独立；为远期 #10 Move Method 到 `Order.create()` 铺路 |
| **11** | Extract Interface `EmailSender` + 构造器注入；删除 `new SmtpEmailSender()` | #3 | 4 | 2 | 2 | 中 | 解锁邮件分支可测；Spring `@Service` 注入 `SmtpEmailSender implements EmailSender` |
| **12** | 邮件改 `ApplicationEventPublisher` + `@TransactionalEventListener(AFTER_COMMIT)` | #8 | 4 | 3 | 3 | 中 | 解决事务内 I/O 阻塞 + 失败回滚问题；**需用户确认是否允许引入事件** |

### 终态预览

完成步骤 1-11 后，`placeOrder` 主体预期降至 **15-20 行**，呈"流水线编排"形态：

```java
public OrderResult placeOrder(...) {
    validateRequest(customerId, items, addr);
    ShippingAddress address = ShippingAddress.from(addr);
    Customer customer = verifyCustomer(customerId);
    Map<String, Product> products = loadProductsByIds(items);
    verifyStock(items);
    BigDecimal itemsTotal = calculateItemsTotal(items, products);
    BigDecimal shipping  = calculateShipping(items, products, address, vip);
    Discount discount    = applyCoupon(couponCode, itemsTotal);
    BigDecimal finalAmt  = computeFinalAmount(itemsTotal, shipping, discount);
    Order order = persistOrder(customerId, address, itemsTotal, shipping, discount, finalAmt);
    persistOrderItems(order.getId(), items);
    emailSender.sendAsync(customer.getEmail(), "Order placed: " + order.getId());
    return new OrderResult(order.getId(), finalAmt);
}
```

---

## 不推荐近期做

| 诊断项 | 不推荐原因 | 重新评估时机 |
|--------|-----------|--------------|
| #10 贫血模型 → 充血 `Order` | 当前领域规则尚未稳定（折扣 / 运费规则随业务在变），过早 DDD 化会被业务变更反复推翻；且收益与"加新功能不敢动"的当前痛点关系弱 | 下次出现"订单状态机扩展"或"领域规则集中变更"需求时 |
| #12 长参数列改 `PlaceOrderCommand` | 涉及公有 API 改动，Step 0 未授权 | 用户明确允许后单独排期 |

---

## 进度建议

- **本次会话内可完成**：步骤 1-7（合计 ≈ 4-5 小时；其中步骤 1 占 1.5h）
- **下次会话排期**：步骤 8-11（≈ 半天）
- **需用户决策后再做**：步骤 12（邮件异步化，引入事件机制）
- **暂搁置**：诊断 #10、#12

### PR 切分建议

| PR | 包含步骤 | 主题 |
|----|---------|------|
| PR-1 | 步骤 1 | `test: add characterization tests for OrderService.placeOrder` |
| PR-2 | 步骤 2-7 | `refactor(order): extract validation / pricing / shipping methods from placeOrder` |
| PR-3 | 步骤 8-11 | `refactor(order): coupon strategy + enum status + EmailSender interface` |
| PR-4 | 步骤 12 | `refactor(order): move email side-effect to transactional event listener` |

---

## 待用户确认

1. **顺序是否同意**？特别是步骤 1（特征化测试）作为强制前置，是否接受？
2. **步骤 4 引入 `ShippingAddress` record** 是否同意？（同包内新增，不影响 DTO 与 DB）
3. **步骤 5 顺手解 N+1** 涉及一次性加载所有 Product，库存极少时是否会有遗漏？（建议先按 ID 集合一次 `selectByIds`）
4. **步骤 12 邮件异步化** 是否在本轮排期？如否则止步于步骤 11。
5. **PR 切分粒度**是否合适？是否需要把 PR-2 再拆细？

---

继续 Step 3 展开具体步骤吗？建议优先展开 **步骤 1（特征化测试）** 与 **步骤 7（运费 Extract Method 链）**，前者是安全网，后者是用户最痛的"加新功能不敢动"的核心解法。
