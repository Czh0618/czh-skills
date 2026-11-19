# API Blame Solver — 分析报告

## 第一步：解析输入

| 信息项 | 值 | 来源 |
|--------|-----|------|
| 请求方法 & URL | `POST /api/orders` | 前端 fetch 代码 |
| Content-Type | `text/plain` | 前端 request header |
| 实际发送的 body | `{"orderId":"ORD-001"}` (JSON 字符串) | `JSON.stringify({ orderId: 'ORD-001' })` |
| HTTP 状态码 | `415 Unsupported Media Type` | Response |
| 异常类型 | `org.springframework.web.HttpMediaTypeNotSupportedException` | Stacktrace 第一行 |
| 异常消息 | `Content type 'text/plain' not supported` | Stacktrace |
| 出错位置 | `AbstractMessageConverterMethodArgumentResolver.readWithMessageConverters:212` | Stacktrace |

## 第二步：交叉比对

**核心矛盾**：前端 `body` 实际发送的是 JSON 格式字符串（`JSON.stringify` 序列化后的 `{"orderId":"ORD-001"}`），但 `Content-Type` header 却声明为 `text/plain`。

Spring Boot 的 `@RequestBody` 反序列化流程如下：
1. 读取请求的 `Content-Type` header
2. 根据 Content-Type 选择对应的 `HttpMessageConverter`
3. Spring 默认注册了 `MappingJackson2HttpMessageConverter`（处理 `application/json`），但没有注册能处理 `text/plain` 且反序列化为 DTO 的 converter
4. 因此 Spring 抛出 `HttpMediaTypeNotSupportedException`，拒绝处理该请求

**参数名/类型/完整性**：无法判断——请求在到达参数绑定阶段之前就被拦截了。即使参数完全正确，Content-Type 不对照样报 415。

## 责任判定

**前端**：Content-Type header 设置错误。body 发的是 JSON，但 header 声明为 `text/plain`，导致后端拒绝解析。

## 根本原因

前端把 `Content-Type` 写成了 `'text/plain'`，但 body 实际传的是 JSON 字符串。Spring Boot 后端只接受 `application/json`，看到 `text/plain` 就拒绝处理，返回 415。

## 修复方案

将前端 fetch 的 `Content-Type` 从 `text/plain` 改为 `application/json`：

```javascript
// 修改前（错误）
fetch('/api/orders', {
  method: 'POST',
  headers: {
    'Content-Type': 'text/plain'
  },
  body: JSON.stringify({ orderId: 'ORD-001' })
})

// 修改后（正确）
fetch('/api/orders', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ orderId: 'ORD-001' })
})
```

修改后 Spring 的 `MappingJackson2HttpMessageConverter` 会正确识别 `application/json`，将 body 反序列化为后端的 DTO 对象，请求即可正常处理。

## 补充说明

无其他问题。这是一个单一根因的明确错误。
