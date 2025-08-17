# main.py
import pandas as pd
import logging
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, Query
from fastapi.responses import StreamingResponse, JSONResponse # 添加 JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from io import BytesIO
from typing import List, Optional
from enum import Enum
from functools import reduce
import json
import zipfile
import tempfile
import fitz  # PyMuPDF
import os
import sys
import re
import urllib.parse

# --- 配置与模型定义 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MergeMode(str, Enum):
    OUTER = "outer"
    INNER = "inner"

class CleanOptions(BaseModel):
    remove_empty_rows: bool = True
    remove_empty_cols: bool = True
    trim_spaces: bool = False

# --- FastAPI 应用实例 ---
app = FastAPI(
    title="Excelab Pro - Backend",
    description="为表格处理工具提供核心API服务。",
)

# --- 配置CORS (跨域资源共享) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 辅助函数 ---

def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    清理文件名，去掉非法字符，保留中文、英文、数字、常用符号。
    """
    # 去掉路径（防止上传带路径）
    filename = os.path.basename(filename)
    # 只保留中英文、数字、空格、下划线、连字符、点号
    filename = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff _\-.]", replacement, filename)
    # 避免空文件名
    if not filename.strip():
        filename = "file"
    return filename

async def process_uploaded_files(files: List[UploadFile]) -> List[pd.DataFrame]:
    """读取并解析上传的文件为 pandas DataFrame 列表。"""
    dataframes = []
    for file in files:

        # 文件名清理，防止非法字符
        clean_filename = sanitize_filename(file.filename)

        content = BytesIO(await file.read())
        filename = clean_filename.lower()
        df = None
        try:
            if filename.endswith((".xlsx", ".xls")):
                excel_file = pd.ExcelFile(content, engine='openpyxl')
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
        except Exception as e:
            logger.error(f"读取文件 {file.filename} 时出错: {e}",exc_info=True)
            raise HTTPException(status_code=400, detail=f"无法解析文件 {file.filename}: {str(e)}")
    if not dataframes:
        raise HTTPException(status_code=400, detail="上传的文件均无法解析或内容为空。")
    return dataframes

def merge_dataframes(dataframes: List[pd.DataFrame], mode: MergeMode) -> pd.DataFrame:
    """根据指定模式合并 DataFrame 列表。"""
    if mode == MergeMode.OUTER:
        merged_df = pd.concat(dataframes, ignore_index=True, sort=False) # sort=False to avoid FutureWarning
    else: # INNER
        if not dataframes:
             raise ValueError("没有数据帧可供合并。")
        common_columns = list(reduce(lambda x, y: x.intersection(y), [set(df.columns) for df in dataframes]))
        if not common_columns:
            raise ValueError("所选文件之间没有任何共同的字段。")
        # 只保留共同列并合并
        filtered_dfs = [df[common_columns] for df in dataframes]
        merged_df = pd.concat(filtered_dfs, ignore_index=True)
    return merged_df

def dataframe_to_excel_bytes(df: pd.DataFrame) -> BytesIO:
    """将 DataFrame 转换为 Excel 字节流。"""
    output = BytesIO()
    max_rows_per_sheet = 1_000_000

    if len(df) <= max_rows_per_sheet:
        df.to_excel(output, index=False, sheet_name="Merged_Data")
    else:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.iloc[:max_rows_per_sheet].to_excel(
                writer, index=False, sheet_name="Merged_Data_1"
            )
            for i in range(1, (len(df) // max_rows_per_sheet + 1)):
                start_idx = i * max_rows_per_sheet
                end_idx = (i + 1) * max_rows_per_sheet
                sheet_name = f"Merged_Data_{i+1}"
                df.iloc[start_idx:end_idx].to_excel(
                    writer, index=False, sheet_name=sheet_name
                )
    output.seek(0)
    return output

def clean_dataframe(df: pd.DataFrame, options: CleanOptions) -> pd.DataFrame:
    """根据选项清理 DataFrame。"""
    cleaned_df = df.copy()
    
    if options.remove_empty_rows:
        # 删除所有列都为空的行
        cleaned_df.dropna(how='all', inplace=True)
        # 重置索引
        cleaned_df.reset_index(drop=True, inplace=True)

    if options.remove_empty_cols:
        # 删除所有行都为空的列
        cleaned_df.dropna(axis=1, how='all', inplace=True)

    if options.trim_spaces:
        # 只对字符串列进行 strip 操作
        string_columns = cleaned_df.select_dtypes(include=['object']).columns
        cleaned_df[string_columns] = cleaned_df[string_columns].apply(lambda x: x.str.strip() if x.dtype == "object" else x)

    return cleaned_df

# --- API 端点 ---

@app.post("/api/merge")
async def merge_files_api(
    files: List[UploadFile] = File(...),
    merge_mode: MergeMode = Form(...)
):
    """
    接收上传的表格文件和合并模式，返回合并后的Excel文件。
    """
    if not files:
        raise HTTPException(status_code=400, detail="没有提供任何文件。")

    try:
        dataframes = await process_uploaded_files(files)
        merged_df = merge_dataframes(dataframes, merge_mode)
        output = dataframe_to_excel_bytes(merged_df)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise # Re-raise HTTPExceptions
    except Exception as e:
        logger.error(f"处理合并时发生未知错误: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}")

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=merged_pro.xlsx"}
    )

@app.post("/api/merge/preview")
async def merge_preview_api(
    files: List[UploadFile] = File(...),
    merge_mode: MergeMode = Form(...),
    preview_rows: int = Form(10) # 获取前N行用于预览
):
    """
    接收上传的表格文件和合并模式，返回合并后数据的JSON预览。
    """
    if not files:
        raise HTTPException(status_code=400, detail="没有提供任何文件。")

    try:
        dataframes = await process_uploaded_files(files)
        merged_df = merge_dataframes(dataframes, merge_mode)

        # 获取预览数据
        preview_df = merged_df.head(preview_rows)

        # 处理 NaN 值，因为 JSON 不能直接序列化 NaN
        # fillna(None) 会将 NaN 转换为 None，这在 JSON 中是 null
        preview_json = preview_df.fillna("").to_dict(orient='records')
        columns = preview_df.columns.tolist()

        return JSONResponse(content={
            "columns": columns,
            "data": preview_json,
            "total_rows": len(merged_df) # 可选：返回总行数
        })

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise # Re-raise HTTPExceptions
    except Exception as e:
        logger.error(f"处理预览时发生未知错误: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}")


@app.post("/api/split/columns")
async def get_split_columns(file: UploadFile = File(...)):
    """
    接收一个表格文件，返回其列名列表。
    """
    if not file:
        raise HTTPException(status_code=400, detail="没有提供文件。")

    try:
        content = BytesIO(await file.read())
        filename = file.filename.lower()
        df = None

        if filename.endswith((".xlsx", ".xls")):
            # 读取第一个 sheet
            excel_file = pd.ExcelFile(content, engine='openpyxl')
            df = excel_file.parse(excel_file.sheet_names[0])
        elif filename.endswith(".csv"):
            try:
                df = pd.read_csv(content)
            except UnicodeDecodeError:
                content.seek(0)
                df = pd.read_csv(content, encoding='gbk')
        
        if df is not None and not df.empty:
            # 确保列名是字符串类型，避免序列化问题
            columns = [str(col) for col in df.columns.tolist()]
            return JSONResponse(content={"columns": columns})
        else:
            raise HTTPException(status_code=400, detail="文件为空或无法解析。")

    except Exception as e:
        logger.error(f"获取列名时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"处理文件时出错: {e}")


@app.post("/api/split")
async def split_file_api(
    file: UploadFile = File(...),
    split_column: str = Form(...)
):
    """
    接收一个表格文件和拆分列名，返回包含拆分后文件的 ZIP 包。
    """
    if not file:
        raise HTTPException(status_code=400, detail="没有提供文件。")
    if not split_column:
         raise HTTPException(status_code=400, detail="没有提供拆分列名。")

    try:
        content = BytesIO(await file.read())
        filename = file.filename.lower()
        df = None

        if filename.endswith((".xlsx", ".xls")):
            excel_file = pd.ExcelFile(content, engine='openpyxl')
            df = excel_file.parse(excel_file.sheet_names[0]) # 通常拆分第一个sheet
        elif filename.endswith(".csv"):
            try:
                df = pd.read_csv(content)
            except UnicodeDecodeError:
                content.seek(0)
                df = pd.read_csv(content, encoding='gbk')

        if df is None or df.empty:
            raise HTTPException(status_code=400, detail="文件为空或无法解析。")

        if split_column not in df.columns:
            raise HTTPException(status_code=400, detail=f"指定的拆分列 '{split_column}' 在文件中不存在。")

        # --- 执行拆分 ---
        # 按 split_column 分组
        grouped = df.groupby(split_column, sort=False) # sort=False 保持原始顺序

        if grouped.ngroups == 0:
             raise HTTPException(status_code=400, detail="根据指定列拆分后没有产生任何组。")

        # --- 创建 ZIP 文件 ---
        # 使用 tempfile.TemporaryDirectory 确保临时文件被自动清理
        with tempfile.TemporaryDirectory() as tmpdirname:
            zip_filename = "split_files.zip"
            zip_path = os.path.join(tmpdirname, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for name, group in grouped:
                    # 处理分组名，避免文件名中的非法字符
                    safe_name = str(name).replace('/', '_').replace('\\', '_').replace(':', '_')
                    # 简单截断长文件名，防止文件系统问题
                    safe_name = safe_name[:50] 
                    
                    # 为每个组创建一个临时的 Excel 文件
                    group_filename = f"{safe_name}_split.xlsx"
                    group_path = os.path.join(tmpdirname, group_filename)
                    
                    # 保存分组数据到临时Excel文件
                    group.to_excel(group_path, index=False, sheet_name=safe_name[:31]) # Sheet名限制31字符
                    
                    # 将临时Excel文件添加到ZIP中
                    zipf.write(group_path, arcname=group_filename)
                    # 临时文件会在 with tempfile.TemporaryDirectory 退出时自动删除

            # 读取生成的 ZIP 文件内容
            with open(zip_path, 'rb') as f:
                zip_content = f.read()

        # 返回 ZIP 文件
        zip_bytes_io = BytesIO(zip_content)
        zip_bytes_io.seek(0)

        return StreamingResponse(
            zip_bytes_io,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )

    except HTTPException:
        raise # Re-raise HTTPExceptions
    except Exception as e:
        logger.error(f"拆分文件时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}")

@app.post("/api/clean/preview")
async def clean_preview_api(
    file: UploadFile = File(...),
    remove_empty_rows: bool = Form(True),
    remove_empty_cols: bool = Form(True),
    trim_spaces: bool = Form(False),
    preview_rows: int = Form(5) # 获取前N行用于预览
):
    """
    接收一个表格文件和清理选项，返回清理预览（统计信息和前几行数据）。
    """
    if not file:
        raise HTTPException(status_code=400, detail="没有提供文件。")

    try:
        content = BytesIO(await file.read())
        filename = file.filename.lower()
        df_original = None

        if filename.endswith((".xlsx", ".xls")):
            excel_file = pd.ExcelFile(content, engine='openpyxl')
            df_original = excel_file.parse(excel_file.sheet_names[0]) # 通常处理第一个sheet
        elif filename.endswith(".csv"):
            try:
                df_original = pd.read_csv(content)
            except UnicodeDecodeError:
                content.seek(0)
                df_original = pd.read_csv(content, encoding='gbk')

        if df_original is None or df_original.empty:
            raise HTTPException(status_code=400, detail="文件为空或无法解析。")

        original_rows, original_cols = df_original.shape
        
        # 应用清理选项
        options = CleanOptions(
            remove_empty_rows=remove_empty_rows,
            remove_empty_cols=remove_empty_cols,
            trim_spaces=trim_spaces
        )
        df_cleaned = clean_dataframe(df_original, options)
        
        cleaned_rows, cleaned_cols = df_cleaned.shape

        # 获取预览数据 (清理后的)
        preview_df = df_cleaned.head(preview_rows)
        preview_json = preview_df.fillna("").to_dict(orient='records')
        columns = preview_df.columns.tolist()

        return JSONResponse(content={
            "original_rows": original_rows,
            "original_cols": original_cols,
            "cleaned_rows": cleaned_rows,
            "cleaned_cols": cleaned_cols,
            "preview_columns": columns,
            "preview_data": preview_json,
            "actions": [k for k, v in options.dict().items() if v] # 返回执行了哪些操作
        })

    except HTTPException:
        raise # Re-raise HTTPExceptions
    except Exception as e:
        logger.error(f"生成清理预览时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}")


@app.post("/api/clean")
async def clean_file_api(
    file: UploadFile = File(...),
    remove_empty_rows: bool = Form(True),
    remove_empty_cols: bool = Form(True),
    trim_spaces: bool = Form(False)
):
    """
    接收一个表格文件和清理选项，返回清理后的文件。
    """
    if not file:
        raise HTTPException(status_code=400, detail="没有提供文件。")

    try:
        content = BytesIO(await file.read())
        filename = file.filename.lower()
        df_original = None

        if filename.endswith((".xlsx", ".xls")):
            excel_file = pd.ExcelFile(content, engine='openpyxl')
            df_original = excel_file.parse(excel_file.sheet_names[0])
        elif filename.endswith(".csv"):
            try:
                df_original = pd.read_csv(content)
            except UnicodeDecodeError:
                content.seek(0)
                df_original = pd.read_csv(content, encoding='gbk')

        if df_original is None or df_original.empty:
            raise HTTPException(status_code=400, detail="文件为空或无法解析。")

        # 应用清理选项
        options = CleanOptions(
            remove_empty_rows=remove_empty_rows,
            remove_empty_cols=remove_empty_cols,
            trim_spaces=trim_spaces
        )
        df_cleaned = clean_dataframe(df_original, options)

        # 将清理后的 DataFrame 导出为 Excel 字节流
        output = dataframe_to_excel_bytes(df_cleaned) # 复用之前定义的函数

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=cleaned_data.xlsx"}
        )

    except HTTPException:
        raise # Re-raise HTTPExceptions
    except Exception as e:
        logger.error(f"清理文件时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}")


@app.post("/api/pdf-to-images")
async def pdf_to_images(
    file: UploadFile = File(..., description="PDF 文件"),
    format: str = Form(..., description="图片格式，png 或 jpeg"),
    dpi: int = Form(150, description="图片 DPI"),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="上传的文件必须是 PDF 格式。")

    if format.lower() not in ["png", "jpeg"]:
        raise HTTPException(status_code=400, detail="图片格式必须是 png 或 jpeg。")

    try:
        pdf_bytes = await file.read()
        pdf_stream = BytesIO(pdf_bytes)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=dpi)
                img_bytes = pix.tobytes(output=format)
                img_filename = f"page_{page_num+1}.{format.lower()}"
                zip_file.writestr(img_filename, img_bytes)

        zip_buffer.seek(0)
        doc.close()

        # 清理文件名
        original_filename_no_ext = sanitize_filename(file.filename.rsplit(".", 1)[0])
        zip_filename = f"{original_filename_no_ext}_images.zip"

        # Content-Disposition 安全处理
        safe_ascii_name = "converted_images.zip"
        quoted_name = urllib.parse.quote(zip_filename)

        headers = {
            "Content-Disposition": f"attachment; filename={safe_ascii_name}; filename*=UTF-8''{quoted_name}"
        }

        return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)

    except Exception as e:
        logger.error(f"PDF 转换失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF 转换失败: {str(e)}")

# PDF合并相关的导入和代码

@app.post("/api/pdfmerge/preview")
async def pdfmerge_preview_api(
    files: List[UploadFile] = File(...),
    merge_options: List[str] = Form(default=[])
):
    """
    PDF合并预览接口，返回合并后的统计信息
    """
    if not files:
        raise HTTPException(status_code=400, detail="没有提供文件。")
    
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="至少需要上传两个PDF文件才能合并。")

    try:
        total_pages = 0
        total_size = 0
        
        # 验证文件并计算统计信息
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail=f"文件 {file.filename} 不是PDF格式。")
            
            # 读取文件内容计算大小
            content = await file.read()
            total_size += len(content)
            
            # 计算页数
            pdf_document = fitz.open(stream=content, filetype="pdf")
            total_pages += pdf_document.page_count
            pdf_document.close()
            
            # 重置文件指针
            await file.seek(0)
        
        # 如果选择了添加空白页选项，需要额外计算
        if "add_blank_page" in merge_options and len(files) > 1:
            # 在文件之间添加空白页，n个文件需要n-1个空白页
            total_pages += (len(files) - 1)
        
        # 如果选择了添加目录页选项
        if "add_toc" in merge_options:
            total_pages += 1  # 添加一个目录页
        
        return JSONResponse(content={
            "total_pages": total_pages,
            "total_size": total_size,
            "actions": merge_options
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF合并预览时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}")


@app.post("/api/pdfmerge")
async def pdfmerge_api(
    files: List[UploadFile] = File(...),
    merge_options: List[str] = Form(default=[])
):
    """
    PDF合并接口，返回合并后的PDF文件
    """
    if not files:
        raise HTTPException(status_code=400, detail="没有提供文件。")
    
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="至少需要上传两个PDF文件才能合并。")

    try:
        # 创建一个新的PDF文档用于合并
        merged_pdf = fitz.open()
        
        # 如果选择了添加目录页选项，先添加目录页
        if "add_toc" in merge_options:
            toc_page = merged_pdf.new_page()
            # 添加目录标题
            toc_page.insert_text((50, 50), "目录", fontsize=20, color=(0, 0, 0))
            y_position = 100
            
            # 添加各个文件的条目
            for i, file in enumerate(files):
                filename = sanitize_filename(file.filename)
                toc_page.insert_text((70, y_position), f"{i+1}. {filename}", fontsize=12, color=(0, 0, 0))
                y_position += 20

        # 逐个处理每个PDF文件
        for i, file in enumerate(files):
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail=f"文件 {file.filename} 不是PDF格式。")
            
            # 读取文件内容
            content = await file.read()
            
            # 打开PDF文件
            pdf_document = fitz.open(stream=content, filetype="pdf")
            
            # 将所有页面插入到合并的PDF中
            merged_pdf.insert_pdf(pdf_document)
            
            # 关闭当前PDF文件
            pdf_document.close()
            
            # 如果选择了添加空白页选项，且不是最后一个文件，则添加空白页
            if "add_blank_page" in merge_options and i < len(files) - 1:
                blank_page = merged_pdf.new_page()
                # 可以在空白页上添加"分页"文字（可选）
                # blank_page.insert_text((50, 50), "分页", fontsize=12, color=(0.5, 0.5, 0.5))

        # 将合并后的PDF保存到内存中
        output_buffer = BytesIO()
        merged_pdf.save(output_buffer)
        merged_pdf.close()
        
        # 重置缓冲区指针
        output_buffer.seek(0)
        
        # 生成文件名
        merged_filename = "merged_pdf.pdf"
        
        return StreamingResponse(
            output_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={merged_filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF合并时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}")

@app.get("/health")
def health_check():
    """健康检查端点，用于确认后端服务是否运行正常。"""
    return {"status": "ok"}

# 在 backend/main.py 中添加一个简单的测试路由
@app.post("/api/test")
async def test_post():
    return {
        "message": "POST request successful",
        "python_executable": sys.executable,
        "python_path": sys.path,
        "current_working_directory": os.getcwd(),
        "environment_variables": dict(os.environ)
    }

# --- 挂载前端静态文件 ---
# 假设你的项目根目录结构如上所示
# 获取当前文件 (main.py) 的目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 构造 frontend 目录的路径
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# 检查 frontend 目录是否存在
if os.path.isdir(FRONTEND_DIR):
    # 挂载 frontend 目录到根路径 "/"
    # 这意味着访问 http://127.0.0.1:8000/ 将会返回 frontend/index.html
    # 访问 http://127.0.0.1:8000/style.css 将会返回 frontend/style.css
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    # 如果没有 frontend 目录，可以简单地返回一个提示信息
    @app.get("/")
    def read_root():
        return {"message": "Frontend directory not found. Please ensure the 'frontend' folder exists at the project root."}
# --- 挂载结束 ---

# --- 运行服务 ---
# 使用命令行运行: uvicorn main:app --reload