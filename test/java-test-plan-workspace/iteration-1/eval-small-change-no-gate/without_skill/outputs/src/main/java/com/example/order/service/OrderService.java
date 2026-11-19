package com.example.order.service;

import com.example.order.dto.CreateOrderRequest;
import com.example.order.dto.OrderDetailResponse;
import com.example.order.entity.Order;
import com.example.order.mapper.OrderMapper;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class OrderService {

    private final OrderMapper orderMapper;

    public OrderService(OrderMapper orderMapper) {
        this.orderMapper = orderMapper;
    }

    public Long create(CreateOrderRequest req) {
        Order order = new Order();
        order.setUserId(req.userId());
        order.setAmount(req.amount());
        order.setRemark(req.remark());
        orderMapper.insert(order);
        return order.getId();
    }

    public OrderDetailResponse detail(Long id) {
        Order order = orderMapper.selectById(id);
        if (order == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "order not found: " + id);
        }
        return OrderDetailResponse.from(order);
    }
}
