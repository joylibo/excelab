# simple_test.py
import pandas as pd
from io import BytesIO
import traceback

print("Python版本:", __import__('sys').version)
print("Pandas版本:", pd.__version__)

try:
    import openpyxl
    print("Openpyxl版本:", openpyxl.__version__)
except ImportError:
    print("❌ 未安装openpyxl")

# 测试文件
filename = "./文件1.xlsx"

print(f"\n测试读取文件: {filename}")

try:
    # 测试1: 直接读取
    print("\n--- 测试1: 直接读取 ---")
    df = pd.read_excel(filename, engine='openpyxl')
    print(f"✅ 直接读取成功! 形状: {df.shape}")
    
    # 测试2: 模拟上传方式
    print("\n--- 测试2: 模拟上传方式 ---")
    with open(filename, 'rb') as f:
        content = BytesIO(f.read())
    
    excel_file = pd.ExcelFile(content)
    print(f"✅ ExcelFile创建成功! 工作表: {excel_file.sheet_names}")
    
    for sheet in excel_file.sheet_names:
        df = excel_file.parse(sheet)
        print(f"  工作表'{sheet}': {df.shape}")
        
    print("\n🎉 所有测试通过!")
    
except Exception as e:
    print(f"❌ 错误: {e}")
    print("\n详细错误信息:")
    traceback.print_exc()