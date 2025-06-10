#!/bin/bash

# ---!! 重要配置 !! ---
# 请将下面的路径修改为您希望在接收电脑上存放 'dry-cut' 文件夹的父目录
# 例如，如果您希望文件最终存放在 /mnt/storage/dry-cut，则设置为 "/mnt/storage"
TARGET_BASE_DIR="/tmp/received_data" # <--- 修改这里为你希望的接收文件夹的父目录
PORT="12345" # 可以根据需要修改端口号，但需与发送端脚本一致
# ---!! 重要配置结束 !! ---

echo "接收脚本已启动..."
echo "将在 '${TARGET_BASE_DIR}' 目录下创建 'dry-cut' 文件夹来存放接收的文件。"
echo "请确保目标目录 '${TARGET_BASE_DIR}' 存在或脚本有权限创建它。"
echo "正在监听端口: ${PORT}"
echo "请现在到发送端电脑上运行发送脚本。"
echo "----------------------------------------------------"

# 确保目标基础目录存在
mkdir -p "${TARGET_BASE_DIR}"
if [ $? -ne 0 ]; then
    echo "错误：无法创建或访问目标目录 '${TARGET_BASE_DIR}'。"
    echo "请检查路径和权限。"
    exit 1
fi

# 等待连接并接收数据，解压到目标基础目录
# tar 会在 TARGET_BASE_DIR 下创建 dry-cut 目录
nc -l -p "${PORT}" | tar -xvf - -C "${TARGET_BASE_DIR}"

if [ $? -eq 0 ]; then
    echo "----------------------------------------------------"
    echo "文件接收和解压完成！"
    echo "文件应该位于: '${TARGET_BASE_DIR}/dry-cut'"
    echo "如果传输中断或出现问题，请检查两端的输出。"
else
    echo "----------------------------------------------------"
    echo "错误：文件接收或解压过程中发生错误。"
    echo "请检查发送端和接收端的错误信息。"
    exit 1
fi

exit 0 