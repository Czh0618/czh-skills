package com.example.order.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;

public record CreateOrderRequest(
        @NotNull Long userId,
        @NotNull BigDecimal amount,
        @Size(max = 200) String remark) {
}
