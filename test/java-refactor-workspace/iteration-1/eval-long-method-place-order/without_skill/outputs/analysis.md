# OrderService.placeOrder 重构方案

这个方法是非常典型的"事务脚本越长越胖"的样子——校验、查询、计算、落库、发通知全部塞在一个方法里。下面我从几个维度梳理一下问题，并给出一个分阶段的重构路线，可以小步前进、每一步都能跑测试。

## 一、当前代码的主要问题

1. **Long Method（长方法）**：单方法 90+ 行，做了 8 件事——参数校验、查客户、库存校验、金额计算、运费计算、优惠券、落库、发邮件。
2. **Feature Envy / 业务规则散落**：运费、优惠券、最终金额计算都是纯业务规则，但被埋在 Service 流程代码里，无法独立测试。
3. **Duplicate Loops（重复循环）**：items 被遍历了 4 次，productMapper.selectById 重复调用 3 次，是 N+1 查询雏形。
4. **Data Clump（数据泥团）**：province/city/district/detail 应抽 Address 值对象；itemsTotal/shipping/discount/finalAmount 应封装 OrderAmount。
5. **Primitive Obsession**：status=0、coupon.type==1/2、customer.status!=1 这种魔法数字应改成 enum。
6. **Hard-coded `new`**：new SmtpEmailSender() 在方法里直接 new，导致这条分支无法 mock。
7. **副作用与主流程混杂**：发邮件失败被吞 catch，难以扩展重试或事务消息。
8. **缺事务边界**：写 order、order_item、扣库存、标记 coupon，看不到 @Transactional。
9. **并发/幂等隐患**：markUsed 与 decreaseStock 无并发控制。
10. **测试不足**：30% 覆盖率，优惠券、VIP 折扣无用例——重构最大阻碍。

## 二、诊断报告

| 坏味道 | 位置 | 严重度 | 推荐手法 | 工作量 | 依赖前置 |
|---|---|---|---|---|---|
| Long Method | placeOrder 整体 | 高 | Extract Method / Class | M | 先补特征化测试 |
| Data Clump（地址） | addr 四字段 | 中 | Introduce Parameter Object → Address VO | S | - |
| Data Clump（金额） | itemsTotal/shipping/discount/finalAmount | 中 | OrderAmount VO | S | 抽出金额计算后做 |
| 重复循环 + N+1 | 4 次遍历 items | 高 | 批量加载 + 缓存 | S | 先补测试 |
| 魔法数 | status / coupon.type / customer.status | 中 | Replace Magic Number with Enum | S | 影响范围广 |
| 硬编码 new SmtpEmailSender | 发邮件分支 | 高 | Extract Interface + 构造器注入 | S | - |
| 缺事务边界 | 整方法 | 高 | @Transactional | XS | 确认容器内调用 |
| 并发/幂等 | markUsed / decreaseStock | 高 | 乐观锁 / 唯一约束 | M | 单独需求 |
| 副作用耦合（邮件） | 方法末尾 | 中 | Extract Method + 事件发布 | S | 接口抽出后做 |
| 测试覆盖不足 | 整方法 | 高 | Characterization Test | M | **必须最先做** |

## 三、重构路线图

**Step 0 对齐范围**：范围是否仅 placeOrder？HTTP 契约是否必须保持？是否允许引入 @Transactional / ApplicationEventPublisher？邮件可否异步？成本预算？

**Step 1 补特征化测试**（必须最先做）：覆盖 VIP 运费打折、北京/上海加价、超重运费、固定额优惠券、百分比优惠券、最低消费门槛、优惠券过期、库存不足、商品不存在、客户禁用、地址缺字段、负值截 0。目标 ≥80%。

**Step 2 抽 Address 值对象** → 详见下方
**Step 3 抽 EmailSender 接口** → 详见下方
**Step 4 Extract Method**:8 段切 8 个私有方法。
**Step 5 合并循环 + 一次性加载 Product**:消除 N+1。
**Step 6 Extract Class**:ShippingCalculator / CouponApplier。
**Step 7 OrderAmount VO**:聚合金额，封装负数截 0。
**Step 8 事务与副作用解耦**:@Transactional + OrderPlacedEvent + @TransactionalEventListener(AFTER_COMMIT)。
**Step 9 魔法数 → enum**:OrderStatus / CustomerStatus / CouponType。

## 四、详细执行

### Step 2 引入 Address 值对象

Before：方法里四个 setter + 四字段判空。
After：`public record Address(String province, String city, String district, String detail) { public Address { if (...) throw new IllegalArgumentException("address fields"); } }`，placeOrder 内构造一次即可。

机械化步骤：建 record → 紧接 addr!=null 后构造 → 跑测试 → 后续可推到 Order 实体。
测试命令：`./mvnw test -Dtest=OrderServiceTest`。
回滚：单 commit，git revert。
风险：AddressRequest 来自 HTTP 时不要破坏外部契约。

### Step 3 抽 EmailSender 接口 + 构造器注入

Before：`new SmtpEmailSender().send(...)`。
After：`interface EmailSender { void send(String to, String subject); }`，SmtpEmailSender 实现并 @Component，OrderService 改构造器注入 final 字段。

机械化步骤：建接口 → 现有类 implements → OrderService 加 final 字段 + 构造器 → 替换调用点 → 单测 @Mock EmailSender 加两个用例（验证调用 / 验证异常被吞）。
测试命令：`./mvnw test -Dtest=OrderServiceTest`。
回滚：单 commit revert。
风险：原字段注入要改构造器注入，搜一遍 new OrderService() 调用点；多实现时 @Primary。

## 五、关键提醒

1. 不要先重构再补测试——Feathers《Working Effectively with Legacy Code》Characterization Test 标准场景。
2. 每步小提交、可独立回滚，diff > 200 行就停下来再切。
3. 不要顺手改行为；运费规则不合理另立 issue。
4. 并发与幂等单独立项，不混进本次重构。

需要我接下来 (A) Step 1 测试用例清单 / (B) Step 4-5 详细执行 / (C) Step 8 事务边界评估？告诉我优先级即可。
