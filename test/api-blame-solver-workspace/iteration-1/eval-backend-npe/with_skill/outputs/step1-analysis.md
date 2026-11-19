## 责任判定

**后端**：后端代码存在判空缺陷，未对可为 null 的 nickname 参数做防御性处理导致 NPE。

## 根本原因

前端传来的 `nickname` 参数值为 `null`，后端在 `UserService.updateProfile` 方法的第 87 行直接调用了 `nickname.length()`，没有先判空，所以抛出了 NullPointerException。

## 详细分析

### 第一步：解析输入

| 信息项 | 值 |
|--------|-----|
| 请求方法 & URL | POST /api/user/profile |
| 实际发送的参数 | `{ "userId": 456, "nickname": null }` |
| HTTP 状态码 | 500 Internal Server Error |
| 响应体错误信息 | `{"code":500,"message":"Internal Server Error"}` |
| 异常类型 | `java.lang.NullPointerException` |
| 出错位置 | `com.example.service.UserService.updateProfile(UserService.java:87)` |
| 调用链路 | `UserController.profile(UserController.java:42)` → `UserService.updateProfile` |
| 错误原因 | `Cannot invoke "String.length()" because "nickname" is null` |

### 第二步：交叉比对

**参数分析**：
- 前端传的 `userId: 456`（数字类型），正常接收
- 前端传的 `nickname: null`，后端代码在第 87 行对该变量调用了 `String.length()`

**状态码 + 异常对应**：
- `500` + `NullPointerException` → 明确指向后端代码缺陷：没有对可能为 null 的参数进行判空处理

**根因定位**：
从 Stacktrace 错误信息 `Cannot invoke "String.length()" because "nickname" is null` 可以精确判断：
- 后端在 `UserService.java:87` 行对 `nickname` 调用了 `length()` 方法
- 此时 `nickname` 的值为 `null`
- 说明后端允许前端传 null（没有用 `@NotNull` 等校验注解拦截），但在业务代码中又没有判空

### 第三步：责任判定依据

前端传 `nickname: null` 本身并不一定是错误的——这取决于接口契约：
- 如果接口约定 nickname 是必填字段，那前端没传值是前端问题
- 如果接口约定 nickname 是可选字段（允许不传或传 null），那后端就应该判空

但无论从哪个角度，**后端报 500 NPE 是明确的代码缺陷**：
1. 如果 nickname 是必填的，应该用 `@NotNull` / `@NotBlank` 校验注解在入口处返回 400，而不是让 NPE 抛到外层变成 500
2. 如果 nickname 是可选的，应该在代码中判空处理

## 修复方案

### 方案一：加参数校验（推荐，如果 nickname 是必填字段）

在 Controller 层或 DTO 上添加校验注解，在入口处拦截非法请求：

```java
// 如果 nickname 是 DTO 字段
public class ProfileUpdateRequest {
    private Long userId;

    @NotNull(message = "nickname 不能为空")
    @NotBlank(message = "nickname 不能为空字符串")
    private String nickname;

    // getter / setter
}
```

同时在 Controller 方法参数上加 `@Valid`：

```java
@PostMapping("/profile")
public Result profile(@Valid @RequestBody ProfileUpdateRequest request) {
    // ...
}
```

这样当前端传 `nickname: null` 时，会返回 400 状态码并带上明确的错误提示，而不是 500 NPE。

### 方案二：加判空防御（如果 nickname 是可选字段）

在 `UserService.updateProfile` 方法中判空：

```java
// UserService.java:87 修复前
if (nickname.length() > 20) {
    throw new IllegalArgumentException("昵称过长");
}

// UserService.java:87 修复后
if (nickname != null && nickname.length() > 20) {
    throw new IllegalArgumentException("昵称过长");
}
```

或者更规范地，在方法入口处统一处理：

```java
public void updateProfile(Long userId, String nickname) {
    if (nickname == null) {
        // 可选策略1：跳过 nickname 更新
        // 可选策略2：使用默认值
        // 可选策略3：抛出自定义业务异常
        return;
    }
    // 后续逻辑...
}
```

### 补充建议

1. **全局异常处理**：确保项目有 `@ControllerAdvice` 全局异常处理器，将 NPE 等运行时异常统一转为有意义的错误响应，避免直接暴露 500
2. **接口契约明确**：在接口文档中明确标注哪些字段必填、哪些可选，避免前后端理解不一致

## 补充说明

这是一个典型的**后端健壮性不足**问题。前后端联调中，后端永远不应该信任前端传来的数据——即使前端"按理说不该传 null"，后端也应该做好防御。最佳实践是：
- 必填字段用 `@Valid` 校验注解在入口处拦截（返回 400）
- 可选字段在业务代码中判空处理
- 永远不要让 NPE 穿透到全局异常处理器变成 500 错误
