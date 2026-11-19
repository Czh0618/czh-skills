package com.example.order.dto;

import com.example.order.entity.Order;
import java.math.BigDecimal;

public record OrderDetailResponse(Long id, Long userId, BigDecimal amount, String remark) {

    public static OrderDetailResponse from(Order o) {
        return new OrderDetailResponse(o.getId(), o.getUserId(), o.getAmount(), o.getRemark());
    }
}
