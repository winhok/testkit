---
name: apitestspec-shared
description: 内部共享资源库，不直接触发。供其他 apitestspec-* 技能引用的 spec 格式定义、示例项目、路由表和共享脚本模块。不要在任何用户场景下直接使用这个 skill。
---

# API TestSpec 共享资源

本目录不是可触发的 skill，而是 apitestspec 套件的公共资源库。

## 内容

- `references/spec-format.md` — 框架原生 spec 的完整格式定义（数据模型、断言运算符、模板语法、Excel/CSV 列定义）
- `references/example-project.md` — 一个完整的最小示例项目，包含 project.yaml、flow、case、.env.example
- `references/routing.md` — 五阶段路由表，供各 skill 引用
- `scripts/_project_template.py` — project.yaml 模板生成函数，供 bootstrap 脚本复用
- `requirements.txt` — Python 依赖声明
