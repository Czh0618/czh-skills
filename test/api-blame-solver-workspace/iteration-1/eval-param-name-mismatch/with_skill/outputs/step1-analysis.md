# API Blame Solver — 分析报告

## 第一步：解析输入

| 信息项 | 值 | 来源 |
|--------|------|------|
| 请求方法 | POST（由 Request Payload 推断） | 前端使用了 Request Payload |
| Content-Type | application/json（由 `{}` 格式推断） | Request Payload 格式 |
| 实际发送的参数 | `userid` (int, 值 123), `orderType` (string, 值 "NORMAL") | Request Payload |
| HTTP 状态码 | 400 Bad Request | Response |
| 响应体错误信息 | `"Required request parameter 'userId' for method parameter type Long is not present"` | Response body |
| 异常类型 | `MissingServletRequestParameterException` | Stacktrace 第一行 |
| 出错位置 | `RequestParamMethodArgumentResolver.java:206` | Stacktrace |
| 后端期望的参数名 | `userId` (驼峰) | 异常信息中的 `'userId'` |
| 后端期望的参数类型 | `Long` | 异常信息中的 `Long` |

## 第二步：交叉比对

### 参数名比对

- 前端发送的 key：**`userid`**（全小写）
- 后端期望的 key：**`userId`**（驼峰，`I` 大写）
- **不匹配！**

### 关键发现：Content-Type 与注解类型不匹配

这是比参数名更深层次的问题：

1. **前端以 JSON body 发送数据**（`Content-Type: application/json`，Payload 为 `{}` 格式）。
2. **后端使用的是 `@RequestParam`**（从 `MissingServletRequestParameterException` 和 `RequestParamMethodArgumentResolver` 可以确认），该注解从 **URL 查询参数** 或 **表单数据** (`application/x-www-form-urlencoded`) 中取值，**不从 JSON body 中读取**。

这意味着即使前端把参数名从 `userid` 改成 `userId`，后端仍然收不到值，因为 Spring 的 `@RequestParam` 根本不会解析 JSON body 中的字段。

### 状态码 + 异常对应

- `400` + `MissingServletRequestParameterException` → 后端要求的必填参数未收到，前端没传（或传的方式后端收不到）。

## 第三步：责任判定

**前端和后端都有问题，但这是两个层面的问题：**

1. **参数名拼写错误（前端问题）**：前端把 `userId` 拼成了 `userid`，即使参数传输方式正确，这个名字也不对。
2. **传输方式不匹配（前后端不一致）**：前端用 JSON body 发请求，后端用 `@RequestParam` 收请求。两者通信方式根本对不上。

**主要责任方：双方都有责任，但根源在于前后端通信协议不一致。** 如果只能改一端，修改后端的收益更大（改成 `@RequestBody` + DTO 是 RESTful API 的标准做法）。

## 第四步：输出报告

### 责任判定

**前端 + 后端**：前端参数名拼写错误（`userid` vs `userId`），且前后端传输方式不一致（JSON body vs `@RequestParam`）。

### 根本原因

这个报错有两层原因：

1. **直接原因**：前端把参数名 `userId` 拼成了 `userid`（全小写），后端用 `@RequestParam` 在 URL 查询参数或表单数据中找 `userId`，当然找不到。
2. **更深层原因**：前端以 JSON body 方式发送请求，而后端用 `@RequestParam` 接收——`@RequestParam` 只读 URL 查询参数和表单数据，不读 JSON body。所以即使参数名拼对了，后端一样收不到值，照样报错。

### 修复方案

**推荐方案：修改后端（RESTful API 标准做法）**

将后端 Controller 从 `@RequestParam` 改为 `@RequestBody` + DTO：

```java
// 修复前
public ResponseEntity<?> getOrder(@RequestParam Long userId, @RequestParam String orderType) { ... }

// 修复后
@Data
public class OrderRequest {
    private Long userId;
    private String orderType;
}

public ResponseEntity<?> getOrder(@RequestBody OrderRequest request) { ... }
```

**备选方案：修改前端（如果后端接口无法改动）**

前端改为以查询参数或表单数据发送：

```javascript
// 方式一：查询参数
const response = await fetch(`/api/order?userId=${userId}&orderType=${orderType}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
});

// 方式二：表单数据（URLSearchParams）
const params = new URLSearchParams();
params.append('userId', userId);
params.append('orderType', orderType);
const response = await fetch('/api/order', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: params,
});
```

### 补充说明

- 如果后端有多个参数，`@RequestBody` + DTO 是更规范的做法，代码也更简洁。
- 前后端在开发前应先对齐接口契约（参数名、传输方式、Content-Type），可以避免大部分这类联调问题。
- 建议团队使用 OpenAPI/Swagger 等工具维护接口文档，减少沟通成本。
