# Step 3 重构步骤：OrderService.placeOrder 详细执行清单

> 本文档展开 `step2-roadmap.md` 中的关键步骤。每步独立可读、可单独 commit、可 revert。Before/After 仅贴最相关 5-15 行，不展示完整文件。

## 上下文回顾

- **范围**：`OrderService.placeOrder` 单方法 + 同包辅助
- **测试覆盖**：30%（VIP / 优惠券 0 覆盖）
- **API 约束**：`placeOrder` 公有签名不可变
- **技术栈**：Java 17 / Spring Boot 3 / MyBatis

---

## 重构步骤 #1：补 placeOrder 特征化测试（安全网）

**手法**：Characterization Test（`references/legacy-code.md` §特征化测试）
**坏味道来源**：诊断 #9（缺少特征化测试）
**对应路线图**：步骤 1

### 影响范围

- **修改文件**：`src/test/java/.../OrderServiceTest.java`（新增 ≥ 8 个用例）
- **新增文件**：可选 `OrderServiceTestFixtures.java`（构建器/数据夹具）
- **删除文件**：无
- **API 变更**：无
- **数据库变更**：无（用 Mockito mock 全部 Mapper）

### 前置条件

- [x] Step 0 已确认范围与技术栈
- [x] 项目已有 Mockito / spring-boot-starter-test
- [ ] 确认是否允许新增 fixture 工具类（默认允许，同 test 包内）

### Before（现状）

```java
// OrderServiceTest 现仅覆盖最朴素 happy path
@Test
void placeOrder_shouldCreateOrder_whenInputValid() {
    // 仅一两个 case，未覆盖 VIP / 优惠券 / 地区运费 / 库存不足 / 客户禁用
    when(customerMapper.selectById("C1")).thenReturn(activeCustomer());
    // ... 仅断言 result.getOrderId() != null
}
```

### After（新增至少 8 个用例锁定当前行为）

```java
// 1. happy path（已有，保留）
// 2. customer 禁用 → IllegalStateException("customer disabled")
// 3. 库存不足 → InsufficientStockException
// 4. VIP 用户 → shipping 乘 0.8（用 BigDecimal 精确断言）
// 5. 北京收货 → shipping 乘 1.2
// 6. 重量 > 5kg → shipping = weight * 2.5；否则 = 10
// 7. 优惠券 type=1（满减）→ discount = coupon.value，且 couponMapper.markUsed 被调用一次
// 8. 优惠券 type=2（百分比）→ discount = itemsTotal * value / 100
// 9. finalAmount < 0 → 截断为 0
// 10. SMTP 抛异常 → 不影响订单成功落库（验证降级）

@Test
void placeOrder_shouldApplyVipShippingDiscount_whenVipTrue() {
    givenActiveCustomer("C1");
    givenProduct("P1", price("100"), 2.0 /*kg*/);
    givenStock("P1", 10);
    var result = service.placeOrder("C1", items("P1", 1), beijingAddr(), true, null);
    // 重量 2kg ≤ 5 → base = 10；VIP → *0.8 = 8；北京 → *1.2 = 9.6
    verify(orderMapper).insert(argThat(o -> o.getShippingAmount().compareTo(bd("9.60")) == 0));
}
```

### 机械化步骤（Feathers mechanics）

1. **不要试图理解每一行业务**：跑现有代码 + 调试器观察输入输出，把当前行为当"金标准"写下来
2. 用 `@MockBean` / `@ExtendWith(MockitoExtension.class)` mock 所有 Mapper + `SmtpEmailSender` 调用边界
3. 优先覆盖以下分支（按优先级）：
   - VIP true/false × 重量 >5 / ≤5 × 地区北京/上海/其他（共 12 组运费，可参数化为 6-8 组采样）
   - 优惠券 null / type=1 / type=2 / 已使用 / 未达 minAmount / 不存在
   - 客户不存在 / 客户禁用
   - 库存不足
4. 每个用例只断言**该路径强相关的关键字段**（不要全字段断言），减少未来重构噪声
5. 跑测试：当前实现下应全绿（如果某个用例红，说明你对原行为的理解错了，**先纠正测试再继续**）
6. 用 JaCoCo 验证：`placeOrder` 行覆盖应达到 ≥ 85%

### 验证

```bash
mvn -pl order test -Dtest=OrderServiceTest
mvn -pl order jacoco:report
# 打开 target/site/jacoco/index.html 检查 placeOrder 行覆盖
```

期望：
- 新增 ≥ 8 个用例全部绿
- `placeOrder` 方法行覆盖 ≥ 85%
- 分支覆盖 ≥ 70%

### 回滚策略

- **单 commit**：所有测试与 fixture 在一个 commit 内
- **回滚命令**：`git revert <hash>`
- **副作用**：无（纯测试新增）

### 后续衔接

- 完成后 → 步骤 #2（删除 dead code `stockMap`，热身）
- **未达 85% 行覆盖前禁止启动步骤 #3 及之后**

