# 使用官方Python基础镜像
FROM python:3.13.2 as builder

# 设置工作目录
WORKDIR /workflow-agent

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ 

# 复制项目文件
COPY . .

# 暴露端口
EXPOSE 8000

# 设置环境变量（可根据需要覆盖）
ENV MODEL_NAME=gemma3:27b \
    BASE_URL=https://proxyapi.955id.com:60443/bfsuai \
    OUTPUT_DIR=/workflow-agent/output

# 创建持久化目录
RUN mkdir -p ${OUTPUT_DIR} && chmod 777 ${OUTPUT_DIR}

# 运行应用
CMD ["uvicorn", "run_app:app", "--host", "0.0.0.0", "--port", "8000"]