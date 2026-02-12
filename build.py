"""
Ankismart 打包脚本
自动构建安装版和便携版
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

def print_header(text):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")

def run_command(cmd, description):
    """运行命令并显示进度"""
    print(f">>> {description}")
    print(f"    命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

    if result.returncode != 0:
        print(f"    ❌ 失败!")
        print(f"    错误输出:\n{result.stderr}")
        return False

    print(f"    ✓ 完成")
    return True

def clean_build():
    """清理构建目录"""
    print_header("清理构建目录")

    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"删除目录: {dir_name}/")
            shutil.rmtree(dir_path)

    print("✓ 清理完成")

def build_with_pyinstaller():
    """使用 PyInstaller 构建应用"""
    print_header("使用 PyInstaller 构建应用")

    if not Path('ankismart.spec').exists():
        print("❌ 错误: 找不到 ankismart.spec 文件")
        return False

    cmd = ['pyinstaller', '--clean', 'ankismart.spec']
    return run_command(cmd, "运行 PyInstaller")

def create_portable_version():
    """创建便携版"""
    print_header("创建便携版")

    dist_dir = Path('dist/Ankismart')
    if not dist_dir.exists():
        print("❌ 错误: 找不到构建输出目录")
        return False

    # 运行便携版打包脚本
    cmd = [sys.executable, 'build_portable.py']
    return run_command(cmd, "配置便携版")

def create_installer():
    """创建安装程序"""
    print_header("创建安装程序")

    # 检查 Inno Setup 是否安装
    inno_setup_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]

    iscc_path = None
    for path in inno_setup_paths:
        if Path(path).exists():
            iscc_path = path
            break

    if not iscc_path:
        print("⚠ 警告: 未找到 Inno Setup")
        print("   请从 https://jrsoftware.org/isdl.php 下载并安装 Inno Setup")
        print("   安装后可以手动运行: ISCC.exe ankismart.iss")
        return False

    if not Path('ankismart.iss').exists():
        print("❌ 错误: 找不到 ankismart.iss 文件")
        return False

    # 创建安装程序输出目录
    Path('dist/installer').mkdir(parents=True, exist_ok=True)

    cmd = [iscc_path, 'ankismart.iss']
    return run_command(cmd, "编译安装程序")

def show_results():
    """显示构建结果"""
    print_header("构建结果")

    results = []

    # 检查便携版
    portable_dir = Path('dist/Ankismart')
    portable_zip = Path('dist/Ankismart-Portable.zip')

    if portable_dir.exists():
        results.append(f"✓ 便携版目录: {portable_dir}")

    if portable_zip.exists():
        size_mb = portable_zip.stat().st_size / (1024 * 1024)
        results.append(f"✓ 便携版压缩包: {portable_zip} ({size_mb:.1f} MB)")

    # 检查安装程序
    installer_dir = Path('dist/installer')
    if installer_dir.exists():
        installers = list(installer_dir.glob('*.exe'))
        for installer in installers:
            size_mb = installer.stat().st_size / (1024 * 1024)
            results.append(f"✓ 安装程序: {installer} ({size_mb:.1f} MB)")

    if results:
        for result in results:
            print(result)
    else:
        print("❌ 未找到构建输出文件")

    print()

def main():
    """主函数"""
    print_header("Ankismart 打包工具")

    # 检查是否在项目根目录
    if not Path('pyproject.toml').exists():
        print("❌ 错误: 请在项目根目录运行此脚本")
        sys.exit(1)

    # 询问是否清理
    response = input("是否清理之前的构建? (y/N): ").strip().lower()
    if response == 'y':
        clean_build()

    # 构建应用
    if not build_with_pyinstaller():
        print("\n❌ PyInstaller 构建失败")
        sys.exit(1)

    # 创建便携版
    if not create_portable_version():
        print("\n❌ 便携版创建失败")
        sys.exit(1)

    # 创建安装程序
    create_installer()  # 即使失败也继续，因为可能没有安装 Inno Setup

    # 显示结果
    show_results()

    print_header("打包完成!")
    print("提示: 如果需要创建安装程序，请确保已安装 Inno Setup")
    print("      下载地址: https://jrsoftware.org/isdl.php")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
