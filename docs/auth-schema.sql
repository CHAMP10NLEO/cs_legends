-- CS Legends · 账号相关增量 DDL（MySQL 8.0）
-- 用法（在项目根目录）：
--   mysql -h 127.0.0.1 -u root --default-character-set=utf8mb4 cs_legends < docs/auth-schema.sql
-- 说明：
--   1) 全部 CREATE TABLE IF NOT EXISTS，可重复执行；已灌数据的 cs_legends 库可直接跑。
--   2) 只做登录态：邮箱、用户名、密码哈希、角色、token_version（退出全部设备）。
--      暂不做邮箱验证 / 找回密码 / 收藏，后续需要时再加表。
--   3) 不写 DROP：账号数据比内容数据更该保住，重建请手工清理。

SET NAMES utf8mb4;

-- ---------------------------------------------------------------------------
-- 账号
-- 不用表名 `user`：MySQL 里 USER() 是函数，`app_user` 免歧义。
-- token_version 自增一次即可让该用户所有已签发 JWT 失效（退出全部设备 / 改密）。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_user (
  id            BIGINT UNSIGNED AUTO_INCREMENT,
  email         VARCHAR(160) NOT NULL,
  username      VARCHAR(32)  NOT NULL,
  password_hash VARCHAR(255) NOT NULL COMMENT 'argon2id，含算法与参数前缀',
  display_name  VARCHAR(64)  NULL,
  role          ENUM('user','admin') NOT NULL DEFAULT 'user',
  is_active     TINYINT(1)   NOT NULL DEFAULT 1,
  token_version INT UNSIGNED NOT NULL DEFAULT 0,
  last_login_at DATETIME     NULL,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_email (email),
  UNIQUE KEY uk_user_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='站点账号';

-- ---------------------------------------------------------------------------
-- refresh token
-- 只存 sha256(明文)；replaced_by 记录轮换链，旧 token 被重放时撤销整条链。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS refresh_token (
  id          BIGINT UNSIGNED AUTO_INCREMENT,
  user_id     BIGINT UNSIGNED NOT NULL,
  token_hash  CHAR(64) NOT NULL,
  issued_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at  DATETIME  NOT NULL,
  revoked_at  DATETIME  NULL,
  replaced_by CHAR(64)  NULL,
  user_agent  VARCHAR(200) NULL,
  ip          VARCHAR(45)  NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_refresh_hash (token_hash),
  KEY idx_refresh_user (user_id),
  CONSTRAINT fk_refresh_user FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='刷新令牌（哈希存储，轮换）';

-- ---------------------------------------------------------------------------
-- 登录尝试
-- 15 分钟内同一 identifier 或同一 IP 失败 5 次即 429；本表只用于判断，不做长期审计。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS login_attempt (
  id         BIGINT UNSIGNED AUTO_INCREMENT,
  identifier VARCHAR(160) NOT NULL COMMENT '邮箱或用户名，统一小写',
  ip         VARCHAR(45)  NOT NULL,
  success    TINYINT(1)   NOT NULL,
  created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_attempt_lookup (identifier, created_at),
  KEY idx_attempt_ip (ip, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='登录尝试（限流用）';
