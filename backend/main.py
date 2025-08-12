import pandas as pd
import logging
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware # CORS是关键
from io import BytesIO
from typing import List
from enum import Enum
from functools import reduce

# --- 配置与模型定义 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MergeMode(str, Enum):
    OUTER = "outer"
    INNER = "inner"

# --- FastAPI 应用实例 ---
app = FastAPI(
    title="Excelab Pro - Backend",
    description="为表格处理工具提供核心API服务。",
)

# --- 配置CORS (跨域资源共享) ---
# 这是前后端分离后必须的步骤，允许前端(不同源)调用后端API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产中应设为你的前端域名，例如 ["http://localhost:8080"]
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
)

# --- API 端点 ---
@app.post("/api/merge") # 建议给API加上/api前缀
async def merge_files_api(
    files: List[UploadFile] = File(...),
    merge_mode: MergeMode = Form(...)
):
    """
    接收上传的表格文件和合并模式，返回合并后的Excel文件。
    """
    if not files:
        raise HTTPException(status_code=400, detail="没有提供任何文件。")

    # --- 核心业务逻辑 ---
    # (这部分逻辑可以保持原样，或者未来也可以再拆分到services.py中)
    try:
        dataframes = []
        for file in files:
            content = BytesIO(await file.read())
            filename = file.filename.lower()
            
            if filename.endswith((".xlsx", ".xls")):
                # 读取所有 sheet
                excel_file = pd.ExcelFile(content)
                for sheet_name in excel_file.sheet_names:
                    df = excel_file.parse(sheet_name)
                    if not df.empty:
                        dataframes.append(df)
            
            elif filename.endswith(".csv"):
                try:
                    df = pd.read_csv(content)
                except UnicodeDecodeError:
                    content.seek(0)
                    df = pd.read_csv(content, encoding='gbk')
                if not df.empty:
                    dataframes.append(df)

        if not dataframes:
            raise HTTPException(status_code=400, detail="上传的文件均无法解析或内容为空。")

        if merge_mode == MergeMode.OUTER:
            merged_df = pd.concat(dataframes, ignore_index=True, join='outer')
        else: # INNER
            common_columns = list(reduce(lambda x, y: x.intersection(y), [set(df.columns) for df in dataframes]))
            if not common_columns:
                raise ValueError("所选文件之间没有任何共同的字段。")
            merged_df = pd.concat([df[common_columns] for df in dataframes], ignore_index=True)

        output = BytesIO()
        
                # 优化后的导出逻辑 - 自动分割大数据集
        max_rows_per_sheet = 1_000_000  # 每个工作表最大行数
        
        if len(merged_df) <= max_rows_per_sheet:
            merged_df.to_excel(output, index=False, sheet_name="Merged_Data")
        else:
            with pd.ExcelWriter(output) as writer:
                # 第一个工作表包含前1,000,000行
                merged_df.iloc[:max_rows_per_sheet].to_excel(
                    writer, index=False, sheet_name="Merged_Data_1"
                )
                
                # 剩余数据分割到其他工作表
                for i in range(1, (len(merged_df) // max_rows_per_sheet + 1)):
                    start_idx = i * max_rows_per_sheet
                    end_idx = (i + 1) * max_rows_per_sheet
                    sheet_name = f"Merged_Data_{i+1}"
                    merged_df.iloc[start_idx:end_idx].to_excel(
                        writer, index=False, sheet_name=sheet_name
                    )

        output.seek(0)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"处理合并时发生未知错误: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}")
    # --- 业务逻辑结束 ---

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=merged_pro.xlsx"}
    )

@app.get("/health")
def health_check():
    """健康检查端点，用于确认后端服务是否运行正常。"""
    return {"status": "ok"}