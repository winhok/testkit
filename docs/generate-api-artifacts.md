# 生成 API 工具产物

`generate-api-artifacts` 将一份已复核的 OpenAPI 3.0/3.1 或 Swagger 2.0 定义转换为 Postman Collection、Apifox 可导入 OpenAPI 和 Apache JMeter JMX。源接口定义始终是事实来源，生成文件是可以重建的派生产物。

## 适合什么任务

- 将 OpenAPI 或 Swagger 转成 Postman Collection v2.1。
- 为 Apifox 准备可导入的 OpenAPI 文件。
- 从同一份接口定义生成 JMeter JMX 骨架。
- 一次生成多个目标，并记录格式损失和人工复核项。

它不负责扫描源码、执行 API 请求、运行 Collection/JMX、做模糊测试或压测。只有 curl、自然语言或 Markdown 时，应先形成待复核的 OpenAPI 草稿。

## 输入与产出

输入是一份已复核的 OpenAPI/Swagger 文件。输出目录包含请求的工具文件和 `artifact-manifest.json`；manifest 记录源文件 hash、目标格式、转换警告、格式损失及复核项。

生成前可以先检查契约：

```bash
python skills/generate-api-artifacts/scripts/generate_artifacts.py inspect openapi.yaml
```

一次生成多个目标：

```bash
python skills/generate-api-artifacts/scripts/generate_artifacts.py generate openapi.yaml \
  --target apifox \
  --target jmeter \
  --output-dir api-artifacts
```

Postman 转换需要本机已有 `openapi2postmanv2`，脚本不会隐式下载工具：

```bash
python skills/generate-api-artifacts/scripts/generate_artifacts.py generate openapi.yaml \
  --target postman \
  --output-dir api-artifacts \
  --postman-converter openapi2postmanv2
```

## 交付与安全

- 不在产物中嵌入 Token、Cookie、API key、密码或 client secret。
- 不根据字段名猜测断言，也不执行导入的 Postman script。
- 已有输出默认不覆盖；覆盖必须得到明确授权。
- JMX 只是安全默认值下的脚本骨架，没有负载模型时不能称为生产压测方案。

完整执行契约见 [`generate-api-artifacts`](../skills/generate-api-artifacts/SKILL.md)。需要真正执行接口测试时使用 [API 自动化测试](api-test-automation.md)。
