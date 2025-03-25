from app.core.database import Base, engine, SessionLocal
from app.core.config import settings
from app.core.security import get_password_hash
import os

def init_db():
    """
    初始化数据库
    """
    # 创建表
    Base.metadata.create_all(bind=engine)
    
    # 创建目录
    if not os.path.exists(settings.PLUGIN_DIR):
        os.makedirs(settings.PLUGIN_DIR)
    
    if not os.path.exists(settings.TEMP_DIR):
        os.makedirs(settings.TEMP_DIR)
    
    # 这里可以添加初始数据，比如默认标签等
    # db = SessionLocal()
    # try:
    #     # 添加初始数据
    #     pass
    # finally:
    #     db.close()

if __name__ == "__main__":
    init_db()
    print("数据库初始化完成") 