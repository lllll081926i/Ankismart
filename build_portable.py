"""
便携版打包脚本
将应用配置和数据存储在应用目录内，而不是用户目录
"""
import os
import shutil
from pathlib import Path

def create_portable_config():
    """创建便携版配置文件"""
    portable_config = """# Ankismart 便携版配置
# 此文件的存在表示这是便携版，所有配置和数据将存储在应用目录内

portable_mode: true
config_dir: "./config"
data_dir: "./data"
logs_dir: "./logs"
cache_dir: "./cache"
"""

    return portable_config

def setup_portable_structure(dist_dir: Path):
    """设置便携版目录结构"""
    print(f"设置便携版目录结构: {dist_dir}")

    # 创建必要的目录
    dirs = ['config', 'data', 'logs', 'cache']
    for dir_name in dirs:
        dir_path = dist_dir / dir_name
        dir_path.mkdir(exist_ok=True)
        print(f"  创建目录: {dir_name}/")

    # 创建便携版标识文件
    portable_flag = dist_dir / '.portable'
    portable_flag.write_text(create_portable_config(), encoding='utf-8')
    print(f"  创建便携版标识: .portable")

    # 创建 README
    readme_content = """# Ankismart 便携版

这是 Ankismart 的便携版本。所有配置、数据和日志都存储在当前目录下。

## 目录结构

- Ankismart.exe - 主程序
- config/ - 配置文件目录
- data/ - 数据文件目录
- logs/ - 日志文件目录
- cache/ - 缓存文件目录
- .portable - 便携版标识文件

## 使用说明

1. 直接运行 Ankismart.exe 启动程序
2. 所有设置和数据都会保存在当前目录
3. 可以将整个文件夹复制到其他位置或U盘使用

## 注意事项

- 请勿删除 .portable 文件，否则程序将使用系统默认配置目录
- 首次运行需要配置 LLM 提供商和 AnkiConnect
"""

    readme_path = dist_dir / 'README.txt'
    readme_path.write_text(readme_content, encoding='utf-8')
    print(f"  创建说明文件: README.txt")

def main():
    """主函数"""
    # 获取 dist 目录
    dist_dir = Path('dist/Ankismart')

    if not dist_dir.exists():
        print(f"错误: 找不到 dist 目录: {dist_dir}")
        print("请先运行 PyInstaller 构建应用")
        return

    print("=" * 60)
    print("Ankismart 便携版打包工具")
    print("=" * 60)

    # 设置便携版结构
    setup_portable_structure(dist_dir)

    # 创建便携版压缩包
    portable_zip = Path('dist/Ankismart-Portable')
    print(f"\n创建便携版压缩包...")
    shutil.make_archive(str(portable_zip), 'zip', 'dist', 'Ankismart')
    print(f"  完成: {portable_zip}.zip")

    print("\n" + "=" * 60)
    print("便携版打包完成！")
    print("=" * 60)
    print(f"\n输出文件:")
    print(f"  - 便携版目录: {dist_dir}")
    print(f"  - 便携版压缩包: {portable_zip}.zip")

if __name__ == '__main__':
    main()
