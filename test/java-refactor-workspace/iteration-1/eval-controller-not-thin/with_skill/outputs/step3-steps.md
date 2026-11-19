# Step 3：执行步骤生成（至少 2 步）

本文档展开路线图中的 **步骤 0（MockMvc 特征化测试）**、**步骤 1（Extract Class → OrderService）**、**步骤 2-3（@Valid + @ControllerAdvice）** 三组共 4 个原子步骤。每步可独立 commit / revert，且整个序列结束后 HTTP 契约逐字节不变。

---

## 重构步骤 #0：补 MockMvc 特征化测试（安全网）

**手法**：Characterization Test（`references/legacy-code.md §特征化测试`）
**坏味道来源**：路线图前置项（无明确测试覆盖 → 高风险）
**影响文件**：
- 新增：`OrderControllerTest.java`（`src/test/java/.../OrderControllerTest.java`）
- 修改：无
- 不变 API：全部

**前置条件**：
- [ ] 用户已确认错误响应体形态 `{"error": "..."}` 为不变契约
- [ ] 项目已引入 `spring-boot-starter-test`（Spring Boot 默认已带）

**目标**：用 MockMvc + Mockito Mock `OrderMapper` / `CustomerMapper` / `ProductMapper`，覆盖 7 类输入路径并把**当前精确响应**写成断言基线（含状态码 + JSON 字段值 + 错误 message 字符串）。

**Before**：无测试。

**After**（测试代码骨架，5-15 行核心断言）：
```java
@WebMvcTest(OrderController.class)
class OrderControllerTest {
    @Autowired MockMvc mvc;
    @MockBean OrderMapper orderMapper;
    @MockBean CustomerMapper customerMapper;
    @MockBean ProductMapper productMapper;

    @Test
    void create_happyPath_returns200_andCurrentVoShape() throws Exception {
        // given: customer 存在、product 存在、qty 合法
        // when: POST /api/orders
        // then: status 200, $.orderId 非空, $.customerName == 'Alice', $.amount == 99.00, $.status == 'DRAFT'
    }

    @Test
    void create_customerIdBlank_returns400_withErrorBody() throws Exception {
        mvc.perform(post("/api/orders").contentType(APPLICATION_JSON)
                .content("{\"items\":[{\"productId\":\"p1\",\"quantity\":1}]}"))
           .andExpect(status().isBadRequest())
           .andExpect(jsonPath("$.error").value("customerId required"));
    }
    // 其余 5 个用例：body 缺失 / items 空 / qty<=0 / customer 404 / product 404
}
```

**机械化步骤**
1. 新建 `OrderControllerTest`，标 `@WebMvcTest(OrderController.class)`
2. 为每个 Mapper 加 `@MockBean`
3. 按 7 种输入逐个写测试：happy / body 缺失 / customerId 空 / items 空/null / qty<=0 / customer 404 / product 404
4. **每个断言精确到字符串**：`jsonPath("$.error").value("customerId required")` 而非 `.exists()`，固化文案
5. `mvn -Dtest=OrderControllerTest test`，确认 7 项全绿

**验证**：`mvn test -Dtest=OrderControllerTest` → 7 个测试全绿；测试报告中无 skip。

**回滚策略**：单 commit `test: add characterization tests for OrderController#create`。`git revert <hash>` 即可移除，无生产代码影响。

**后续衔接**：完成后才能启动 #1。

---

## 重构步骤 #1：Extract Class → OrderService + Move Method

**手法**：Extract Class（`refactoring-techniques.md §7`）+ Move Method（`refactoring-techniques.md §7.1`，Spring 适配版见 `spring-specific.md §分层架构与职责泄露`）
**坏味道来源**：诊断 #1 Fat Controller、#2 分层泄露
**影响文件**：
- 新增：`OrderService.java`
- 修改：`OrderController.java`（删除 Mapper 字段 + 业务代码；改为注入 `OrderService` + 委托调用）
- 不变 API：`POST /api/orders` 路径 / 请求体 / 响应体 / 状态码

**前置条件**：
- [x] 步骤 #0 MockMvc 测试已绿
- [ ] 本步骤完成后再跑一次 MockMvc，必须仍然 7/7 绿

