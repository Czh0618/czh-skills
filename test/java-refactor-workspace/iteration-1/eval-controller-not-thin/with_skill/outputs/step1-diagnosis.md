# Step 0：边界与安全网确认

## 重构上下文摘要（待用户确认）

| 维度 | 内容 |
|------|------|
| 范围 | `OrderController#create`（单方法），允许波及同包/新增 `OrderService`、`@ControllerAdvice`、DTO Mapper、Bean Validation 注解 |
| 测试覆盖 | **未明确**。用户只说"review 一下"，没有提供测试覆盖率信息 → 需要询问/标记为 **高风险** |
| API 变更 | **必须保持 HTTP 契约不变**：路径 `POST /api/orders`、请求体 `OrderRequest`、响应 `OrderResponseVO` JSON 结构、HTTP 状态码（200 / 400 / 404）、错误响应体形态 `{"error": "..."}` |
| 技术栈 | Spring Boot（基于 `@RestController` / `@RequestMapping` 推断），MyBatis（基于 `*Mapper` 命名），Java 版本未明确 |
| 风险标记 | **高**（测试覆盖未知 + Controller 是 Web 边界，行为变更会影响前端调用方） |

### 待用户确认（Step 0 阻塞项）

1. **测试覆盖**：`OrderController#create` 是否有 MockMvc / `@WebMvcTest` 测试？覆盖到 customer not found / product not found / qty 非法等错误路径吗？
   - 如果**没有**：路线图必须先排入"补 Controller 层特征化测试（MockMvc）"，固化当前 HTTP 行为后再拆。
   - 如果**有**：直接进入业务重构步骤。
2. **错误响应体格式**：当前手写返回 `Map.of("error", "...")`。引入 `@ControllerAdvice` 后是否允许把错误体升级为更规范的 `{"code": "...", "message": "...", "timestamp": "..."}`？还是必须**逐字段保持** `{"error": "..."}` 这个形态？这直接决定 ControllerAdvice 输出 schema。
3. **Java 版本与 Bean Validation 版本**：Spring Boot 3.x 使用 `jakarta.validation.*`，Spring Boot 2.x 使用 `javax.validation.*`，请确认以便给出正确 import。
4. **是否允许新增依赖**：MapStruct（推荐）或保持手写 Mapper？

> 在以上 4 项中，**测试覆盖** 与 **错误响应体格式** 是阻塞性问题（影响安全网与契约边界），其余可在 Step 3 前补齐。本次诊断在"假定测试覆盖低且错误体必须保持原形态"的保守前提下继续。

---

# Step 1：诊断报告（Diagnosis）

**扫描范围**：`OrderController#create`（单方法 ~50 行，但承载了校验/数据访问/业务编排/落库/响应组装五重职责）
**Java 版本**：未明确（按 Spring Boot 3.x 推断）| **框架**：Spring Boot + MyBatis | **测试覆盖**：未明确（按低覆盖假设）

## 问题清单

| # | 坏味道（Java 名）| 全局规则映射 | 位置 | 严重度 | 推荐手法 | 工作量 | 依赖前置 |
|---|----------------|------------|------|-------|---------|-------|---------|
| 1 | **Fat Controller / 业务逻辑泄露到 Web 层**：Controller 方法承担了客户查询、库存与价格计算、订单落库等业务编排 | 僵化 + 不必要复杂性 + 晦涩性 | `create` 整方法 L9-L52 | **高** | Extract Class → `OrderService`；Move Method 把业务搬到 Service | 1.5h | 需 MockMvc 特征化测试 |
| 2 | **分层泄露（Layer Violation）**：Controller 直接 `@Autowired` 注入 `OrderMapper` / `CustomerMapper` / `ProductMapper`，绕过 Service 层 | 僵化 + 循环依赖风险 + 脆弱性 | 字段声明 L4-L6 | **高** | Move Field（Mapper 注入下沉到 Service）；Controller 仅注入 `OrderService` | 30min | 依赖 #1 完成 |
| 3 | **手写参数校验泥潭**：5 处 `if (xxx == null) return ResponseEntity.badRequest()...`，散落在 Controller 内 | 冗余 + 霰弹式修改 | L11-L23 | **高** | 引入 `@Valid` + Bean Validation 注解（`@NotBlank` / `@NotEmpty` / `@Positive` / `@Valid` 嵌套），把校验声明化 | 45min | 需确认 jakarta vs javax；不破坏 400 响应契约 |
| 4 | **手写异常处理 / 状态码硬编码**：`return ResponseEntity.status(404).body(...)` 混在业务流里，每加一种错误都要改 Controller | 霰弹式修改 + 不必要复杂性 | L26-L28, L33-L35 | **高** | 自定义业务异常（`CustomerNotFoundException` / `ProductNotFoundException`）+ `@ControllerAdvice` + `@ExceptionHandler` 集中处理 | 1h | 需确认错误体 JSON schema 是否允许调整 |
| 5 | **手写 DTO ↔ Domain ↔ VO 字段拷贝**：构造 `Order` 9 行 set，构造 `OrderResponseVO` 4 行 set | 冗余 + 数据泥团 | L42-L51 | **中** | Extract Class → `OrderDtoMapper`（手写或 MapStruct）；`req → Order`、`Order + Customer → VO` 两个映射方法 | 30min | 与 #1 一并落地 |
| 6 | **晦涩的魔法值**：`status(0)` / `setStatus("DRAFT")` 同义不同形 | 晦涩性 + 数据泥团 | L46, L51 | **中** | Replace Magic Number with Symbolic Constant 或 Replace Type Code with Enum（`OrderStatus` enum） | 30min | 影响面较广，建议单独安排 |
| 7 | **N+1 查询风险**：`for items: productMapper.selectById(...)` 循环单条查 | 性能隐患（不必要复杂性） | L36-L40 | **中** | 改批量 `selectByIds(Collection)`；建议同时引入 `code-performance-analyzer` 评估 | 1h | 与 #1 重构同步完成 |
| 8 | **响应错误结构不一致风险**：成功路径返回 `OrderResponseVO`，错误路径返回 `Map<String,String>` | 晦涩性 | 全方法 | 低 | 统一错误响应体（与 #4 配套） | - | 跟随 #4 |

## 总体观察

1. **核心问题不是"Controller 多写了几行"，而是 Web 层承担了三类不属于它的职责**：业务编排、数据访问、错误响应组装。三个职责各自有 Spring 提供的成熟落地方案——`@Service` / Service 注入 Mapper / `@ControllerAdvice` + Bean Validation。引入这三件套后，Controller 自然瘦下来。
2. **诊断 #1、#2、#3、#4 是同一个根因（"Controller 承担了全部职责"）的不同表现**，重构时彼此强耦合，应一组规划但分小步落地。
3. **测试覆盖未明确是当前最大风险**：Controller 是 HTTP 契约的边界，任何重构若没有 MockMvc 层的特征化测试兜底，就无法证明"路径/状态码/响应体没变"。Step 2 路线图会把"补 MockMvc 测试"排在第一位。

## 待用户确认

1. Step 0 阻塞项的 4 个问题（特别是测试覆盖与错误体 schema）。
2. 是否同意把诊断 #1+#2+#3+#4 作为一组"Controller 瘦身核心改造"打包推进，#5+#6 跟随，#7 性能优化分离评估。

> 引用：`references/spring-specific.md §Controller 瘦身`、`§分层架构与职责泄露`、`references/smells-catalog.md`、`references/refactoring-techniques.md §7 Extract Class`。
