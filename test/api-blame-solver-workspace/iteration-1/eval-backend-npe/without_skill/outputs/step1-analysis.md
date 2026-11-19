# API Blame Analysis: /api/user/profile NPE

## Error Summary

- **Endpoint**: `POST /api/user/profile`
- **HTTP Status**: 500 Internal Server Error
- **Exception**: `java.lang.NullPointerException: Cannot invoke "String.length()" because "nickname" is null`
- **Location**: `com.example.service.UserService.updateProfile(UserService.java:87)`
- **Caller**: `com.example.controller.UserController.profile(UserController.java:42)`

## Request Details

```json
{
  "userId": 456,
  "nickname": null
}
```

## Root Cause

The backend `UserService.updateProfile` method at line 87 calls `nickname.length()` without first checking if `nickname` is null. When the frontend sends `"nickname": null`, the method receives a null value and immediately throws a `NullPointerException` when trying to invoke the `length()` method on it.

## Responsibility: **Backend**

The backend is responsible for this 500 error. Here's the reasoning:

1. **Backend's duty to validate input**: A backend API must defensively validate all incoming request parameters, including checking for null values. Sending `null` for an optional field is a perfectly valid client behavior.

2. **`null` is a valid JSON value**: The frontend correctly serialized `"nickname": null` as valid JSON. The backend accepted it at the transport level but failed to handle it at the business logic level.

3. **Missing null-safety**: The code directly calls `nickname.length()` (a String method) without a null guard. This is a textbook case of missing defensive programming.

4. **Proper error handling absent**: Instead of returning a 500 Internal Server Error, the backend should have either:
   - Accepted `null` as a valid value (e.g., to clear the nickname), or
   - Returned a 400 Bad Request with a descriptive validation error message

## Fix Recommendations

### Backend Fix (Primary Responsibility)

Add null-safety to `UserService.updateProfile` at line 87:

```java
// Before (broken):
if (nickname.length() > 10) { ... }

// After (safe):
if (nickname != null && nickname.length() > 10) { ... }
```

Alternatively, use validation annotations at the DTO/parameter level:

```java
public void updateProfile(@NotNull Long userId,
                          @Size(max = 10) String nickname) {
    // Safe to use nickname after validation
}
```

Or use Java's `Optional` or `StringUtils` for cleaner null handling:

```java
if (StringUtils.hasLength(nickname) && nickname.length() > 10) { ... }
// or
int length = Optional.ofNullable(nickname).map(String::length).orElse(0);
```

### Frontend (Optional Improvement)

While the backend bears primary responsibility, the frontend should ideally omit the `nickname` field entirely rather than sending `"nickname": null` if the user did not provide a value. This follows the convention of omitting absent optional fields:

```json
{
  "userId": 456
}
```

## Verdict

| Aspect | Detail |
|--------|--------|
| **Responsible party** | Backend |
| **Root cause** | Missing null check before calling `String.length()` on `nickname` |
| **Severity** | High -- causes 500 error for valid client input |
| **Fix location** | `UserService.updateProfile`, line 87 |
| **Fix type** | Add null guard / input validation |
