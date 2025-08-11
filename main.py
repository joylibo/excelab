from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse, HTMLResponse
import pandas as pd
from io import BytesIO
from typing import List
import os

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def upload_form():
    return """
    <html>
        <body>
            <h2>Excelab - 表格合并工具</h2>
            <form action="/merge" method="post" enctype="multipart/form-data">
                <input type="file" name="files" multiple>
                <input type="submit" value="上传并合并">
            </form>
        </body>
    </html>
    """

@app.post("/merge")
async def merge_excel(files: List[UploadFile] = File(...)):
    sheets_dict = {}

    for file in files:
        filename = file.filename.lower()
        file_bytes = await file.read()

        if filename.endswith((".xlsx", ".xls")):
            xls = pd.ExcelFile(BytesIO(file_bytes), engine="openpyxl")
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, engine="openpyxl")
                if df.empty:
                    continue
                header_tuple = tuple(sorted(df.columns))
                sheets_dict.setdefault(header_tuple, []).append(df)

        elif filename.endswith(".csv"):
            df = pd.read_csv(BytesIO(file_bytes))
            if df.empty:
                continue
            header_tuple = tuple(sorted(df.columns))
            sheets_dict.setdefault(header_tuple, []).append(df)

        else:
            # 忽略不支持的格式
            continue

    # 合并结果写入内存
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for i, (header_tuple, dfs) in enumerate(sheets_dict.items(), start=1):
            merged_df = pd.concat(dfs, ignore_index=True)
            merged_df = merged_df[list(sorted(header_tuple))]
            merged_df.to_excel(writer, sheet_name=f"Group_{i}", index=False)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=merged.xlsx"}
    )
