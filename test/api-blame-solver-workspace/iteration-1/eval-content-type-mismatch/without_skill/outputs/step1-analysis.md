# API 415 Content-Type Mismatch 分析

## 问题概述

前端 POST 请求返回 **415 Unsupported Media Type**。

## 责任方：前端

**明确归因：前端负责修复。**

## 根因分析

1. **前端发送的 Content-Type**：`text/plain`
2. **前端发送的实际数据**：`JSON.stringify({ orderId: 'ORD-001' })`，即 `{"orderId":"ORD-001"}`，本质是 JSON 格式
3. **后端 Spring 期望的 Content-Type**：`application/json`（由 `@RequestBody` 反序列化触发）

后端 Spring MVC 的 `@RequestBody` 注解配合 JSON MessageConverter 会检查请求的 `Content-Type` 头。当声明为 `text/plain` 时，Spring 认为这不是 JSON 数据，拒绝处理，抛出 `HttpMediaTypeNotSupportedException`。

**核心矛盾：前端声明了 `text/plain`，但实际发送的是 JSON 数据。声明与内容不一致。**

## Stacktrace 解读

```
org.springframework.web.HttpMediaTypeNotSupportedException: Content type 'text/plain' not supported
```

Spring 的 `AbstractMessageConverterMethodArgumentResolver.readWithMessageConverters` 在处理请求体时，会遍历已注册的 HttpMessageConverter，寻找能处理 `text/plain` 的转换器。但 Spring MVC 默认没有为 `text/plain` 注册对象反序列化转换器（只有 `StringHttpMessageConverter` 会处理为纯字符串，不会做 JSON 反序列化），因此抛出异常。

## 修复方案

### 前端修复（推荐，正确做法）

将 `Content-Type` 改为 `application/json`：

```javascript
fetch('/api/orders', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'  // 改这里
  },
  body: JSON.stringify({ orderId: 'ORD-001' })
})
```

### 后端修复（不推荐，仅在特殊场景下考虑）

如果确实需要接受 `text/plain`，后端需手动将请求体作为字符串读取后再自行解析 JSON：

```java
@PostMapping(value = "/api/orders", consumes = {"application/json", "text/plain"})
public Order createOrder(@RequestBody String body) {
    // 手动解析 JSON
    OrderRequest request = new ObjectMapper().readValue(body, OrderRequest.class);
    ...
}
```

但这属于反模式，不推荐。**标准做法是前端修正 Content-Type。**

## 总结

| 项目 | 值 |
|------|-----|
| 责任方 | 前端 |
| 根因 | `Content-Type` 声明为 `text/plain`，但实际发送 JSON 数据 |
| 修复方式 | 前端将 `Content-Type` 改为 `application/json` |
| HTTP 状态码 | 415 Unsupported Media Type（服务端正确行为） |
