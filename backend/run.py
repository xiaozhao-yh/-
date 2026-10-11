"""后端启动入口：python run.py  （API 地址 http://localhost:8000）"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
