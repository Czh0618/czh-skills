# Step 2：重构路线图（Roadmap）

## 排序原则回顾

1. **先安全网、后重构**：Controller 是 HTTP 边界，测试覆盖未明确 → 第 0 步先补 MockMvc 特征化测试，固化当前契约。
2. **先内部、后边界**：保持 HTTP 契约（路径 / 请求体 / 响应 JSON / 状态码）不变是**硬约束**，所有步骤围绕"对外行为零变化"展开。
3. **先解耦、后清理**：先把业务从 Controller 抽到 Service（解耦分层），再做 `@Valid` 与 `@ControllerAdvice` 的声明化替换（清理冗余），最后是 Mapper 抽取与 enum 化（清理细节）。
4. **每步可独立 commit/revert**。

## 推荐顺序

| 步骤 | 手法 | 对应诊断项 | 收益 | 风险 | 成本 | 优先级 | 备注 |
|-----|------|----------|------|------|------|------|------|
| **0** | **补 MockMvc 特征化测试**（覆盖 happy path + 5 类错误：body 缺失 / customerId 空 / items 空 / qty<=0 / customer 404 / product 404） | 全部前置 | 4 | 1 | 2 | **高** | 安全网，**任何业务重构前必须先完成**；记录当前精确 JSON 响应体作为断言基线 |
| **1** | **Extract Class → `OrderService`** + **Move Method** 把业务编排、Mapper 调用、落库搬入 Service；Controller 仅注入 `OrderService` | #1、#2 | 5 | 2 | 2 | **高** | 解决分层泄露；保持 Controller `create` 签名与 HTTP 契约不变；Service 抛业务异常（先在 Controller 内 catch 转响应，保留旧错误体） |
| **2** | **引入 `@Valid` + Bean Validation**：在 `OrderRequest` / `OrderItemRequest` 加 `@NotBlank` / `@NotEmpty` / `@Valid` / `@Positive`；Controller 方法参数加 `@Valid` | #3 | 4 | 2 | 1 | **高** | 删除 Controller 内 5 处手写校验；**需要**配套 `@ControllerAdvice` 处理 `MethodArgumentNotValidException` 转 400，否则响应体会变（步骤 3 兜底） |
| **3** | **引入 `@ControllerAdvice` + 自定义业务异常**：`CustomerNotFoundException` / `ProductNotFoundException`（404）、`InvalidOrderRequestException`（400，承接 Bean Validation）；Controller 内 if-return 全部删除，Service 直接抛异常 | #4、#8、#3 配套 | 5 | 3 | 2 | **高** | 风险点：错误体 JSON schema 必须与原 `{"error": "..."}` 逐字段一致，否则违反 HTTP 契约；ControllerAdvice 内手工拼装老格式即可 |
| **4** | **Extract Class → `OrderDtoMapper`**：`OrderRequest → Order` 与 `(Order, Customer) → OrderResponseVO` 两个静态/Bean 方法；可手写或 MapStruct | #5 | 3 | 1 | 1 | 中 | 与步骤 1 完成后才有意义；MapStruct 需新增依赖（需用户确认） |
| **5** | **Replace Type Code with Enum**：`OrderStatus { DRAFT, PAID, ... }`，DB 列保持 int（用 `@TableField` typeHandler 或 MyBatis enum 处理器） | #6 | 3 | 3 | 2 | 中 | 涉及持久化层适配，需评估是否触及 `OrderMapper` XML / 其他读取方；可延后到下次 sprint |
| **6** | **批量查询优化**：`productMapper.selectByIds(Set<String>)`，一次性把所有 productId 查出，循环改成 map 查找 | #7 | 4 | 2 | 2 | 中 | 性能优化，建议与 `code-performance-analyzer` 配套评估；HTTP 契约不变 |

## 三维评分说明

- **收益**：可读性 / 可测性 / 可扩展性 / 是否解锁后续改造（1-5）
- **风险**：跨模块 / 无测试 / API 变更 / 事务边界（1-5；越高越危险）
- **成本**：估算工时 × 依赖前置数量（1-5）
- **综合公式**：优先级 ≈ 收益 - 风险 - 成本/2（仅供排序参考）

## 不推荐近期做

- **统一错误响应体升级到 `{"code","message","timestamp"}`**：诱惑很大，但属于 HTTP 契约变更，需前端协同发版，不在本次"保持契约不变"的约束内。等下一次大版本一并谈。
- **把 `OrderService` 进一步拆 CQRS（OrderQueryService / OrderCommandService）**：当前 Service 还没真正建起来，谈拆分为时过早。等 Service 跑稳几个月、方法数 > 10 再评估（参考 `spring-specific.md §@Service 上帝类拆分`）。
- **把 `productMapper.selectById` 改 Redis 缓存**：性能优化的另一条路，但属于不同关注点；先完成本次重构，性能问题留 `code-performance-analyzer` 评估。

## 关键约束（贯穿所有步骤）

- **HTTP 契约 = 硬约束**：
  - 路径：`POST /api/orders` 不变
  - 请求体：`OrderRequest` 字段名、类型、嵌套结构不变（只加注解）
  - 成功响应：HTTP 200 + `OrderResponseVO` JSON 字段全集与字段名不变
  - 错误响应：HTTP 状态码（400 / 404）与 body 形态 `{"error": "..."}` 不变（包括 `"product not found: " + productId` 这种拼接文案）
- **MockMvc 测试在每一步前后都必须全绿**，作为契约不变的硬证据。
- **不引入新依赖**前先与用户确认（MapStruct、`commons-lang3` 等）。

## 待用户确认

1. 是否同意此顺序？是否要调整某步的优先级？
2. 步骤 0 的 MockMvc 测试是否由用户自行补，还是希望我在 Step 3 一并展开测试代码骨架？
3. 步骤 3 的错误体 JSON schema 必须**逐字符匹配**当前 `Map.of("error", "...")` 输出，还是允许 `error` 字段值的文案微调？
4. 步骤 4 是否允许引入 MapStruct？不允许则手写 Mapper。
5. 步骤 5 与 6 是否纳入本次 sprint？还是下次再做？

> 引用：`references/decision-matrix.md`、`references/spring-specific.md §Controller 瘦身`、`references/output-templates.md §重构路线图模板`。
