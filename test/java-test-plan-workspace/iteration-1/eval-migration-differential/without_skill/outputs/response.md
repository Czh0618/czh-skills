测试计划已出，共两份文档。没有真实代码可读，盘点表目前只是排查清单。

产出文件
- /Users/chenzhihua/person_code/czh-skills/test/java-test-plan-workspace/iteration-1/eval-migration-differential/without_skill/outputs/docs/test-plan/order-list-migration-test-plan.md：目标与思路、阶段计划 P0 到 P7、回放设计、日志之外的补充用例、退出标准、待确认问题
- /Users/chenzhihua/person_code/czh-skills/test/java-test-plan-workspace/iteration-1/eval-migration-differential/without_skill/outputs/docs/test-plan/order-list-diff-rules.md：行为盘点排查清单、差异分级与处置、比对规则、覆盖度度量

核心思路
1. 老实现就是验收标准，用差分测试：同一请求、同一份数据快照，新旧各跑一次逐字段比对（含顺序、total、异常响应），不另写预期值。
2. 比的是老实现在同一快照上现跑的结果，不是日志里的历史响应，因为数据早已变化。
3. 日志只能覆盖出现过的请求，所以另有补充用例覆盖日志没触发的分支和数据边界，并用老实现实际执行的 SQL 条件片段统计分支覆盖。日志窗口之外的季节性行为单独列为风险。
4. 最容易出差异的地方：MyBatis 插件或拦截器里追加的数据权限、租户、逻辑删除条件；`<if test>` 对 0 和空串的判断；排序并列时的顺序；一对多 join 与分页；IN 空列表等异常出口。

需要你回答（我停在这里，没有替你决定）
1. 日志有哪些字段？有没有用户、租户、角色身份，请求时间，历史响应？是 access log 还是应用层请求日志，有无请求体？（阻塞 P0）
2. 回放环境：能拿到脱敏的生产库副本，还是只能在生产上做只读影子比对？（阻塞 P2）
3. 同跑方式：同一进程内用开关调用新旧两个实现，还是两套实例各自回放再比对？我倾向前者，需要你确认。
4. 回放发现老行为本身是 bug（比如 status=0 被当成没传）时，新实现先保持一致、修正另行发版，还是迁移时一并修？我倾向先一致，由你拍板。
5. 排序键并列时老实现的顺序本来就不稳定，这类顺序差异算不算缺陷？
6. 性能阈值（p95、SQL 条数）、影子期时长、样本量。
7. 真实代码在哪个目录？拿到后才能把盘点表填实。

没做的：没读任何真实代码和日志，没跑 mvn，没写回放比对器代码，只出了计划。
风险：日志窗口之外的低频行为（季度、年度活动）回放覆盖不到，需要业务方补充清单。