**Before**（Controller 内部，节选关键段）：
```java
// Controller 直连 Mapper
@Autowired private OrderMapper orderMapper;
@Autowired private CustomerMapper customerMapper;
@Autowired private ProductMapper productMapper;

@PostMapping
public ResponseEntity<?> create(@RequestBody OrderRequest req) {
    // ... 校验略
    Customer customer = customerMapper.selectById(req.getCustomerId());
    if (customer == null) return ResponseEntity.status(404).body(Map.of("error", "customer not found"));

    BigDecimal total = BigDecimal.ZERO;
    for (OrderItemRequest item : req.getItems()) {
        Product p = productMapper.selectById(item.getProductId());
        if (p == null) return ResponseEntity.status(404).body(Map.of("error", "product not found: " + item.getProductId()));
        total = total.add(p.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())));
    }
    // ... 落库 + 组装 VO 略
}
```

**After**（保留原响应组装在 Controller，仅把"找客户/找商品/算价/落库"搬到 Service；错误异常先在 Controller 内 catch 转旧响应，保契约）：
```java
// Service：业务编排
@Service
public class OrderService {
    private final OrderMapper orderMapper;
    private final CustomerMapper customerMapper;
    private final ProductMapper productMapper;

    public OrderService(OrderMapper o, CustomerMapper c, ProductMapper p) {
        this.orderMapper = o; this.customerMapper = c; this.productMapper = p;
    }

    public PlacedOrder place(OrderRequest req) {
        Customer customer = customerMapper.selectById(req.getCustomerId());
        if (customer == null) throw new CustomerNotFoundException(req.getCustomerId());

        BigDecimal total = BigDecimal.ZERO;
        for (OrderItemRequest item : req.getItems()) {
            Product p = productMapper.selectById(item.getProductId());
            if (p == null) throw new ProductNotFoundException(item.getProductId());
            total = total.add(p.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())));
        }

        Order order = new Order();
        order.setId(UUID.randomUUID().toString());
        order.setCustomerId(req.getCustomerId());
        order.setAmount(total);
        order.setStatus(0);
        order.setCreatedAt(new Date());
        orderMapper.insert(order);
        return new PlacedOrder(order, customer);
    }
}

// Controller：仅校验 + 委托 + 响应组装；错误暂时本地 catch（步骤 #3 会接走）
@RestController
@RequestMapping("/api/orders")
public class OrderController {
    private final OrderService orderService;
    public OrderController(OrderService s) { this.orderService = s; }

    @PostMapping
    public ResponseEntity<?> create(@RequestBody OrderRequest req) {
        // 原手写校验保留（步骤 #2 替换）
        if (req == null) return ResponseEntity.badRequest().body(Map.of("error", "body required"));
        if (req.getCustomerId() == null || req.getCustomerId().isEmpty())
            return ResponseEntity.badRequest().body(Map.of("error", "customerId required"));
        if (req.getItems() == null || req.getItems().isEmpty())
            return ResponseEntity.badRequest().body(Map.of("error", "items required"));
        for (OrderItemRequest item : req.getItems())
            if (item.getQuantity() <= 0) return ResponseEntity.badRequest().body(Map.of("error", "qty must > 0"));

        try {
            PlacedOrder placed = orderService.place(req);
            OrderResponseVO vo = new OrderResponseVO();
            vo.setOrderId(placed.order().getId());
            vo.setCustomerName(placed.customer().getName());
            vo.setAmount(placed.order().getAmount());
            vo.setStatus("DRAFT");
            return ResponseEntity.ok(vo);
        } catch (CustomerNotFoundException e) {
            return ResponseEntity.status(404).body(Map.of("error", "customer not found"));
        } catch (ProductNotFoundException e) {
            return ResponseEntity.status(404).body(Map.of("error", "product not found: " + e.getProductId()));
        }
    }
}
```

**机械化步骤**
1. 新建 `OrderService` 空类，加 `@Service`，构造函数注入三个 Mapper，编译
2. 新建 `CustomerNotFoundException` / `ProductNotFoundException`（继承 `RuntimeException`，后者带 `productId` 字段），编译
3. 新建 record/类 `PlacedOrder(Order order, Customer customer)`
4. 把 Controller 内"找客户 → 找商品算价 → 落库"原样复制到 `OrderService#place`，把两处 `return ResponseEntity.status(404)...` 改成抛对应异常
5. 编译，跑 `OrderControllerTest`——此时仍走旧代码，应该 7/7 绿
6. 在 Controller 内删除三个 `@Autowired Mapper`，替换为构造注入 `OrderService`，编译
7. Controller 内业务段替换为 `try { orderService.place(req); 组装 VO; } catch (...) { 返回原 404 响应 }`，**catch 块文案逐字保持原值**
8. 跑 `OrderControllerTest`，必须仍然 7/7 绿（关键：404 文案 `product not found: p1` 一定要带 productId）
9. commit `refactor: extract OrderService and move business orchestration out of controller`

