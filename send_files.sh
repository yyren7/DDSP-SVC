#!/bin/bash

# ---!! 重要配置 !! ---
# 请将下面的 IP 地址修改为接收电脑的 IP 地址
RECEIVER_IP="192.168.16.190" # <--- 修改这里为接收电脑的实际 IP 地址
PORT="12345" # 必须与接收端脚本中的 PORT 一致

# 要发送的文件夹相对于当前脚本的路径
# 由于脚本在 DDSP-SVC 目录下，且文件夹是 data/dry-cut，这里保持默认
SOURCE_DIR_PARENT="data"
SOURCE_DIR_NAME="dry-cut"
# ---!! 重要配置结束 !! ---

# 检查 pv 命令是否存在，如果存在则使用它来显示进度
PV_COMMAND=""
if command -v pv &> /dev/null; then
    PV_COMMAND="pv"
    echo "找到 'pv' 命令，将用它显示传输进度。"
else
    echo "未找到 'pv' 命令。如需显示传输进度，请考虑安装它 (例如：sudo apt install pv)。"
    echo "将继续进行无进度显示的传输。"
fi

SOURCE_FULL_PATH="${SOURCE_DIR_PARENT}/${SOURCE_DIR_NAME}"

echo "发送脚本已启动..."
echo "准备发送文件夹: '${SOURCE_FULL_PATH}'"
echo "目标接收电脑 IP: ${RECEIVER_IP}"
echo "目标端口: ${PORT}"
echo "----------------------------------------------------"

if [ ! -d "${SOURCE_FULL_PATH}" ]; then
    echo "错误：源文件夹 '${SOURCE_FULL_PATH}' 不存在！"
    echo "请检查路径是否正确，以及脚本是否在正确的目录下运行。"
    exit 1
fi

echo "重要提示：请确保接收电脑上的接收脚本 (receive_files.sh) 已经启动并在监听端口 ${PORT}。"
read -p "按 Enter键 开始发送..."

echo "正在打包并发送文件，请稍候..."

# -C ${SOURCE_DIR_PARENT} 切换到 data 目录，然后打包 dry-cut，这样解压时不会包含 data/ 这一层
# 如果 PV_COMMAND 为空，则不使用 pv
if [ -n "$PV_COMMAND" ]; then
    tar -cvf - -C "${SOURCE_DIR_PARENT}" "${SOURCE_DIR_NAME}" | ${PV_COMMAND} -s $(du -sb "${SOURCE_FULL_PATH}" | awk '{print $1}') | nc "${RECEIVER_IP}" "${PORT}"
else
    tar -cvf - -C "${SOURCE_DIR_PARENT}" "${SOURCE_DIR_NAME}" | nc "${RECEIVER_IP}" "${PORT}"
fi

if [ $? -eq 0 ]; then
    echo "----------------------------------------------------"
    echo "文件发送完成！"
    echo "请检查接收电脑上的输出以确认接收和解压是否成功。"
else
    echo "----------------------------------------------------"
    echo "错误：文件发送过程中发生错误。"
    echo "可能的原因包括："
    echo "  - 接收端脚本未运行或未在监听正确的端口。"
    echo "  - 网络连接问题。"
    echo "  - 目标 IP 地址或端口错误。"
    exit 1
fi

exit 0 