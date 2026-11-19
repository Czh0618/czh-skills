package com.example.order.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.example.order.dto.CreateOrderRequest;
import com.example.order.entity.Order;
import com.example.order.mapper.OrderMapper;
import java.math.BigDecimal;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock
    OrderMapper orderMapper;

    @InjectMocks
    OrderService orderService;

    @Test
    void createPassesRemarkToMapper() {
        orderService.create(new CreateOrderRequest(1L, BigDecimal.TEN, "leave at door"));

        ArgumentCaptor<Order> captor = ArgumentCaptor.forClass(Order.class);
        verify(orderMapper).insert(captor.capture());
        assertEquals("leave at door", captor.getValue().getRemark());
    }

    @Test
    void createWithoutRemarkKeepsNull() {
        orderService.create(new CreateOrderRequest(1L, BigDecimal.TEN, null));

        ArgumentCaptor<Order> captor = ArgumentCaptor.forClass(Order.class);
        verify(orderMapper).insert(captor.capture());
        assertNull(captor.getValue().getRemark());
    }

    @Test
    void detailReturnsRemark() {
        Order order = new Order();
        order.setId(7L);
        order.setRemark("gift");
        when(orderMapper.selectById(7L)).thenReturn(order);

        assertEquals("gift", orderService.detail(7L).remark());
    }
}
