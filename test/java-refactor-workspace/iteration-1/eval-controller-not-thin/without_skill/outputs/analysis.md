# OrderController Review 分析

> Scope: Spring Boot `@RestController` 直接注入 Mapper，承担参数校验、业务计算、持久化编排与响应组装。
> Constraint: 仅做 review 与建议，不改用户代码 (no code edits)。HTTP 契约保持不变 (preserve HTTP contract)。

## 1. 诊断总览 / Diagnosis Summary

| # | 坏味道 / Code Smell | 严重度 | 位置 | 影响 |
|---|---|---|---|---|
| 1 | Fat Controller（胖控制器/业务逻辑泄露到 Web 层） | 高 | `create()` 全方法 | Controller 承担非 HTTP 职责，难复用难测试 |
| 2 | Layer Violation（分层泄露/跨层调用） | 高 | `@Autowired OrderMapper / CustomerMapper / ProductMapper` | 绕过 Service 层，破坏分层架构 |
| 3 | Manual Validation（手写校验） | 中 | 前四个 `if` 块 | 校验散落、易遗漏、错误响应不统一 |
| 4 | Exception via Return（用返回值表达异常） | 中 | `ResponseEntity.status(404).body(...)` 多处 | 缺少集中异常处理 (`@ControllerAdvice`) |
| 5 | N+1 / Per-item Mapper Call | 中 | 循环内 `productMapper.selectById(...)` | 性能隐患 (potential N+1 query) |
| 6 | Manual DTO Mapping（手写字段拷贝） | 低-中 | 末尾构造 `OrderResponseVO` | 字段多易漏 |
| 7 | Magic Number / Type Code | 低 | `setStatus(0)`、`"DRAFT"` | 建议 `enum OrderStatus` |
| 8 | Direct `new Date()`（不可注入时间源） | 低 | `setCreatedAt(new Date())` | 难测，建议 `Clock` 或 DB 默认值 |
| 9 | Error Body Inconsistency | 低 | `Map.of("error", ...)` ad-hoc | 建议统一 `ErrorResponse` (RFC 7807) |

## 2. 推荐目标分层 / Target Layering

```
OrderController (Web 层)  → 仅做：参数绑定 + @Valid + 调用 Service + 异常→HTTP 映射
        ▼
OrderService (业务层)     → 编排：客户校验、价格计算、订单持久化、领域异常
        ▼
*Mapper (持久层)
```

辅助：`@ControllerAdvice` + `@ExceptionHandler`；`OrderAssembler` 或 MapStruct；Bean Validation 注解。

## 3. 重构路线图 / Refactoring Roadmap

顺序原则：**先建网，再拆梁** — characterization tests & exception infra first, then move logic, then polish.

| 步骤 | 动作 | 手法 | 风险 | 前置 |
|---|---|---|---|---|
| S1 | 为 `POST /api/orders` 补特征化测试（成功 + 各 4xx 分支） | Characterization Test (MockMvc) | 低 | — |
| S2 | 引入 `@ControllerAdvice` + 领域异常 | Introduce Exception Handler | 低 | S1 |
| S3 | `OrderRequest`/`OrderItemRequest` 加 Bean Validation 注解，Controller 加 `@Valid` | Replace Conditional with Annotation | 低 | S2 |
| S4 | 抽取 `OrderService.createOrder(OrderRequest)`，迁出查询/计算/落库 | Extract Class + Move Method | 中 | S1–S3 |
| S5 | Controller 仅保留：`@Valid` → service → assembler → `ResponseEntity.ok` | Inline + Slim Down | 低 | S4 |
| S6 | 引入 `OrderAssembler` 或 MapStruct | Extract Mapper | 低 | S5 |
| S7 | （可选）`productMapper.selectByIds(ids)` 批量查询消除 N+1 | Replace Loop with Batch Query | 中 | S4 |
| S8 | （可选）`Integer status` → `enum OrderStatus`；`new Date()` → `Clock` | Replace Type Code / Inject Clock | 低 | S4 |

**HTTP 契约保持**：path `POST /api/orders`、请求体 `OrderRequest`、成功响应 `OrderResponseVO`（字段不变）、错误响应保留 `{"error": "..."}` 形态。

## 4. 关键步骤详解 / Key Step Detail

### Step 4 — Extract OrderService.createOrder

Before（Controller 内）：见原代码"查客户 / 计算总价 / 落库"三段。

After（Conceptual）：
```java
// Controller
@PostMapping
public ResponseEntity<OrderResponseVO> create(@Valid @RequestBody OrderRequest req) {
    OrderCreatedResult r = orderService.createOrder(req);
    return ResponseEntity.ok(orderAssembler.toVO(r));
}

// Service
@Transactional
public OrderCreatedResult createOrder(OrderRequest req) {
    Customer customer = loadCustomerOrThrow(req.getCustomerId());
    BigDecimal total  = priceCalculator.totalOf(req.getItems());
    Order order       = orderFactory.draftOf(customer, req, total);
    orderMapper.insert(order);
    return new OrderCreatedResult(order, customer);
}
```

机械化步骤：
1. 新建 `OrderService.createOrder` 签名，方法体先 `throw new UnsupportedOperationException()`。
2. 原样剪切"查客户→计算→落库"到 Service，保持行为不变。
3. Controller 改为调用 Service，把 404/400 替换为领域异常 (`CustomerNotFoundException` 等)。
4. `@ControllerAdvice` 把领域异常映射回原 HTTP 状态码 + 原错误体形状。
5. 跑 S1 的特征化测试，确保 HTTP 输入输出完全一致。

测试命令：`./mvnw test -Dtest=OrderControllerTest`（或 Gradle 等价命令）。
回滚：单提交原子化，红条则 `git revert <commit>`。

### Step 3 — Replace Manual Validation with @Valid

```java
public class OrderRequest {
    @NotBlank private String customerId;
    @NotEmpty @Valid private List<OrderItemRequest> items;
}
public class OrderItemRequest {
    @NotBlank private String productId;
    @Min(1)   private int quantity;
}

@ControllerAdvice
class ApiExceptionHandler {
    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<?> onInvalid(MethodArgumentNotValidException ex) {
        return ResponseEntity.badRequest().body(Map.of("error", firstMessage(ex)));
    }
}
```

要点：响应体形状 `{"error": "..."}` 保持不变；校验来源由手写改为注解 + 框架。

## 5. 风险与提示 / Risks & Caveats

- **事务边界**：原 Controller 没 `@Transactional`，迁入 Service 后应显式加上。
- **异常→HTTP 映射**：`@ControllerAdvice` 必须覆盖原 400/404 全部分支，否则静默回归为 500。
- **N+1 隐患**：Step 7 之前每个订单项独立 `selectById`；SKU 多时优先批量化。
- **DTO Mapper 范围**：MapStruct 适合 >5 字段；字段少时手写 Assembler 更轻量，避免 Needless Complexity。
- **不要"先重写再说"**：没有 MockMvc 特征化测试时直接重构属高风险动作。

## 6. 验收清单 / Acceptance Checklist

- [ ] Controller 方法体 ≤ 10 行，仅做 `@Valid → service → assembler → ResponseEntity`
- [ ] Controller 不再注入任何 `*Mapper`
- [ ] 所有 4xx 路径由 `@ControllerAdvice` 集中映射
- [ ] `OrderRequest` 校验通过 Bean Validation 完成
- [ ] MockMvc 测试在重构前后输出（status + body）完全一致
- [ ] HTTP 契约（path / payload / response shape）零变更
