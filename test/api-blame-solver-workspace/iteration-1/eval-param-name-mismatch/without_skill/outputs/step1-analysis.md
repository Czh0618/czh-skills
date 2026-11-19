# API 联调错误分析报告

## 1. 责任方判定

**责任方：前端 + 后端双方都有问题**（但主要责任在**前端**）

前端传递了错误的参数名，但后端也没有给出清晰的错误提示来帮助快速定位问题。

---

## 2. 根本原因

**参数名大小写不一致**导致的经典联调错误。

| 角色   | 使用的参数名 | 说明                              |
|--------|-------------|-----------------------------------|
| 前端   | `userid`    | Request Payload 中的字段名         |
| 后端   | `userId`    | Spring 期望的参数名（驼峰命名）     |

### 错误链路分析

1. 前端发送的 JSON body（或 query 参数）中包含字段 `"userid": 123`
2. 后端 Controller 方法签名中使用了 `@RequestParam("userId")` 注解，期望接收到名为 `userId` 的参数
3. Spring 在请求中找不到名为 `userId` 的参数，抛出 `MissingServletRequestParameterException`
4. 返回 400 状态码及错误信息

### 关键证据

错误信息原文：
```
Required request parameter 'userId' for method parameter type Long is not present
```

这明确说明后端期望的参数名是 `userId`（注意大写 `I`），而前端发送的是 `userid`（全小写）。

---

## 3. 修复方案

### 方案一：前端修改（推荐，改动最小）

将前端请求中的参数名改为驼峰命名，与后端保持一致：

```json
{
  "userId": 123,
  "orderType": "NORMAL"
}
```

### 方案二：后端修改

如果团队约定使用全小写参数名，后端应添加 `@RequestParam` 的 value 属性来兼容：

```java
// 修改前
public Response method(@RequestParam Long userId, ...)

// 修改后
public Response method(@RequestParam("userid") Long userId, ...)
```

### 方案三：双方统一规范（长期方案）

建立团队 API 命名规范，统一使用 camelCase 或 snake_case，并通过以下方式防止此类问题再次发生：

- **Swagger/OpenAPI 文档**：前后端基于同一份 API 契约生成代码
- **代码审查检查清单**：将参数命名一致性加入 code review 检查项
- **自动化测试**：编写契约测试（如 Pact），在 CI 阶段拦截此类不匹配

---

## 4. 建议的修复步骤（推荐方案一）

1. **前端**：将 `"userid"` 改为 `"userId"`（2 分钟）
2. **验证**：重新发起请求，确认 200 响应
3. **预防**：在团队 API 文档中明确参数命名规范
