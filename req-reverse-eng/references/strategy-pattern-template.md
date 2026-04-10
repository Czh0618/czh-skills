# 策略模式代码模板

生成 Spring Boot 策略模式骨架时参考此模板。根据决策矩阵的实际内容调整接口名、上下文字段和实现类。

---

## 1. 业务上下文对象

```java
package com.example.{module}.domain;

import lombok.Data;
import lombok.Builder;

/**
 * 业务上下文 — 封装决策矩阵中涉及的所有判断字段
 * 字段应从决策矩阵的"场景条件"列中提取
 */
@Data
@Builder
public class BusinessContext {
    // 从决策矩阵的场景条件中提取字段
    // 示例：
    // private Long userId;
    // private String userStatus;
    // private BigDecimal orderAmount;
    // private Boolean realNameVerified;
    // private String currentState;
}
```

## 2. 校验结果

```java
package com.example.{module}.domain;

import lombok.Data;
import lombok.Builder;

@Data
@Builder
public class ValidationResult {
    private boolean passed;
    private String errorCode;
    private String errorMessage;
    private String suggestedAction; // 如"跳转实名认证"
}
```

## 3. 策略接口

```java
package com.example.{module}.strategy;

import com.example.{module}.domain.BusinessContext;
import com.example.{module}.domain.ValidationResult;

public interface ValidationStrategy {

    /**
     * 判断当前策略是否适用于给定的业务上下文
     * 对应决策矩阵的"场景条件"列
     */
    boolean supports(BusinessContext context);

    /**
     * 执行校验/业务逻辑
     * 对应决策矩阵的"触发动作"和"异常抛出"列
     */
    ValidationResult validate(BusinessContext context);

    /**
     * 执行优先级，数值越小越先执行
     * 用于处理规则冲突时的优先级排序
     */
    int order();
}
```

## 4. 策略工厂

```java
package com.example.{module}.strategy;

import org.springframework.stereotype.Component;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

@Component
public class ValidationStrategyFactory {

    private final List<ValidationStrategy> strategies;

    /**
     * Spring 自动注入所有 ValidationStrategy 实现类
     * 按 order() 升序排列
     */
    public ValidationStrategyFactory(List<ValidationStrategy> strategies) {
        this.strategies = strategies.stream()
            .sorted(Comparator.comparingInt(ValidationStrategy::order))
            .collect(Collectors.toList());
    }

    public List<ValidationStrategy> getApplicableStrategies(BusinessContext context) {
        return strategies.stream()
            .filter(s -> s.supports(context))
            .collect(Collectors.toList());
    }
}
```

## 5. 具体策略实现（每条决策矩阵规则一个类）

```java
package com.example.{module}.strategy.impl;

import com.example.{module}.domain.BusinessContext;
import com.example.{module}.domain.ValidationResult;
import com.example.{module}.strategy.ValidationStrategy;
import org.springframework.stereotype.Component;

/**
 * 规则：[从决策矩阵复制场景条件]
 * 动作：[从决策矩阵复制触发动作]
 */
@Component
public class XxxValidationStrategy implements ValidationStrategy {

    @Override
    public boolean supports(BusinessContext context) {
        // 对应决策矩阵的"场景条件"
        // return context.getXxx() != null && context.getXxx().equals("yyy");
        return false;
    }

    @Override
    public ValidationResult validate(BusinessContext context) {
        // 对应决策矩阵的"触发动作"和"异常抛出"
        return ValidationResult.builder()
            .passed(false)
            .errorCode("XXX_ERROR")
            .errorMessage("具体错误信息")
            .suggestedAction("建议的处理动作")
            .build();
    }

    @Override
    public int order() {
        return 100; // 根据业务优先级调整
    }
}
```

## 6. 编排入口

```java
package com.example.{module}.service;

import com.example.{module}.domain.BusinessContext;
import com.example.{module}.domain.ValidationResult;
import com.example.{module}.strategy.ValidationStrategy;
import com.example.{module}.strategy.ValidationStrategyFactory;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class BusinessValidationService {

    private final ValidationStrategyFactory strategyFactory;

    public BusinessValidationService(ValidationStrategyFactory strategyFactory) {
        this.strategyFactory = strategyFactory;
    }

    /**
     * 对业务上下文执行所有适用的校验策略
     * 遇到第一个不通过的规则即返回（fail-fast）
     */
    public ValidationResult validate(BusinessContext context) {
        List<ValidationStrategy> applicable = strategyFactory.getApplicableStrategies(context);

        for (ValidationStrategy strategy : applicable) {
            ValidationResult result = strategy.validate(context);
            if (!result.isPassed()) {
                return result;
            }
        }

        return ValidationResult.builder()
            .passed(true)
            .build();
    }
}
```

## 后续新增规则的迭代话术

当产品补充了新规则，用户只需对 AI 说：

> "基于之前的决策矩阵，新增一条规则：当 [场景条件] 发生时，执行 [触发动作]，异常抛出 [异常类型]，状态变更为 [目标状态]。请实现一个新的 ValidationStrategy 实现类，并注册到工厂中。"

由于使用了 Spring 的自动扫描机制，新增 `@Component` 类即自动注册，无需修改工厂或编排代码。
