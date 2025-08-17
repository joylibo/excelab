Excelab是一个帮助用户处理Excel文件的小工具

## 部署
### 环境准备
```
conda create --name excelab311 python=3.11
conda activate excelab311
```

### clone 本项目


## 运行
你需要同时运行两个服务，这在开发中非常常见。

### 启动后端服务

打开一个终端，进入 backend 目录。

安装依赖: 
```
pip install -r requirements.txt
```
基础依赖：
```
conda install -c conda-forge uvicorn
conda install -c conda-forge fastapi
conda install -c conda-forge pydantic
conda install -c conda-forge sqlmodel
conda install -c conda-forge pandas
```

启动服务器: 
```
uvicorn main:app --reload --port 8001
```

服务端运行时候用:
```
nohup uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4 > uvicorn.log 2>&1 &
```

后端现在运行在 http://127.0.0.1:8001。


### 访问应用:

在浏览器中打开前端地址： http://127.0.0.1:8080。

现在，你在页面上进行的操作会通过 fetch 调用运行在 8000 端口的后端服务，并通过 CORS 配置被允许，从而完成整个流程。