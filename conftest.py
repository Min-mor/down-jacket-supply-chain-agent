"""pytest 根配置：在导入任何业务模块前，统一设置测试环境。

- 使用独立的临时 SQLite 测试库，避免污染 data/agent.db
- 强制规则模式、固定网关令牌、放宽限流
"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("API_TOKEN", "test-secret")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")
os.environ.setdefault("ENV", "test")