---

## 重构步骤 #7：将运费计算从 placeOrder 提取为 calculateShipping 三段链

**手法**：Extract Method × 3 + Replace Magic Number with Constant（`references/refactoring-techniques.md` §3.1, §9）
**坏味道来源**：诊断 #1（长方法）+ #5（魔法值）+ #6（运费三段耦合）
**对应路线图**：步骤 7

### 影响范围

- **修改文件**：`com/example/order/OrderService.java`（提取 3 个私有方法 + 4 个类常量 + 替换调用点）
- **新增文件**：无（保持单类内，未到 Extract Class 时机）
- **删除文件**：无
- **API 变更**：无（`placeOrder` 公开签名不变）
- **数据库变更**：无
- **事务边界**：无变化（所有新方法仍在原 `@Transactional` 内）

### 前置条件

- [ ] 步骤 #1 特征化测试已完成，VIP / 重量阶梯 / 地区上浮三个分支均有用例
- [ ] 步骤 #5 `loadProductsByIds` 已完成（运费循环不再重复查 product）
- [x] Step 0 确认范围 = `OrderService` 单文件

> **若 #1 或 #5 未完成，禁止启动本步骤**。理由：运费三段是用户痛点中最易踩雷的部分（VIP × 重量 × 地区 = 12 种组合），无测试保护下任何一步都可能引入回归。

### Before（约 10 行，散布在 placeOrder 中部）

```java
// L 运费段，依赖前面循环计算的 weight
double weight = 0;
for (ItemRequest item : items) {
    Product p = productMapper.selectById(item.getProductId()); // 重复查询（已由 #5 解决）
    weight += p.getWeight() * item.getQuantity();
}
BigDecimal shipping;
if (weight > 5) shipping = BigDecimal.valueOf(weight * 2.5);
else shipping = BigDecimal.valueOf(10);
if (vip) shipping = shipping.multiply(BigDecimal.valueOf(0.8));
if ("BEIJING".equals(addr.getProvince()) || "SHANGHAI".equals(addr.getProvince())) {
    shipping = shipping.multiply(BigDecimal.valueOf(1.2));
}
```

### After（placeOrder 中仅 1 行调用 + 同类内 3 个私有方法 + 4 个常量）

```java
// === placeOrder 内 ===
BigDecimal shipping = calculateShipping(items, products, address, vip);

// === OrderService 类内新增 ===
private static final BigDecimal BASE_SHIPPING       = new BigDecimal("10");
private static final BigDecimal HEAVY_WEIGHT_RATE   = new BigDecimal("2.5");
private static final double     HEAVY_WEIGHT_KG     = 5.0;
private static final BigDecimal VIP_SHIPPING_RATE   = new BigDecimal("0.8");
private static final BigDecimal METRO_SURCHARGE     = new BigDecimal("1.2");
private static final Set<String> METRO_PROVINCES    = Set.of("BEIJING", "SHANGHAI");

private BigDecimal calculateShipping(List<ItemRequest> items,
                                     Map<String, Product> products,
                                     ShippingAddress address,
                                     boolean vip) {
    BigDecimal base = shippingByWeight(items, products);
    BigDecimal afterVip = applyVipDiscount(base, vip);
    return applyRegionSurcharge(afterVip, address);
}

private BigDecimal shippingByWeight(List<ItemRequest> items, Map<String, Product> products) {
    double weight = items.stream()
            .mapToDouble(i -> products.get(i.getProductId()).getWeight() * i.getQuantity())
            .sum();
    return weight > HEAVY_WEIGHT_KG
            ? HEAVY_WEIGHT_RATE.multiply(BigDecimal.valueOf(weight))
            : BASE_SHIPPING;
}

private BigDecimal applyVipDiscount(BigDecimal shipping, boolean vip) {
    return vip ? shipping.multiply(VIP_SHIPPING_RATE) : shipping;
}

private BigDecimal applyRegionSurcharge(BigDecimal shipping, ShippingAddress address) {
    return METRO_PROVINCES.contains(address.province())
            ? shipping.multiply(METRO_SURCHARGE)
            : shipping;
}
```

### 机械化步骤（Fowler mechanics，每小步都编译 + 跑测试）

