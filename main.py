import pandas as pd
import logging
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.responses import StreamingResponse, HTMLResponse
from io import BytesIO
from typing import List
from enum import Enum
from functools import reduce

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 初始化FastAPI应用 ---
app = FastAPI(
    title="Excelab Pro",
    description="一个智能的表格合并工具，支持多种合并策略和更友好的用户界面。",
)

# --- 定义合并模式的枚举 ---
class MergeMode(str, Enum):
    OUTER = "outer"  # 保留所有列，缺失值填空
    INNER = "inner"  # 仅保留公共列

# --- 辅助函数：从上传文件中读取DataFrame ---
async def _read_dataframe_from_uploadfile(file: UploadFile) -> pd.DataFrame | None:
    """从UploadFile对象中安全地读取DataFrame，支持xlsx, xls, csv格式。"""
    filename = file.filename.lower()
    try:
        content = await file.read()
        if not content:
            logger.warning(f"文件 '{filename}' 为空，已跳过。")
            return None

        file_bytes = BytesIO(content)

        if filename.endswith((".xlsx", ".xls")):
            # 为了简化，我们默认只读取第一个工作表
            # 如果需要合并多工作表，逻辑会更复杂
            df = pd.read_excel(file_bytes, engine="openpyxl")
        elif filename.endswith(".csv"):
            # 尝试使用不同的编码格式以提高兼容性
            try:
                df = pd.read_csv(file_bytes)
            except UnicodeDecodeError:
                file_bytes.seek(0)
                df = pd.read_csv(file_bytes, encoding='gbk')
        else:
            logger.warning(f"不支持的文件格式: '{filename}'，已跳过。")
            return None
        
        if df.empty:
            logger.warning(f"文件 '{filename}' 读取后数据为空，已跳过。")
            return None

        logger.info(f"成功读取并解析文件: '{filename}'")
        return df

    except Exception as e:
        logger.error(f"处理文件 '{filename}' 时发生错误: {e}")
        return None

# --- 前端UI界面 ---
@app.get("/", response_class=HTMLResponse)
def get_upload_form():
    """提供一个现代化、交互友好的文件上传界面。"""
    return """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Excelab Pro - 智能表格合并</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f4f7f6; }
            .container { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); text-align: center; width: 90%; max-width: 500px; }
            h2 { color: #333; margin-bottom: 20px; }
            .file-upload-wrapper { border: 2px dashed #007bff; padding: 20px; border-radius: 8px; cursor: pointer; position: relative; }
            .file-upload-wrapper:hover { border-color: #0056b3; }
            .file-upload-wrapper input[type="file"] { position: absolute; left: 0; top: 0; opacity: 0; width: 100%; height: 100%; cursor: pointer; }
            .file-upload-label { color: #007bff; font-weight: bold; }
            #file-list { margin-top: 20px; text-align: left; max-height: 150px; overflow-y: auto; background: #f9f9f9; padding: 10px; border-radius: 4px; }
            #file-list div { padding: 5px; border-bottom: 1px solid #eee; }
            .options { margin: 20px 0; text-align: left; }
            .options label { margin-right: 15px; }
            .submit-btn { background-color: #28a745; color: white; padding: 12px 20px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; width: 100%; transition: background-color 0.3s; }
            .submit-btn:hover { background-color: #218838; }
            .submit-btn:disabled { background-color: #ccc; cursor: not-allowed; }
            #loader { display: none; margin-top: 20px; color: #555; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Excelab Pro - 智能表格合并</h2>
            <form id="upload-form" action="/merge" method="post" enctype="multipart/form-data">
                <div class="file-upload-wrapper">
                    <span class="file-upload-label">点击或拖拽文件到此处</span>
                    <input type="file" name="files" id="file-input" multiple required>
                </div>
                <div id="file-list"></div>

                <div class="options">
                    <h4>合并模式</h4>
                    <label>
                        <input type="radio" name="merge_mode" value="outer" checked>
                        保留所有字段 (缺失处填空)
                    </label>
                    <label>
                        <input type="radio" name="merge_mode" value="inner">
                        仅保留共同字段
                    </label>
                </div>

                <button type="submit" class="submit-btn" id="submit-button" disabled>上传并合并</button>
                <div id="loader">正在处理，请稍候...</div>
            </form>
        </div>
        <script>
            const fileInput = document.getElementById('file-input');
            const fileList = document.getElementById('file-list');
            const submitButton = document.getElementById('submit-button');
            const form = document.getElementById('upload-form');
            const loader = document.getElementById('loader');

            fileInput.addEventListener('change', () => {
                fileList.innerHTML = '';
                if (fileInput.files.length > 0) {
                    for (const file of fileInput.files) {
                        const fileItem = document.createElement('div');
                        fileItem.textContent = file.name;
                        fileList.appendChild(fileItem);
                    }
                    submitButton.disabled = false;
                } else {
                    submitButton.disabled = true;
                }
            });

            form.addEventListener('submit', () => {
                submitButton.style.display = 'none';
                loader.style.display = 'block';
            });
        </script>
    </body>
    </html>
    """

# --- 核心合并逻辑 ---
@app.post("/merge")
async def merge_files(
    files: List[UploadFile] = File(...),
    merge_mode: MergeMode = Form(...)
):
    """接收文件和合并模式，执行合并并返回结果。"""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有提供任何文件。"
        )

    # 1. 异步读取所有文件到DataFrame列表
    dataframes = []
    for file in files:
        df = await _read_dataframe_from_uploadfile(file)
        if df is not None:
            dataframes.append(df)

    if not dataframes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传的文件均无法解析或内容为空，请检查文件格式和内容。"
        )
    
    logger.info(f"成功读取 {len(dataframes)} 个文件。合并模式: {merge_mode.value}")

    # 2. 根据合并模式执行合并
    try:
        if merge_mode == MergeMode.OUTER:
            # outer模式：保留所有列，Pandas concat默认行为
            merged_df = pd.concat(dataframes, ignore_index=True, join='outer')

        elif merge_mode == MergeMode.INNER:
            # inner模式：仅保留所有文件的共同列
            # 计算所有DataFrame列名的交集
            common_columns = list(reduce(lambda x, y: x.intersection(y), [set(df.columns) for df in dataframes]))
            
            if not common_columns:
                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="所选文件之间没有任何共同的字段（列名），无法在'仅保留共同字段'模式下合并。"
                )
            
            # 使用共同列进行concat
            merged_df = pd.concat(
                [df[common_columns] for df in dataframes],
                ignore_index=True
            )
        
        logger.info(f"合并完成。最终表格尺寸: {merged_df.shape}")

    except Exception as e:
        logger.error(f"合并DataFrame时发生错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"在服务器端合并数据时发生错误: {e}"
        )


    # 3. 将合并结果写入内存中的Excel文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        merged_df.to_excel(writer, sheet_name="Merged_Data", index=False)
    
    output.seek(0)

    # 4. 以流式响应返回文件
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=merged_pro.xlsx"}
    )