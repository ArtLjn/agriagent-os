-- 应用启动不自动建表；先迁移再发布。时间字段统一存 UTC。
CREATE TABLE memos (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  farm_id INT NOT NULL,
  user_id VARCHAR(36) NOT NULL,
  title VARCHAR(200) NOT NULL,
  content TEXT NOT NULL,
  pinned BOOLEAN NOT NULL DEFAULT FALSE,
  archived BOOLEAN NOT NULL DEFAULT FALSE,
  client_request_id VARCHAR(100) NOT NULL,
  request_fingerprint VARCHAR(64) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_memo_request (farm_id, user_id, client_request_id),
  KEY idx_memo_list (farm_id, user_id, archived, pinned, updated_at),
  CONSTRAINT fk_memo_farm FOREIGN KEY (farm_id) REFERENCES farms(id),
  CONSTRAINT fk_memo_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