1. **抽常量**：在 `OrderService` 顶部新增 6 个常量（`BASE_SHIPPING`、`HEAVY_WEIGHT_RATE`、`HEAVY_WEIGHT_KG`、`VIP_SHIPPING_RATE`、`METRO_SURCHARGE`、`METRO_PROVINCES`），**原代码暂不替换**。编译。
2. **新建空方法 `shippingByWeight(items, products)`**，方法体先 `return BigDecimal.ZERO;`。编译。
3. 把 Before 中"计算 weight + 重量阶梯判断"的两段复制进 `shippingByWeight` 方法体。让其编译通过（注意 `weight` 改局部变量）。
4. **在 placeOrder 原位置**：把"计算 weight + 重量阶梯"两段替换为 `BigDecimal shipping = shippingByWeight(items, products);`。编译 + **跑测试**（应全绿）。**这是第 1 个独立 commit**。
5. **新建 `applyVipDiscount(shipping, vip)`**，方法体 `return shipping;`。编译。
6. 复制 `if (vip) shipping = shipping.multiply(...)` 进新方法。
7. 在 placeOrder 原位置替换为 `shipping = applyVipDiscount(shipping, vip);`。编译 + 跑测试。**第 2 个独立 commit**。
8. **新建 `applyRegionSurcharge(shipping, address)`**，重复步骤 5-7。**第 3 个独立 commit**。
9. **最后**：把 placeOrder 中 3 行替换为一行 `BigDecimal shipping = calculateShipping(items, products, address, vip);`，并新建编排方法 `calculateShipping`。编译 + 跑测试。**第 4 个独立 commit**。
10. （可选）替换硬编码字面量为常量（第 1 步抽出的）：先 `BASE_SHIPPING`，再 `HEAVY_WEIGHT_RATE` 等。每替换一个常量编译跑一次测试。

> **关键纪律**：第 4-9 步每一步**都要跑完整 `OrderServiceTest`**。不要囤积多步一起 commit，否则一旦某用例红，无法定位是哪步引入。

### 验证

```bash
# 每个机械化步骤都跑：
mvn -pl order test -Dtest=OrderServiceTest

# 最后一步额外跑：
mvn -pl order test -Dtest=OrderServiceTest#placeOrder_shouldApplyVipShippingDiscount_whenVipTrue
mvn -pl order test -Dtest=OrderServiceTest#placeOrder_shouldSurchargeShipping_whenProvinceIsBeijing
mvn -pl order test -Dtest=OrderServiceTest#placeOrder_shouldUseHeavyRate_whenWeightOver5kg
```

期望：
- 所有特征化测试用例保持绿
- `placeOrder` 方法体行数从 ≈ 90 行 降到 ≈ 60 行（本步骤贡献减少 ≈ 10 行 + 改 1 行调用）
- `shippingByWeight` / `applyVipDiscount` / `applyRegionSurcharge` 三个私有方法可被未来独立单测覆盖

### 回滚策略

- **4 个独立 commit**，每个对应一段提取
- 任一 commit 出现回归：`git revert <hash>`
- 全部回滚：按时间倒序连续 revert 4 次，或 `git reset --hard <pre-step7-hash>`（仅本地未推送时）
- **副作用**：纯内部重构，无 DB / 外部 API / 消息队列变更

### 后续衔接

- 完成本步骤 → 启用步骤 #8（`applyCoupon` 提取）
- 中期演化提示：当 `applyRegionSurcharge` 的 `METRO_PROVINCES` 规则超过 5 个省份，或重量阶梯需要超过 2 档时，应升级为 `ShippingPolicy` 策略接口 + 多实现（`Replace Conditional with Polymorphism`）。**当前不必做**。

---

## 附：步骤 #3 极简示例（Extract Method `validateRequest`）

> 提供第三个步骤作为"小步示例"，让用户感受 Extract Method 的最小操作单位。

**Before**（placeOrder 开头 6 行）：

```java
if (customerId == null || customerId.isEmpty()) throw new IllegalArgumentException("customerId");
if (items == null || items.isEmpty()) throw new IllegalArgumentException("items");
if (addr == null) throw new IllegalArgumentException("address");
if (addr.getProvince() == null || addr.getCity() == null
    || addr.getDistrict() == null || addr.getDetail() == null) {
    throw new IllegalArgumentException("address fields");
}
```

**After**：

```java
// placeOrder 第一行
validateRequest(customerId, items, addr);

// 私有方法
private void validateRequest(String customerId, List<ItemRequest> items, AddressRequest addr) {
    if (customerId == null || customerId.isEmpty()) throw new IllegalArgumentException("customerId");
    if (items == null || items.isEmpty())            throw new IllegalArgumentException("items");
    if (addr == null)                                 throw new IllegalArgumentException("address");
    if (addr.getProvince() == null || addr.getCity() == null
        || addr.getDistrict() == null || addr.getDetail() == null) {
        throw new IllegalArgumentException("address fields");
    }
}
```

**Mechanics**：1) 新建空方法 → 2) 复制 6 行 → 3) 原位置替换为方法调用 → 4) 编译 + 跑测试 → 5) commit。**总耗时 5 分钟**。

---

## 完成后引导

- 步骤 #1（特征化测试）是**所有后续步骤的安全网**。建议你先确认是否同意启动 #1。
- 步骤 #7（运费三段链）展示了"机械化 + 小步 commit"的标准节奏。你可以挑选其他步骤要求我展开（例如 #5 `loadProductsByIds`、#8 `applyCoupon`、#11 `EmailSender` 接口抽取）。
- **强烈不建议**：跳过 #1 直接做 #7。无测试保护下，运费三段任意一步出错都难以定位。