**验证**：
- `mvn test -Dtest=OrderControllerTest` → 7/7 绿
- 人工 review：Controller 不再 import `*Mapper`；`OrderService` 字段全部通过构造注入；`@Autowired` 已消失

**回滚策略**：单 commit `git revert`。新增类（`OrderService` / `PlacedOrder` / 两个异常）随 revert 一并消失，无遗留 Bean。

**后续衔接**：完成后启动 #2。

---

## 重构步骤 #2：引入 `@Valid` + Bean Validation 替代手写校验

**手法**：Replace Method with Method Object 的声明化变体；详见 `spring-specific.md §Controller 瘦身 → 提取参数校验`
**坏味道来源**：诊断 #3 手写校验泥潭
**影响文件**：
- 修改：`OrderRequest.java` / `OrderItemRequest.java`（加 Bean Validation 注解）
- 修改：`OrderController.java`（参数加 `@Valid`，删除手写校验 if）
- 不变 API：HTTP 路径 / 请求体字段 / 200 响应；**400 响应**由步骤 #3 配套的 `@ControllerAdvice` 兜底保持原 `{"error":"..."}` 文案

**前置条件**：
- [x] 步骤 #1 已完成且测试全绿
- [ ] **必须与步骤 #3 在同一 PR / 同一组 commit 内合并**——否则 `MethodArgumentNotValidException` 会变成 Spring 默认的 400 响应体（不是 `{"error":"..."}`），违反契约
- [ ] 确认使用 `jakarta.validation.*`（Spring Boot 3.x）

**Before**（Controller 内）：
```java
@PostMapping
public ResponseEntity<?> create(@RequestBody OrderRequest req) {
    if (req == null) return ResponseEntity.badRequest().body(Map.of("error", "body required"));
    if (req.getCustomerId() == null || req.getCustomerId().isEmpty())
        return ResponseEntity.badRequest().body(Map.of("error", "customerId required"));
    if (req.getItems() == null || req.getItems().isEmpty())
        return ResponseEntity.badRequest().body(Map.of("error", "items required"));
    for (OrderItemRequest item : req.getItems())
        if (item.getQuantity() <= 0) return ResponseEntity.badRequest().body(Map.of("error", "qty must > 0"));
    // ...
}
```

**After**：
```java
// OrderRequest.java
public class OrderRequest {
    @NotBlank(message = "customerId required")
    private String customerId;

    @NotEmpty(message = "items required")
    @Valid
    private List<OrderItemRequest> items;
    // getters/setters ...
}

// OrderItemRequest.java
public class OrderItemRequest {
    @NotBlank private String productId;
    @Positive(message = "qty must > 0")
    private Integer quantity;
    // getters/setters ...
}

// OrderController.java
@PostMapping
public ResponseEntity<?> create(@RequestBody @Valid OrderRequest req) {
    // 手写校验全部删除
    try {
        PlacedOrder placed = orderService.place(req);
        // ... 组装 VO（不变）
    } catch (CustomerNotFoundException e) { /* ... */ }
    catch (ProductNotFoundException e) { /* ... */ }
}
```

**机械化步骤**
1. 在 `OrderRequest` 加 `@NotBlank(message = "customerId required")` / `@NotEmpty(message = "items required")` / `@Valid`，import `jakarta.validation.constraints.*`
2. 在 `OrderItemRequest` 加 `@NotBlank` / `@Positive(message = "qty must > 0")`
3. Controller 方法签名加 `@Valid`
4. **此时不要删除手写校验**，先跑测试，确认旧测试还能过（因为旧 if 优先短路）
5. 与步骤 #3 同步推进——`@ControllerAdvice` 准备好后再删除手写 if，详见步骤 #3
6. commit `refactor: introduce Bean Validation annotations on OrderRequest`

**验证**：与步骤 #3 合并后一起跑 `OrderControllerTest`，7/7 绿。

**回滚策略**：单 commit revert；注解删除后行为退回手写校验。

---

## 重构步骤 #3：`@ControllerAdvice` 集中异常处理 + 删除手写 if（与 #2 配套合并）

**手法**：Extract Class（处理器集中）+ Replace Exception with Test 的反向版
**坏味道来源**：诊断 #4 手写异常处理、#3 配套
**影响文件**：
- 新增：`GlobalExceptionHandler.java`
- 修改：`OrderController.java`（删除 try-catch、删除手写校验 if）
- 不变 API：所有 4xx 响应体逐字段 = 原 `{"error": "<原文案>"}`，状态码不变

**前置条件**：
- [x] 步骤 #1、#2 准备就绪
- [ ] 用户确认错误响应体保持 `{"error":"..."}` 形态

