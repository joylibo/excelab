# test_excel_environment.py
import pandas as pd
import logging
from io import BytesIO
import sys
import os

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_excel_reading():
    """测试Excel文件读取功能"""
    
    # 打印环境信息
    logger.info("=== 环境信息 ===")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"Pandas版本: {pd.__version__}")
    
    try:
        import openpyxl
        logger.info(f"Openpyxl版本: {openpyxl.__version__}")
    except ImportError:
        logger.error("未安装openpyxl")
        return False
        
    try:
        import xlrd
        logger.info(f"Xlrd版本: {xlrd.__version__}")
    except ImportError:
        logger.warning("未安装xlrd（读取.xls文件需要）")
    
    # 检查文件是否存在
    test_file = "./文件1.xlsx"
    if not os.path.exists(test_file):
        logger.error(f"测试文件不存在: {test_file}")
        logger.info("请确保在项目目录下放置一个名为'文件1.xlsx'的Excel文件")
        return False
    
    logger.info(f"找到测试文件: {test_file}")
    logger.info(f"文件大小: {os.path.getsize(test_file)} bytes")
    
    try:
        # 方法1: 直接读取文件
        logger.info("=== 测试方法1: 直接pd.read_excel ===")
        df1 = pd.read_excel(test_file, sheet_name=0)
        logger.info(f"直接读取成功，形状: {df1.shape}")
        logger.info(f"列名: {list(df1.columns)}")
        logger.info(f"前3行:\n{df1.head(3)}")
        
        # 方法2: 使用ExcelFile（模拟项目中的方式）
        logger.info("=== 测试方法2: 使用pd.ExcelFile ===")
        with open(test_file, 'rb') as f:
            content = BytesIO(f.read())
        
        excel_file = pd.ExcelFile(content)
        logger.info(f"Excel文件工作表: {excel_file.sheet_names}")
        
        dataframes = []
        for sheet_name in excel_file.sheet_names:
            logger.info(f"读取工作表: {sheet_name}")
            df = excel_file.parse(sheet_name)
            if not df.empty:
                dataframes.append(df)
                logger.info(f"  工作表'{sheet_name}'读取成功，形状: {df.shape}")
            else:
                logger.warning(f"  工作表'{sheet_name}'为空")
        
        if dataframes:
            logger.info(f"总共读取了 {len(dataframes)} 个工作表")
            # 测试合并
            if len(dataframes) > 1:
                merged_df = pd.concat(dataframes, ignore_index=True)
                logger.info(f"合并后总形状: {merged_df.shape}")
        else:
            logger.warning("没有读取到任何数据")
            
        logger.info("=== 所有测试通过 ===")
        return True
        
    except Exception as e:
        logger.error(f"读取Excel文件时出错: {e}")
        logger.exception(e)
        return False

def test_multiple_formats():
    """测试多种Excel格式"""
    formats = [".xlsx", ".xls"]
    
    for ext in formats:
        files = [f for f in os.listdir(".") if f.endswith(ext)]
        if files:
            logger.info(f"找到{ext}文件: {files[:3]}")  # 只显示前3个
            for file in files[:1]:  # 只测试第一个文件
                try:
                    logger.info(f"测试读取 {file}")
                    df = pd.read_excel(file)
                    logger.info(f"  成功读取，形状: {df.shape}")
                except Exception as e:
                    logger.error(f"  读取失败: {e}")

if __name__ == "__main__":
    logger.info("开始测试Excel读取环境...")
    
    success = test_excel_reading()
    
    logger.info("=== 额外信息 ===")
    test_multiple_formats()
    
    if success:
        logger.info("🎉 环境测试通过！")
        sys.exit(0)
    else:
        logger.error("❌ 环境测试失败！")
        sys.exit(1)