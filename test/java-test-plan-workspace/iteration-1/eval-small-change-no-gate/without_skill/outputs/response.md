结论：不用先出测试计划。这是给订单表加一个可空 varchar(200) 字段，只涉及 DDL、创建入参、insert/select 映射、详情返回这几处，风险集中且很小，直接按下面的验收条件开发并补测试即可。完整测试计划留给涉及状态流转、金额、多表事务这类改动。

（说明：我没有读 java-test-plan 目录下的任何文件，以上是按自己的判断。）

## 验收条件（执行结果：未执行，本次不能运行 mvn）

1. 创建订单传 remark，落库后详情接口返回同样的值。
2. 创建订单不传 remark，创建成功，详情里 remark 为 null。
3. remark 超过 200 个字符，返回 400，不落库。
4. 老版本应用（不认识 remark 列）在新表上 insert/select 不受影响：列可空，无默认值依赖。

## 改了什么（outputs 目录当作项目根目录）

- src/main/resources/db/migration/V20261119_1__order_add_remark.sql：ADD COLUMN remark VARCHAR(200) NULL，注释里带回滚语句。
- Order、CreateOrderRequest（@Size(max = 200)）、OrderDetailResponse：各加 remark。
- OrderMapper.xml：insert 和 selectById 加 remark。
- OrderService：创建时写入 remark。
- OrderServiceTest：覆盖验收条件 1、2 的服务层部分，以及详情返回 remark。

## 需要你确认（我没有替你决定）

1. 真实项目的表名、包名、迁移脚本工具是我假设的（t_order、com.example.order、Flyway 风格脚本、MySQL 语法），和真实项目不一致的地方需要对一下。
2. remark 超长目前是校验失败返回 400。如果你希望截断，或者把空串、纯空白统一存成 null，请告诉我。
3. 只改了详情接口。订单列表、导出或其他查询如果也要带 remark，请告诉我。

## 没做 / 没查

- 没跑任何测试。
- 没有 pom 和启动类，因为你说没有别的改动。
- 验收条件 3、4 没有自动化测试覆盖：3 需要 WebMvcTest，4 需要上线前人工确认。
- 没写 Mapper 层集成测试（需要 H2 或 Testcontainers），所以 SQL 映射是否正确目前没有被验证过。
- 上线顺序：先执行 DDL，再发应用。