**Before**：异常处理散落在 Controller 内（步骤 #1 后样子）。

**After**：
```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(CustomerNotFoundException.class)
    public ResponseEntity<Map<String, String>> handleCustomerNotFound(CustomerNotFoundException e) {
        return ResponseEntity.status(404).body(Map.of("error", "customer not found"));
    }

    @ExceptionHandler(ProductNotFoundException.class)
    public ResponseEntity<Map<String, String>> handleProductNotFound(ProductNotFoundException e) {
        return ResponseEntity.status(404).body(Map.of("error", "product not found: " + e.getProductId()));
    }

    // 接管 @Valid 的 400 响应，保持原 {"error": "..."} 形态
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, String>> handleValidation(MethodArgumentNotValidException e) {
        // 取第一个错误的 message 作为 error 字段（Bean Validation message 已设定为原文案）
        String msg = e.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(FieldError::getDefaultMessage)
                .orElse("invalid request");
        return ResponseEntity.badRequest().body(Map.of("error", msg));
    }

    // body 缺失（HttpMessageNotReadableException）保持原 "body required" 文案
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String, String>> handleBodyMissing(HttpMessageNotReadableException e) {
        return ResponseEntity.badRequest().body(Map.of("error", "body required"));
    }
}

// Controller 最终形态：薄了
@RestController
@RequestMapping("/api/orders")
public class OrderController {
    private final OrderService orderService;
    public OrderController(OrderService s) { this.orderService = s; }

    @PostMapping
    public OrderResponseVO create(@RequestBody @Valid OrderRequest req) {
        PlacedOrder placed = orderService.place(req);
        OrderResponseVO vo = new OrderResponseVO();
        vo.setOrderId(placed.order().getId());
        vo.setCustomerName(placed.customer().getName());
        vo.setAmount(placed.order().getAmount());
        vo.setStatus("DRAFT");
        return vo;
    }
}
```

**机械化步骤**
1. 新建 `GlobalExceptionHandler`，加 `@RestControllerAdvice`
2. 实现 `CustomerNotFoundException` / `ProductNotFoundException` 两个 `@ExceptionHandler`，**响应体逐字符匹配原 `Map.of("error", "...")` 文案**（包括 `"product not found: " + productId`）
3. 实现 `MethodArgumentNotValidException` 处理器：取第一条 FieldError 的 message，包成 `{"error": message}`。前提是步骤 #2 的 message 文本已设为 `"customerId required"` / `"items required"` / `"qty must > 0"`
4. 实现 `HttpMessageNotReadableException` 处理器，返回 `{"error": "body required"}`
5. 删除 Controller 内的所有手写校验 if 与 try-catch
6. 跑 `OrderControllerTest`，**逐个用例**确认状态码与 `$.error` 文案完全一致；不一致就调整 ControllerAdvice 文案直到匹配
7. commit `refactor: introduce @ControllerAdvice for centralized error handling`

**验证**：
- `mvn test -Dtest=OrderControllerTest` → 7/7 绿
- 人工 curl 比对：步骤 #0 之前的响应 vs 步骤 #3 之后的响应，二进制级别一致（content-type / 状态码 / body）

**回滚策略**：两个 commit（步骤 #2 + #3）一起 revert，或合并为一个 commit `refactor: replace hand-written validation with @Valid + @ControllerAdvice`。

**后续衔接**：完成后路线图核心三件套已落地。继续可启动步骤 #4（DTO Mapper 抽取）、#5（Enum 化）、#6（批量查询性能优化），任一项均独立可做。

---

## 全局校验清单（整个重构序列结束后）

- [ ] HTTP 路径不变：`POST /api/orders`
- [ ] 请求体字段名 / 嵌套结构不变（仅新增校验注解）
- [ ] 200 响应 JSON 字段集与值类型不变：`orderId` / `customerName` / `amount` / `status`
- [ ] 400 响应 body 形态 `{"error": "..."}` 不变；4 类文案逐字符匹配：`body required` / `customerId required` / `items required` / `qty must > 0`
- [ ] 404 响应 body 形态 `{"error": "..."}` 不变；2 类文案：`customer not found` / `product not found: <productId>`
- [ ] `OrderControllerTest` 7/7 绿
- [ ] Controller 不再 import `*Mapper`
- [ ] 无 `@Autowired` 字段，全部构造注入

> 引用：`references/refactoring-techniques.md §7 Extract Class`、`references/spring-specific.md §Controller 瘦身`、`references/output-templates.md §重构步骤模板`、`references/legacy-code.md §特征化测试`。
