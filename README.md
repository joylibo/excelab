# 手边工具箱 (Excelab)

手边工具箱是一个综合性的文件处理工具，提供表格、文档和图片处理功能，帮助用户高效处理各类文件。

## 主要功能

### 表格处理
- **表格合并**：支持多个Excel/CSV文件合并，可选择保留所有列或仅保留共同列
- **表格拆分**：根据指定列将表格拆分为多个文件
- **表格清理**：支持删除空行、空列，清除单元格前后空格

### 文档处理
- **PDF转图片**：将PDF文档转换为图片格式
- **PDF合并**：合并多个PDF文件

### 图片处理
- 提供多种图片处理功能

## 部署指南

### 环境准备
```
conda create --name excelab311 python=3.11
conda activate excelab311
```

### 克隆项目
```
git clone <项目仓库地址>
cd excelab
```

## 运行指南
你需要同时运行前端和后端两个服务。

### 启动后端服务

打开一个终端，进入 backend 目录。

安装依赖: 
```
pip install -r requirements.txt
```

或者使用conda安装基础依赖：
```
conda install -c conda-forge uvicorn fastapi pydantic pandas
conda install -c conda-forge pymupdf  # 用于PDF处理
```

启动开发服务器: 
```
uvicorn main:app --reload --port 8001
```

生产环境启动命令:
```
nohup uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4 > uvicorn.log 2>&1 &
```

后端服务运行在 http://127.0.0.1:8001

### 启动前端服务

可以使用任何静态文件服务器来提供前端文件。例如，使用Python的内置HTTP服务器：

```
cd frontend
python -m http.server 8080
```

### 访问应用

在浏览器中打开前端地址： http://127.0.0.1:8080

现在，你在页面上进行的操作会通过API调用后端服务，完成各种文件处理功能。