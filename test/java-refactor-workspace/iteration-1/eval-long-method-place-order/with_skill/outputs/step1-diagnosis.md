# Step 1 诊断报告：OrderService.placeOrder

## Step 0 上下文回顾（用户已提供，确认无误）

| 维度 | 内容 |
|------|------|
| 范围 | `OrderService.placeOrder`（单方法，约 90 行；允许在同类内拆出私有方法 / 同包内新增辅助类） |
| 测试覆盖 | `OrderServiceTest` 行覆盖约 30%；**优惠券分支与 VIP 折扣分支无用例覆盖** |
| API 变更 | 公有方法 `placeOrder` 签名暂视为不可变（用户未明确允许变更）；私有结构可拆；DB 表结构不动 |
| 技术栈 | Java 17 / Spring Boot 3.x / MyBatis（含 `customerMapper`、`productMapper`、`inventoryMapper`、`couponMapper`、`orderMapper`、`orderItemMapper`） |
| 风险标记 | **高**：核心路径无完整测试且含 SMTP I/O 副作用与 DB 写副作用 |

> ⚠️ **风险提示**：本次重构范围内测试覆盖不足（行覆盖 ≈ 30%，且优惠券与 VIP 路径完全无用例）。路线图首位将插入"特征化测试"步骤。请勿跳过此步骤直接重构——否则优惠券折扣类型 1/2 分支、北京/上海地区运费上浮、VIP 运费 8 折等隐式行为一旦回归无测试可发现。

---

## 重构诊断报告

**扫描范围**：`OrderService.placeOrder(String, List<ItemRequest>, AddressRequest, boolean, String)`（约 90 行，单方法）
**Java 版本**：17 | **框架**：Spring Boot 3.x / MyBatis | **测试覆盖**：行覆盖 ≈ 30%（优惠券/VIP 分支 0 覆盖）
**扫描时间**：2026-05-19

### 问题清单

| # | 坏味道（Java 名） | 全局规则映射 | 位置 | 严重度 | 推荐手法 | 估算工作量 | 依赖前置 |
|---|------------------|--------------|------|--------|----------|------------|----------|
| 1 | 长方法 `placeOrder` | 晦涩性 / 不必要复杂性 | 整方法体（≈ 90 行，承担 7 个职责：参数校验 / 客户校验 / 库存校验 / 计价 / 运费 / 优惠券 / 落库 / 邮件） | **高** | Extract Method × N + Introduce Parameter Object | 1.5h | 需先补特征化测试（#9） |
| 2 | 数据泥团 `province/city/district/detail` | 数据泥团 | `AddressRequest` 4 字段被整体使用；`Order` 中再次拆为 4 个字段 | **高** | Introduce Parameter Object / Extract Class（值对象 `ShippingAddress`） | 30m | 无 |
| 3 | 硬编码 `new SmtpEmailSender()` | 僵化 / 脆弱性 | 邮件发送处 | **高** | Extract Interface `EmailSender` + 构造器注入（Spring `@Service`） | 30m | 无（但建议与 #9 同步） |
| 4 | 重复遍历 `items` 三次（库存 / 计价 / 运费内重复 `productMapper.selectById`） | 冗余 / 性能隐患（N+1 雏形） | 库存循环 / 金额循环 / 运费循环 | **高** | Replace Temp with Query + 一次性加载 `Map<String, Product>` | 45m | 依赖 #1 已拆出方法 |
| 5 | 魔法值散布 | 不必要复杂性 | `customer.getStatus() != 1`、`coupon.getStatus() != 1`、`coupon.getType() == 1/2`、`order.setStatus(0)`、运费 `5 / 2.5 / 10 / 0.8 / 1.2`、北京/上海字符串字面量 | **中** | Replace Magic Number with Symbolic Constant / Enum；将 `couponType`、`customerStatus`、`orderStatus` 改 enum | 1h | 建议与 #1、#7 协同 |
| 6 | 霰弹式修改风险：运费规则三段（重量 / VIP / 地区）耦合在同一表达式 | 脆弱性 | 运费计算段 | **中** | Extract Method 链：`shippingByWeight` → `applyVipDiscount` → `applyRegionSurcharge`；远期可演化为 `ShippingPolicy` 链 | 30m | 依赖 #1 |
| 7 | 类型码（int 状态码 / int couponType） | 晦涩性 | `customer.getStatus()`、`coupon.getStatus()`、`coupon.getType()`、`order.setStatus(0)` | **中** | Replace Type Code with Enum（先内部 enum，DB 列保持 int） | 1h | 与 #5 合并 |
| 8 | 异常吞没 + 副作用越界（邮件发送失败仅 log，但事务边界外执行） | 脆弱性 | 邮件 try/catch 段 | **中** | Move to ApplicationEventPublisher + `@TransactionalEventListener(AFTER_COMMIT)` | 1h | 依赖 #3 |
| 9 | 缺少特征化测试 | （元问题，方法学） | 整方法 | **高（前置）** | Characterization Test（参见 `references/legacy-code.md` §特征化测试） | 1.5h | 无 |
| 10 | 贫血模型 `Order`（Service 直接 `setXxx`） | 晦涩性 | `order.setItemsAmount(...)` 等 13 行 setter 链 | 低 | Move Method / 静态工厂 `Order.create(...)` | 1h | 远期 DDD 化时再做 |
| 11 | 不必要临时变量 `stockMap`（写入但从未读取） | 冗余 | 库存校验段 | 低 | Remove Dead Code | 5m | 无 |
| 12 | 长参数列（5 个参数，含 boolean flag `vip`） | 数据泥团 / 晦涩性 | `placeOrder` 签名 | 低 | Introduce Parameter Object `PlaceOrderCommand`（需 API 变更许可） | 30m | **公有 API**：暂不动 |

### 总体观察

1. **核心矛盾不是"代码烂"，是"测试网洞"**：优惠券与 VIP 两条最复杂的折扣路径完全没有用例。先补测再重构是不可商量的前置条件。
2. **`placeOrder` 是典型的"事务脚本"**：7 个职责线性堆叠。当前阶段不建议跳到 DDD 充血模型（问题 #10），先用 Extract Method 把脊柱拉直，让方法体降到 20 行以内即可解锁"加新功能不敢动"的痛点。
3. **问题 #4 既是冗余也是性能隐患**：`productMapper.selectById` 在同一次下单里被调用 3N 次。重构后顺手解掉 N+1 雏形，收益高、风险低。
4. **邮件副作用（问题 #3 + #8）是隐藏雷**：现在 `new SmtpEmailSender()` 在 DB 写入后同步执行，一旦 SMTP 慢/挂会拖死整个下单事务。建议改异步事件，但**不在第一轮重构内强推**，列为路线图末尾的"加分项"。
5. **问题 #12（长参数列）涉及公有 API**，按 Step 0 约定**暂不动**，等用户明确许可后再排期。

### 待用户确认

1. 是否同意先补特征化测试（问题 #9，约 1.5h），再开始任何结构性改动？
2. 是否允许新增 `ShippingAddress` 值对象（问题 #2）作为同包内的 record？（不影响 `AddressRequest` DTO 与 DB 字段）
3. 邮件发送（问题 #3 + #8）的处理方式：**A. 仅做接口抽取（最小改动）** / **B. 改 Spring 事件 + AFTER_COMMIT 异步**？默认推荐 A。
4. 问题 #10（贫血模型转充血）当前不建议立刻做，留到下次"领域规则有变更"时一并评估，是否同意搁置？

---

继续 Step 2 路线图生成吗？还是先针对某一项（如问题 #1 长方法）展开 Step 3 拿到具体改法？
