import pandas as pd
import logging
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.responses import StreamingResponse, HTMLResponse
# 新增: 导入CORS中间件
from fastapi.middleware.cors import CORSMiddleware
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

# --- 新增：配置CORS ---
# 允许所有来源的跨域请求。在生产环境中应配置得更严格。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)


# --- 定义合并模式的枚举 ---
class MergeMode(str, Enum):
    OUTER = "outer"
    INNER = "inner"

# --- 辅助函数：从上传文件中读取DataFrame ---
async def _read_dataframe_from_uploadfile(file: UploadFile) -> pd.DataFrame | None:
    # ... (此函数无需改动) ...
    filename = file.filename.lower()
    try:
        content = await file.read()
        if not content:
            logger.warning(f"文件 '{filename}' 为空，已跳过。")
            return None
        file_bytes = BytesIO(content)
        if filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_bytes, engine="openpyxl")
        elif filename.endswith(".csv"):
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

# --- 前端UI界面 (JavaScript部分有重大更新) ---
@app.get("/", response_class=HTMLResponse)
def get_upload_form():
    return """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Excelab Pro - 智能表格合并</title>
        <style>
            /* ... (CSS样式无需改动) ... */
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
            #loader { display: none; margin-top: 20px; color: #555; font-weight: bold; }
            #error-message { display: none; margin-top: 20px; color: #d9534f; background-color: #f2dede; border: 1px solid #ebccd1; padding: 10px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Excelab Pro - 智能表格合并</h2>
            <form id="upload-form">
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
                <div id="error-message"></div>
            </form>
        </div>
        <script>
            const fileInput = document.getElementById('file-input');
            const fileList = document.getElementById('file-list');
            const submitButton = document.getElementById('submit-button');
            const form = document.getElementById('upload-form');
            const loader = document.getElementById('loader');
            const errorMessage = document.getElementById('error-message');

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

            // *** 核心改动：用异步函数替换原有的submit监听器 ***
            form.addEventListener('submit', async (event) => {
                event.preventDefault(); // 1. 阻止表单的默认提交行为

                // 2. 显示加载状态，隐藏按钮和旧的错误信息
                submitButton.style.display = 'none';
                errorMessage.style.display = 'none';
                loader.style.display = 'block';

                const formData = new FormData(form); // 3. 收集表单数据 (包括文件和选项)

                try {
                    // 4. 使用fetch API异步发送请求
                    const response = await fetch('/merge', {
                        method: 'POST',
                        body: formData,
                    });

                    // 5. 处理响应
                    if (response.ok) {
                        // 5a. 如果响应成功(200 OK)，则处理文件下载
                        if (response.headers.get('Content-Type').includes('sheet')) {
                            const blob = await response.blob(); // 获取文件内容的二进制对象
                            const url = window.URL.createObjectURL(blob); // 创建一个临时的URL
                            const a = document.createElement('a'); // 创建一个隐藏的下载链接
                            a.style.display = 'none';
                            a.href = url;
                            a.download = 'merged_pro.xlsx'; // 设置下载文件名
                            document.body.appendChild(a);
                            a.click(); // 模拟点击以下载
                            window.URL.revokeObjectURL(url); // 释放URL资源
                            a.remove();
                        }
                    } else {
                        // 5b. 如果服务器返回错误 (如 400, 500)
                        const errorData = await response.json(); // FastAPI的HTTPException会返回JSON
                        errorMessage.textContent = '错误: ' + (errorData.detail || '未知错误');
                        errorMessage.style.display = 'block';
                    }
                } catch (error) {
                    // 6. 处理网络错误等
                    errorMessage.textContent = '请求失败，请检查网络连接。';
                    errorMessage.style.display = 'block';
                } finally {
                    // 7. 无论成功或失败，最后都恢复UI到初始状态
                    loader.style.display = 'none';
                    submitButton.style.display = 'block';
                    // 可选：清空文件选择，让用户可以开始下一次操作
                    // fileInput.value = ''; 
                    // fileList.innerHTML = '';
                    // submitButton.disabled = true;
                }
            });
        </script>
    </body>
    </html>
    """

# --- 核心合并逻辑 (此函数无需改动) ---
@app.post("/merge")
async def merge_files(
    files: List[UploadFile] = File(...),
    merge_mode: MergeMode = Form(...)
):
    # ... (此函数无需改动) ...
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有提供任何文件。"
        )
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
    try:
        if merge_mode == MergeMode.OUTER:
            merged_df = pd.concat(dataframes, ignore_index=True, join='outer')
        elif merge_mode == MergeMode.INNER:
            common_columns = list(reduce(lambda x, y: x.intersection(y), [set(df.columns) for df in dataframes]))
            if not common_columns:
                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="所选文件之间没有任何共同的字段（列名），无法在'仅保留共同字段'模式下合并。"
                )
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
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        merged_df.to_excel(writer, sheet_name="Merged_Data", index=False)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=merged_pro.xlsx"}
    )