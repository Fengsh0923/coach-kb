FROM mirror.ccs.tencentyun.com/library/python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir --index-url https://mirrors.tencent.com/pypi/simple/ fastapi uvicorn[standard] jinja2
COPY . /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
