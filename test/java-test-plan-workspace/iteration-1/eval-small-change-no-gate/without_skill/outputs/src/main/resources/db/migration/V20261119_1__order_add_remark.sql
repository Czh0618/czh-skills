-- Additive and nullable: old app versions keep working during a rolling deploy.
-- Rollback: ALTER TABLE t_order DROP COLUMN remark;
ALTER TABLE t_order ADD COLUMN remark VARCHAR(200) NULL COMMENT '备注';
